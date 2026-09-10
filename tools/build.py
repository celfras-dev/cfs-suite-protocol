"""Build the public (and, on request, internal) editions.

Public output goes to out/public and is committed; internal output goes to
out/internal, which .gitignore holds, so the edition carrying product values
cannot reach the public repository by habit or by accident.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from jinja2 import Template

from tools import pdf, render
from tools.extract import __main__ as extract_all

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "spec"
LANGS = ("en", "ko", "zh")

PDF_NAME_FMT = "Celfras Standard Protocol V{ver} ({LANG}).pdf"


def forbidden_public_values() -> set[int]:
    """Every value the product bakes in, read from the source.

    Deliberately not a literal tuple. The hand-written one in this plan's
    first draft was already wrong -- it missed CHG_TIMEOUT_TH (600) and
    LONG_PUFF_TH (10000). Deriving it means a new default in par_map.json
    joins the gate on its own.
    """
    from tools.extract import varpar
    values = {r["default"]
              for rows in varpar.extract(internal=True)["par"].values()
              for r in rows if "default" in r}
    # An empty set here would make every leak assertion in
    # test_public_leak.py pass vacuously -- the gate would be silently off
    # instead of enforcing anything. Fail loudly instead. This must not be
    # a bare `assert`: `python -O` strips those, which would silently turn
    # this guard back off in exactly the situation it exists to catch.
    if not values:
        raise RuntimeError(
            "forbidden_public_values() derived an empty set -- the leak gate "
            "would pass vacuously; check that par_map.json still has entries "
            "with a 'default' field"
        )
    return values


def _load_generated(gen_dir: Path) -> dict:
    return {p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(gen_dir.glob("*.json"))}


def _gen_dir_for(internal: bool, out_root: Path) -> Path:
    """Where extracted JSON goes, for a given edition/out_root combination.

    Pulled out of build() as a pure function (no I/O) precisely so the
    out_root == ROOT branches -- the ones that decide where the artefacts
    that actually get committed and shipped land -- can be exercised by a
    test directly, without that test performing a real ROOT-rooted build
    (which would touch the actual repository just to prove a path).

    The public generated tables are committed, so a standalone clone can
    build without the product repos present. The internal ones never are:
    for a real (out_root == ROOT) internal build they are nested under
    out/internal/, which .gitignore already holds, rather than at the
    repo root -- a real product default sitting in an ungitignored
    top-level directory is exactly the accidental leak this build exists
    to prevent.
    """
    if not internal and out_root == ROOT:
        return SPEC / "_generated"
    if internal and out_root == ROOT:
        return out_root / "out" / "internal" / "_generated"
    return out_root / "_generated"


def build(internal: bool = False, out_root: Path | None = None,
          langs: tuple[str, ...] = LANGS) -> dict:
    # out_root is the root of every artefact, so a test can hand it a
    # tmp_path and leave the repository untouched.
    out_root = out_root or ROOT
    edition = "internal" if internal else "public"

    gen_dir = _gen_dir_for(internal, out_root)
    extract_all.run(gen_dir, internal=internal)
    gen = _load_generated(gen_dir)
    ver = gen["version"]["cmd_set_version"]

    pdf_dir = out_root / "out" / edition
    site_dir = out_root / "site"
    site_dir.mkdir(parents=True, exist_ok=True)

    pdfs: dict[str, Path] = {}
    site: dict[str, Path] = {}
    # The literal HTML string each PDF is printed from. This is the
    # authoritative surface for the public-leak gate (see
    # tests/test_public_leak.py): it is plain text, so it is immune to the
    # PDF-text-extraction quirks below. The PDF-text check that gate also
    # runs is a second line of defence, not the guarantee -- pypdf's
    # extract_text() is a heuristic over the PDF's glyph layout, and it has
    # (at least) three known holes:
    #   1. `letter-spacing` CSS spreads a run of digits across separate
    #      glyph placements, so "10000" can extract as "1 0 0 0 0" and slip
    #      past a word-boundary regex. spec/assets/style.css already uses
    #      letter-spacing (on .badge-internal), so this is one rule change
    #      away from a real leak going undetected by that check alone.
    #   2. A non-breaking space (`&nbsp;`, U+00A0) inside a number extracts
    #      byte-for-byte ("10\xa0000"), which a regex tuned for plain ASCII
    #      digits does not match.
    #   3. Text drawn into a <canvas> has no text layer at all: visually
    #      present, invisible to extract_text().
    # None of these change what is actually in print_html, which is why it,
    # not the rendered PDF, is what must be checked to actually guarantee
    # nothing leaks.
    print_html: dict[str, str] = {}
    for lang in langs:
        md = (SPEC / f"{lang}.md").read_text(encoding="utf-8")
        page = render.render_page(lang, md, gen, for_print=False)
        sp = site_dir / f"{lang}.html"
        sp.write_text(page, encoding="utf-8")
        site[lang] = sp

        printable = render.render_page(lang, md, gen, for_print=True)
        print_html[lang] = printable
        name = PDF_NAME_FMT.format(ver=ver, LANG=lang.upper())
        pdfs[lang] = pdf.html_to_pdf(printable, pdf_dir / name)

    # Non-language site artefacts, kept out of `site` so that dict stays
    # exactly {lang: page path} -- existing tests iterate `site` expecting
    # only the three language pages, and index.html is not a fourth
    # language. A separate dict lets the leak gate reach it (and anything
    # else that joins it later) without disturbing that contract.
    site_extra: dict[str, Path] = {}
    if not internal:
        dl = site_dir / "downloads"
        dl.mkdir(exist_ok=True)
        for p in pdfs.values():
            shutil.copy2(p, dl / p.name)
        site_extra["index"] = _write_index(site_dir, ver, pdfs)

    return {"version": ver, "edition": edition, "pdfs": pdfs, "site": site,
            "site_extra": site_extra, "print_html": print_html}


def _write_index(site_dir: Path, ver: str, pdfs: dict[str, Path]) -> Path:
    """Render the site's front door: language switcher, PDF downloads, and
    a placeholder slot for the reference example code (not a link yet --
    see examples/README.md).

    Stays entirely inside site_dir, same as the language pages above, so a
    build into a tmp_path out_root never touches the repository.
    """
    tpl = Template((SPEC / "assets" / "index.html.j2").read_text(encoding="utf-8"))
    out = site_dir / "index.html"
    out.write_text(
        tpl.render(
            ver=ver,
            pdf_names=[(lang, p.name) for lang, p in sorted(pdfs.items())],
            css=(SPEC / "assets" / "style.css").read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the Celfras Standard Protocol document")
    ap.add_argument("--internal", action="store_true",
                    help="include product default values; output stays out of git")
    a = ap.parse_args()
    got = build(internal=a.internal)
    print(f"{got['edition']} edition V{got['version']}")
    for lang, p in got["pdfs"].items():
        print(f"  {lang}: {p}")


if __name__ == "__main__":
    main()
