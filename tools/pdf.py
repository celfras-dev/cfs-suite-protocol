"""HTML -> PDF via headless Chrome.

Chrome/Edge ship with Windows and carry the CJK fonts already installed, so
this needs no toolchain install (no pandoc, no LaTeX, no GTK). The page is
written to a temp file rather than piped, because --print-to-pdf only takes
a URL.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]


class BrowserMissing(Exception):
    """No Chrome or Edge to print with."""


def find_browser() -> Path:
    for p in _CANDIDATES:
        if p.exists():
            return p
    raise BrowserMissing(
        "need Chrome or Edge for --print-to-pdf; looked in:\n  "
        + "\n  ".join(str(p) for p in _CANDIDATES)
    )


def html_to_pdf(html_text: str, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "page.html"
        src.write_text(html_text, encoding="utf-8")
        try:
            subprocess.run(
                [
                    str(find_browser()),
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--no-pdf-header-footer",
                    f"--print-to-pdf={out_path}",
                    src.as_uri(),
                ],
                check=True, capture_output=True, timeout=120,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"browser did not finish printing {out_path} within "
                f"{exc.timeout}s; giving up rather than hanging the build"
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"browser exited {exc.returncode} while printing {out_path}\n"
                f"stderr: {exc.stderr!r}"
            ) from exc
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError(
            f"browser produced no usable file at {out_path} "
            "(missing or zero bytes) even though it exited cleanly"
        )
    return out_path
