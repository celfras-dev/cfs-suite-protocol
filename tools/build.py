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
    # instead of enforcing anything. Fail loudly instead.
    assert values, (
        "forbidden_public_values() derived an empty set -- the leak gate "
        "would pass vacuously; check that par_map.json still has entries "
        "with a 'default' field"
    )
    return values


def _load_generated(gen_dir: Path) -> dict:
    return {p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(gen_dir.glob("*.json"))}


def build(internal: bool = False, out_root: Path | None = None,
          langs: tuple[str, ...] = LANGS) -> dict:
    # out_root is the root of every artefact, so a test can hand it a
    # tmp_path and leave the repository untouched.
    out_root = out_root or ROOT
    edition = "internal" if internal else "public"

    # The public generated tables are committed, so a standalone clone can
    # build without the product repos present. The internal ones never are:
    # for a real (out_root == ROOT) internal build they are nested under
    # out/internal/, which .gitignore already holds, rather than at the
    # repo root -- a real product default sitting in an ungitignored
    # top-level directory is exactly the accidental leak this build exists
    # to prevent.
    if not internal and out_root == ROOT:
        gen_dir = SPEC / "_generated"
    elif internal and out_root == ROOT:
        gen_dir = out_root / "out" / "internal" / "_generated"
    else:
        gen_dir = out_root / "_generated"
    extract_all.run(gen_dir, internal=internal)
    gen = _load_generated(gen_dir)
    ver = gen["version"]["cmd_set_version"]

    pdf_dir = out_root / "out" / edition
    site_dir = out_root / "site"
    site_dir.mkdir(parents=True, exist_ok=True)

    pdfs: dict[str, Path] = {}
    site: dict[str, Path] = {}
    for lang in langs:
        md = (SPEC / f"{lang}.md").read_text(encoding="utf-8")
        page = render.render_page(lang, md, gen, for_print=False)
        sp = site_dir / f"{lang}.html"
        sp.write_text(page, encoding="utf-8")
        site[lang] = sp

        printable = render.render_page(lang, md, gen, for_print=True)
        name = PDF_NAME_FMT.format(ver=ver, LANG=lang.upper())
        pdfs[lang] = pdf.html_to_pdf(printable, pdf_dir / name)

    if not internal:
        dl = site_dir / "downloads"
        dl.mkdir(exist_ok=True)
        for p in pdfs.values():
            shutil.copy2(p, dl / p.name)

    return {"version": ver, "edition": edition, "pdfs": pdfs, "site": site}


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
