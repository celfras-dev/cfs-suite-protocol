"""The three language editions must never drift apart in structure.

spec/{en,ko,zh}.md are hand-written prose in three languages, but they are
supposed to be the same document: same section/heading layout, same
{{table:...}} placeholders in the same order. Nothing else enforces that --
tools/render.py expands whichever placeholders a given file happens to
contain, and would happily render three documents with different tables in
them without complaining. A translator (or a later prose edit) can silently
drop a heading or a placeholder in just one language; this is the only
check that would catch it.

This is a structural check, not a translation check: it does not read what
the headings or notes say, only how many of them there are, at what level,
and in what placeholder order. That is deliberate -- verifying translated
prose is a human job.
"""
from __future__ import annotations

import re
from pathlib import Path

SPEC = Path(__file__).resolve().parent.parent / "spec"
LANGS = ("en", "ko", "zh")

_HEADING = re.compile(r"^(#{1,6})[ \t]", re.MULTILINE)
_PLACEHOLDER = re.compile(r"\{\{table:[a-z_0-9:]+\}\}")


def _heading_levels(text: str) -> list[int]:
    return [len(m.group(1)) for m in _HEADING.finditer(text)]


def _placeholders(text: str) -> list[str]:
    return _PLACEHOLDER.findall(text)


def _texts() -> dict[str, str]:
    return {lang: (SPEC / f"{lang}.md").read_text(encoding="utf-8") for lang in LANGS}


def test_heading_structure_is_identical_across_editions():
    levels = {lang: _heading_levels(text) for lang, text in _texts().items()}
    en = levels["en"]
    for lang in ("ko", "zh"):
        assert levels[lang] == en, (
            f"{lang}.md's heading levels (count and depth, in order) differ from "
            f"en.md -- a heading was added, removed, or re-leveled in only one "
            f"edition"
        )


def test_table_placeholders_match_byte_for_byte_across_editions():
    phs = {lang: _placeholders(text) for lang, text in _texts().items()}
    en = phs["en"]
    assert en, "en.md has no {{table:...}} placeholders -- extraction pattern broke"
    for lang in ("ko", "zh"):
        assert phs[lang] == en, (
            f"{lang}.md's {{{{table:...}}}} placeholders differ from en.md's, "
            f"in content or order -- the three editions must expand to the same "
            f"tables in the same places"
        )
