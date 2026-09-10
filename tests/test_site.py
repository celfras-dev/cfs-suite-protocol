from urllib.parse import unquote

from tools import build


def test_index_links_every_language_and_pdf(tmp_path):
    got = build.build(internal=False, out_root=tmp_path)
    index = (got["site"]["en"].parent / "index.html").read_text(encoding="utf-8")
    for lang in ("en", "ko", "zh"):
        assert f'href="{lang}.html"' in index
    for p in got["pdfs"].values():
        assert p.name in index


def test_examples_slot_is_present_but_not_yet_a_link(tmp_path):
    got = build.build(internal=False, out_root=tmp_path)
    index = (got["site"]["en"].parent / "index.html").read_text(encoding="utf-8")
    assert "example" in index.lower()
    assert 'class="pending"' in index


def test_download_hrefs_resolve_to_real_files_on_disk(tmp_path):
    """The PDF filenames contain spaces and parentheses (e.g. "Celfras
    Standard Protocol V2.11.0 (EN).pdf"). A byte-for-byte href would not be
    a valid URL, so the template must percent-encode it -- but that is only
    correct if the *encoded* href, once decoded, still names the file that
    is actually on disk next to index.html. Check that by resolving the
    href the way a browser would, not by eye."""
    got = build.build(internal=False, out_root=tmp_path)
    site_dir = got["site"]["en"].parent
    index = (site_dir / "index.html").read_text(encoding="utf-8")

    for lang, p in got["pdfs"].items():
        needle = f'>{p.name}</a>'
        assert needle in index, f"{lang} download link text missing for {p.name}"

        start = index.rindex('href="', 0, index.index(needle)) + len('href="')
        end = index.index('"', start)
        href = index[start:end]

        assert not href.startswith("/"), f"{lang} href must be relative, got {href!r}"
        assert "://" not in href, f"{lang} href must not be an external URL, got {href!r}"

        resolved = (site_dir / unquote(href)).resolve()
        assert resolved.is_file(), (
            f"{lang} href {href!r} decodes to {resolved}, which does not exist"
        )
        # site/downloads/<name> is a shutil.copy2() of out/public/<name>, so
        # they are two files, not one -- compare content, not path identity.
        assert resolved.read_bytes() == p.read_bytes()
