"""The built-output gate in test_public_leak.py never looks at this
repository's own tracked source. That blind spot is exactly how the
2026-09-10 leak happened: two internal working documents were copied
straight into docs/superpowers/ and would have been pushed with everything
in them -- the complete set of forbidden product values, several paired
with the parameter name they belong to, an assertion line carrying a
threshold and its identifier, and absolute filesystem paths off the
author's own machine. Removing those two files fixed that specific leak;
this file is the durable fix, so the next document dropped anywhere in the
tree fails here before it ever reaches git push.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from tools import build

ROOT = Path(__file__).resolve().parent.parent


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [f for f in out.split("\n") if f.strip()]


def test_no_forbidden_value_in_any_tracked_file():
    """Scans every tracked file -- not just built output -- for the leak
    gate's values.

    Values come from build.leak_gate_values(), never hand-written here (the
    same reasoning as forbidden_public_values() itself: a hand-written list
    is exactly the kind of fact that goes stale).

    Matching uses the same digit-boundary rule test_public_leak.py uses
    (`(?<![0-9.])N(?![0-9.])`), so a shorter gate value cannot match inside
    a longer number that merely contains its digits, plus one addition: a
    match immediately preceded by "0x"/"0X" is skipped. A hex literal's
    digits are not a product threshold -- a CRC bit mask can share digits
    with a decimal gate value while meaning something entirely unrelated --
    and this repo's own CRC worked examples in spec/*.md (0x0DE7, 0x861A,
    0x29B1) are exactly that shape, even though none of them currently
    collides. Deliberately narrow (a hex prefix check, not a file-level
    exclusion list): excluding whole files by name would recreate the same
    blind spot this test exists to close.

    Note this docstring names no gate value as a bare decimal, on purpose.
    This file is tracked, so the scanner reads it too -- an illustrative
    number here would flag itself. Its sibling below solves the same
    problem by assembling its marker from parts. A detector that has to be
    exempted from its own rule is a detector with a hole in it.

    Binary or non-UTF-8 files are skipped rather than crashing the test --
    they cannot carry a text leak, and this repo does not need to inspect
    PDF bytes here (test_public_leak.py already covers PDF text directly).
    """
    gate = build.leak_gate_values()
    bad = []
    for f in _tracked_files():
        path = ROOT / f
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for value in gate:
            pattern = rf"(?<!0[xX])(?<![0-9.]){value}(?![0-9.])"
            for m in re.finditer(pattern, text):
                line_no = text.count("\n", 0, m.start()) + 1
                bad.append(f"{f}:{line_no}: forbidden value {value}")
    assert not bad, "tracked-file leak(s) found:\n" + "\n".join(bad)


def test_no_developer_machine_path_in_any_tracked_file():
    """The leaked documents also carried absolute filesystem paths off the
    author's own machine (a drive letter plus this company's sync-folder
    name). That is exactly the kind of thing a working document drops in
    without thinking, and it must never reach a public repo.

    The marker is assembled from parts rather than written as one
    contiguous string: this test file is itself tracked, and a plain
    substring search -- which is what `git grep` does, and what the
    pre-push audit this test mirrors uses -- must not flag this detector
    as a second instance of the thing it detects.
    """
    marker = "Baidu" + "Sync" + "disk"
    hits = subprocess.run(
        ["git", "-C", str(ROOT), "grep", "-l", marker],
        capture_output=True, text=True,
    ).stdout.split()
    assert not hits, f"developer-machine path marker found in: {hits}"
