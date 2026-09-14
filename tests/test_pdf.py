import subprocess
from pathlib import Path

import pypdf
import pytest

from tools import pdf

CJK_PAGE = """<!doctype html><meta charset="utf-8">
<style>@page{size:A4;margin:18mm}
body{font-family:"Microsoft YaHei","Noto Sans SC",sans-serif}</style>
<h1>Celfras Standard Protocol V4.0.0</h1>
<p>帧格式与校验和</p><p>프레임 포맷과 체크섬</p>"""


def _pdf_arg_path(cmd) -> Path:
    """Pull the destination path back out of the --print-to-pdf=... arg."""
    for part in cmd:
        if isinstance(part, str) and part.startswith("--print-to-pdf="):
            return Path(part.split("=", 1)[1])
    raise AssertionError("no --print-to-pdf= arg in command")


def test_browser_is_found():
    assert pdf.find_browser().exists()


def test_produces_a_readable_pdf(tmp_path: Path):
    out = pdf.html_to_pdf(CJK_PAGE, tmp_path / "t.pdf")
    assert out.exists() and out.stat().st_size > 5000
    r = pypdf.PdfReader(str(out))
    assert len(r.pages) >= 1
    text = r.pages[0].extract_text()
    assert "Celfras Standard Protocol V4.0.0" in text


def test_missing_browser_raises_clear_error(monkeypatch, tmp_path: Path):
    """No Chrome/Edge candidate exists -> BrowserMissing, not a silent bad path."""
    monkeypatch.setattr(pdf, "_CANDIDATES", [tmp_path / "no-such-browser.exe"])
    out_path = tmp_path / "out.pdf"

    with pytest.raises(pdf.BrowserMissing, match="Chrome or Edge"):
        pdf.html_to_pdf(CJK_PAGE, out_path)

    assert not out_path.exists()


def test_browser_timeout_raises_clear_error(monkeypatch, tmp_path: Path):
    """subprocess.run timing out -> RuntimeError naming the timeout, not a bare
    TimeoutExpired and never a returned Path."""

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout"))

    monkeypatch.setattr(pdf.subprocess, "run", fake_run)
    out_path = tmp_path / "out.pdf"

    with pytest.raises(RuntimeError, match="did not finish printing.*120s"):
        pdf.html_to_pdf(CJK_PAGE, out_path)

    assert not out_path.exists()


def test_browser_nonzero_exit_raises_clear_error(monkeypatch, tmp_path: Path):
    """Chrome exiting non-zero -> RuntimeError carrying the exit code and
    stderr, not a bare CalledProcessError and never a returned Path."""

    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=1, cmd=cmd, output=b"", stderr=b"boom: bad url"
        )

    monkeypatch.setattr(pdf.subprocess, "run", fake_run)
    out_path = tmp_path / "out.pdf"

    with pytest.raises(RuntimeError, match="exited 1"):
        pdf.html_to_pdf(CJK_PAGE, out_path)

    assert not out_path.exists()

    # message must also carry the stderr, not just the exit code
    with pytest.raises(RuntimeError, match="boom: bad url"):
        pdf.html_to_pdf(CJK_PAGE, out_path)


def test_clean_exit_with_no_file_raises_clear_error(monkeypatch, tmp_path: Path):
    """Chrome exits 0 but never wrote the destination -> RuntimeError, never a
    Path pointing at a file that doesn't exist."""

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(pdf.subprocess, "run", fake_run)
    out_path = tmp_path / "out.pdf"

    with pytest.raises(RuntimeError, match="missing or zero bytes"):
        pdf.html_to_pdf(CJK_PAGE, out_path)

    assert not out_path.exists()


def test_clean_exit_with_empty_file_raises_clear_error(monkeypatch, tmp_path: Path):
    """Chrome exits 0 and leaves a zero-byte PDF -> RuntimeError, never a Path
    pointing at an unusable (empty) artifact."""

    def fake_run(cmd, **kwargs):
        _pdf_arg_path(cmd).write_bytes(b"")
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(pdf.subprocess, "run", fake_run)
    out_path = tmp_path / "out.pdf"

    with pytest.raises(RuntimeError, match="missing or zero bytes"):
        pdf.html_to_pdf(CJK_PAGE, out_path)

    # the guard's whole point: an empty file must not be handed back as usable
    assert out_path.exists()
    assert out_path.stat().st_size == 0
