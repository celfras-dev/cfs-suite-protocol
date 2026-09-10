from pathlib import Path

import pypdf
import pytest

from tools import pdf

CJK_PAGE = """<!doctype html><meta charset="utf-8">
<style>@page{size:A4;margin:18mm}
body{font-family:"Microsoft YaHei","Noto Sans SC",sans-serif}</style>
<h1>Celfras Standard Protocol V2.11.0</h1>
<p>帧格式与校验和</p><p>프레임 포맷과 체크섬</p>"""


def test_browser_is_found():
    assert pdf.find_browser().exists()


def test_produces_a_readable_pdf(tmp_path: Path):
    out = pdf.html_to_pdf(CJK_PAGE, tmp_path / "t.pdf")
    assert out.exists() and out.stat().st_size > 5000
    r = pypdf.PdfReader(str(out))
    assert len(r.pages) >= 1
    text = r.pages[0].extract_text()
    assert "Celfras Standard Protocol V2.11.0" in text
