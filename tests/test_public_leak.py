import re

import pypdf
import pytest

from tools import build


@pytest.fixture(scope="module")
def public_build(tmp_path_factory):
    return build.build(internal=False, out_root=tmp_path_factory.mktemp("pub"))


@pytest.fixture(scope="module")
def internal_build(tmp_path_factory):
    return build.build(internal=True, out_root=tmp_path_factory.mktemp("int"))


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
    make every leak assertion below pass vacuously."""
    assert len(build.forbidden_public_values()) > 0


def test_no_product_threshold_leaks_into_public_pdfs(public_build):
    """The public edition defines what an id means, never what this product
    writes into it. A bare number here is a leak."""
    for lang, p in public_build["pdfs"].items():
        text = _pdf_text(p)
        for value in build.forbidden_public_values():
            assert not re.search(rf"(?<![\d.]){value}(?![\d.])", text), (
                f"{value} leaked into the {lang} public PDF"
            )


def test_no_product_threshold_leaks_into_the_site(public_build):
    for p in public_build["site"].values():
        text = p.read_text(encoding="utf-8")
        for value in build.forbidden_public_values():
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
        for value in build.forbidden_public_values():
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
        for value in build.forbidden_public_values():
            assert not re.search(rf"(?<![\d.]){value}(?![\d.])", html), (
                f"{value} leaked into the {lang} public print HTML"
            )


def test_par16_defaults_render_only_in_internal_build(public_build, internal_build):
    """Exercises the actual mechanism this whole gate exists to protect:
    render.py's `internal = any("default" in r for r in rows_src)`, which
    decides whether the Default column is emitted at all. Before the
    {{table:par:par16}} stub was added to spec/*.md, no table rendered in
    the whole suite ever carried a default, so a regression in that one
    line -- e.g. always showing the Default column, or never showing it --
    would have gone undetected by every other test here."""
    for lang in ("en", "ko", "zh"):
        pub_html = public_build["site"][lang].read_text(encoding="utf-8")
        int_html = internal_build["site"][lang].read_text(encoding="utf-8")
        assert "Default" not in pub_html
        assert "Default" in int_html
        # LONG_PUFF_TH's real default (par16 id 6) -- must actually appear
        # as a value, not just the column header.
        assert "10000" in int_html
        assert "10000" not in pub_html
