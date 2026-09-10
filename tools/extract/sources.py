"""Read source files from the sibling product repos.

Everything is read from the committed tree (``git show HEAD:<path>``),
never from the working tree. A bench session routinely swaps
CFS-ECIG-SUITE/pc_app/conf/*.json for another board's copy; reading the
working tree would put that board's tables into the standard document.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class SourceMissing(Exception):
    """A source repo or a path inside it could not be read."""


def repo_path(name: str) -> Path:
    p = PROJECT_ROOT / name
    if not p.is_dir():
        raise SourceMissing(f"source repo not found: {p}")
    return p


def read_committed(repo: str, relpath: str) -> str:
    root = repo_path(repo)
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "show", f"HEAD:{relpath}"],
            capture_output=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        raise SourceMissing(
            f"{repo}:{relpath} is not in HEAD ({e.stderr.decode(errors='replace').strip()})"
        ) from e
    return out.stdout.decode("utf-8")
