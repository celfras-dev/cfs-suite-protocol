import re
from pathlib import Path

import pypdf
import pytest

from tools import build, render

SPEC = Path(__file__).resolve().parent.parent / "spec"


@pytest.fixture(scope="module")
def public_build(tmp_path_factory):
    return build.build(internal=False, out_root=tmp_path_factory.mktemp("pub"))


def _pdf_text(p):
    return "\n".join(pg.extract_text() or "" for pg in pypdf.PdfReader(str(p)).pages)


def test_all_three_languages_are_built(public_build):
    assert set(public_build["pdfs"]) == {"en", "ko", "zh"}
    for p in public_build["pdfs"].values():
        assert p.exists()


def test_filename_carries_the_cmd_set_version(public_build):
    for lang, p in public_build["pdfs"].items():
        assert p.name.startswith("Celfras Standard Protocol V2.11.0 (")
        assert p.name.endswith(f"({lang.upper()}).pdf")


def test_forbidden_public_values_is_not_empty():
    """A gate nobody can fail is a gate that isn't there: an empty set would
    make every leak assertion below pass vacuously.

    Deliberately checks forbidden_public_values() itself, not
    leak_gate_values() -- see below, every actual leak assertion in this
    file scans against build.leak_gate_values() (forbidden minus
    build.PROTOCOL_VALUE_EXEMPTIONS, see tools/build.py and
    tests/test_build_exemptions.py), because the gate matches raw numbers
    and a real protocol constant can legitimately collide with a product
    default (BURST_PERIOD_MS_MAX == LED_BREATH_PERIOD_MS == 1000)."""
    assert len(build.forbidden_public_values()) > 0


def test_no_product_threshold_leaks_into_public_pdfs(public_build):
    """The public edition defines what an id means, never what this product
    writes into it. A bare number here is a leak."""
    for lang, p in public_build["pdfs"].items():
        text = _pdf_text(p)
        for value in build.leak_gate_values():
            assert not re.search(rf"(?<![\d.]){value}(?![\d.])", text), (
                f"{value} leaked into the {lang} public PDF"
            )


def test_no_product_threshold_leaks_into_the_site(public_build):
    for p in public_build["site"].values():
        text = p.read_text(encoding="utf-8")
        for value in build.leak_gate_values():
            assert not re.search(rf"(?<![\d.]){value}(?![\d.])", text), (
                f"{value} leaked into {p.name}"
            )


def test_no_product_threshold_leaks_into_site_extra(public_build):
    """Non-language site artefacts (currently just index.html) are not part
    of the `site` dict -- see the comment in tools/build.py -- so they need
    their own pass over the same forbidden set. Anything added to
    `site_extra` in the future is covered automatically by this loop."""
    for p in public_build["site_extra"].values():
        text = p.read_text(encoding="utf-8")
        for value in build.leak_gate_values():
            assert not re.search(rf"(?<![\d.]){value}(?![\d.])", text), (
                f"{value} leaked into {p.name}"
            )


def test_internal_edition_is_marked_and_kept_apart(tmp_path):
    got = build.build(internal=True, out_root=tmp_path)
    for p in got["pdfs"].values():
        assert "internal" in str(p.parent).replace("\\", "/")
        assert "INTERNAL" in _pdf_text(p)


def test_no_product_threshold_leaks_into_print_html(public_build):
    """The authoritative leak check: print_html is the literal HTML string
    each PDF is printed from. It is plain text, so unlike the PDF-text
    check above it cannot be fooled by how a particular extractor reads
    glyphs back out of the rendered PDF (letter-spacing splitting digits,
    a non-breaking space inside a number, text drawn into a <canvas> --
    see the comment in tools/build.py). Kept alongside, not instead of,
    the PDF-text check: that one catches a different class of mistake,
    such as a bug in pdf.py itself changing what actually gets printed."""
    for lang, html in public_build["print_html"].items():
        for value in build.leak_gate_values():
            assert not re.search(rf"(?<![\d.]){value}(?![\d.])", html), (
                f"{value} leaked into the {lang} public print HTML"
            )


