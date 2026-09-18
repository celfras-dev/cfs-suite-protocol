"""Read source files from the sibling product repos.

Everything is read from the committed tree (``git show HEAD:<path>``),
never from the working tree. A bench session routinely swaps
CFS-ECIG-SUITE/pc_app/conf/*.json for another board's copy; reading the
working tree would put that board's tables into the standard document.

Since 2026-09-19 the checkouts live in the cfs-suite org folder, which
mirrors Gitea, and a product *tree* may be several git repos: the bridge
tree is an umbrella repo whose fw/brd01, fw/brd02, pc_app, ota and hw
sub-folders are repos of their own. Callers keep naming files by tree and
tree-relative path ("CFS-SUITE-BRIDGE", "fw/brd01/App/Inc/app_version.h");
this module finds the git repo that actually holds the file.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

# The cfs-suite org folder: this repo is <org>/protocol.
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Product trees by their historical names (what the extractors and the spec
# text use) -> checkout folder relative to the org folder. `skip` lists
# sub-folders whose nested repos are not product source (the OTA release
# clones carry manifests that mention cmd_set but are outputs, not copies).
SIBLINGS: dict[str, dict] = {
    "CFS-ECIG-SUITE/FW": {"path": "evapor/fw/framework"},
    "CFS-ECIG-SUITE/pc_app": {"path": "evapor/pc_app"},
    "CFS-SUITE-BRIDGE": {"path": "bridge", "skip": ("ota",)},
    "LIB-MCU": {"path": "lib-mcu"},
}

# How deep to look for nested .git directories inside a tree.
_NESTED_DEPTH = 3


class SourceMissing(Exception):
    """A source repo or a path inside it could not be read."""


def repo_path(name: str) -> Path:
    """The checkout folder of product tree `name`."""
    rel = SIBLINGS.get(name, {"path": name})["path"]
    p = (PROJECT_ROOT / rel).resolve()
    if not p.is_dir():
        raise SourceMissing(f"source repo not found: {name} (expected {p})")
    return p


def git_trees(name: str) -> list[tuple[Path, str]]:
    """Every git repo that makes up product tree `name`, as (repo dir,
    tree-relative prefix) pairs, root first. A plain repo yields one pair
    with prefix ""; the bridge tree yields the umbrella plus its nested
    repos ("fw/brd01", "fw/brd02", "pc_app", "hw")."""
    root = repo_path(name)
    skip = SIBLINGS.get(name, {}).get("skip", ())
    trees = [(root, "")]

    def walk(d: Path, depth: int) -> None:
        if depth > _NESTED_DEPTH:
            return
        for child in sorted(d.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            rel = child.relative_to(root).as_posix()
            if rel in skip or rel.split("/")[0] in skip:
                continue
            if (child / ".git").exists():
                trees.append((child, rel))
                continue  # a nested repo owns everything below it
            walk(child, depth + 1)

    walk(root, 1)
    return trees


def _owner(name: str, relpath: str) -> tuple[Path, str]:
    """The git repo holding `relpath` of tree `name`, and the path inside it:
    the deepest nested repo on the way down, else the tree root."""
    root = repo_path(name)
    parts = Path(relpath).parts
    owner, rest = root, parts
    cur = root
    for i, part in enumerate(parts[:-1]):
        cur = cur / part
        if (cur / ".git").exists():
            owner, rest = cur, parts[i + 1:]
    return owner, "/".join(rest)


def read_committed(repo: str, relpath: str) -> str:
    root, inner = _owner(repo, relpath)
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "show", f"HEAD:{inner}"],
            capture_output=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        raise SourceMissing(
            f"{repo}:{relpath} is not in HEAD ({e.stderr.decode(errors='replace').strip()})"
        ) from e
    return out.stdout.decode("utf-8")
