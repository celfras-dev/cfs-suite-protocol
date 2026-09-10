import re

import pypdf
import pytest

from tools import build


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


def test_internal_edition_is_marked_and_kept_apart(tmp_path):
    got = build.build(internal=True, out_root=tmp_path)
    for p in got["pdfs"].values():
        assert "internal" in str(p.parent).replace("\\", "/")
        assert "INTERNAL" in _pdf_text(p)