def test_no_page_ever_shows_a_default_in_the_public_edition(public_build):
    """No shipped public page may carry a Default column, whatever tables the
    prose happens to place. This is the whole-document half of the check;
    the mechanism itself is exercised directly below."""
    for lang in ("en", "ko", "zh"):
        assert "Default" not in public_build["site"][lang].read_text(encoding="utf-8")


def test_par16_defaults_render_only_in_internal_build():
    """Exercises the actual mechanism this whole gate exists to protect:
    render.py's `internal = any("default" in r for r in rows_src)`, which
    decides whether the Default column is emitted at all. A regression in
    that one line -- always showing the Default column, or never showing
    it -- would go undetected by every other test here.

    Driven from a placeholder this test writes itself rather than from
    whichever placeholders the shipped spec/*.md happen to contain. It used
    to read the built pages, which silently made a stub in every language
    file load-bearing: Part I of the standard defines the var/par *commands*
    and states that the id maps are product-defined, so it carries no par
    table at all, and writing it correctly turned this test red. A coverage
    check that depends on the prose keeping a particular table is testing
    the prose, not render.py."""
    from tools.extract import varpar

    full = varpar.extract(internal=True)
    ph = "{{table:par:par16}}"
    pub = render.expand_tables(ph, {"varpar": varpar.extract(internal=False)})
    int_ = render.expand_tables(ph, {"varpar": full})

    assert "Default" not in pub
    assert "Default" in int_
    # LONG_PUFF_TH's real default must actually appear as a value, not just
    # the column header. Looked up by name at runtime rather than written
    # as a literal here, so this test does not itself carry the real
    # product value as text (see tests/test_tracked_source_leak.py).
    long_puff_default = next(
        e["default"] for e in full["par"]["par16"] if e["name"] == "LONG_PUFF_TH"
    )
    assert str(long_puff_default) in int_
    assert str(long_puff_default) not in pub


def test_shipped_prose_actually_places_a_par_or_var_table():
    """The whole-document leak assertions above
    (test_no_product_threshold_leaks_into_public_pdfs/_the_site/
    _site_extra/_print_html) scan *built* output -- what spec/*.md's prose
    actually renders -- not the extraction layer directly. That scan is
    only capable of catching a real leak if the built output contains a
    par/var table in the first place: forbidden_public_values() is derived
    from par_map.json defaults (tools/build.py), and those numbers can
    only appear on a rendered page via a `{{table:par:...}}` or
    `{{table:var:...}}` placeholder.

    If a future prose edit removed every such placeholder from all three
    editions (as could legitimately happen -- see
    test_par16_defaults_render_only_in_internal_build's docstring, which
    already had to stop depending on the prose for exactly this reason),
    the whole-document assertions above would keep passing -- there would
    be nothing to check -- while silently testing nothing. This test makes
    that precondition explicit and self-checking, so losing it fails here
    instead of nowhere.

    This does not duplicate test_par16_defaults_render_only_in_internal_build:
    that one proves the *mechanism* (render.py hides Default in public mode)
    from a placeholder it writes itself, independent of the shipped prose.
    This one proves the *shipped prose* still exercises that mechanism at
    all, which is what the whole-document tests actually rely on.

    Verified to discriminate: temporarily stripping every {{table:par...}}
    and {{table:var...}} placeholder from spec/en.md turns this test red;
    restoring the file turns it green again (done by hand while writing
    this test, not run as part of the suite)."""
    ph = re.compile(r"\{\{table:(?:par|var):[a-z0-9_]+\}\}")
    for lang in ("en", "ko", "zh"):
        text = (SPEC / f"{lang}.md").read_text(encoding="utf-8")
        assert ph.search(text), (
            f"{lang}.md has no {{{{table:par:...}}}} or {{{{table:var:...}}}} "
            "placeholder -- the whole-document leak-gate assertions in this "
            "file would no longer have anything to check"
        )
