"""Appendix C -- the 0xC0+ band the bridge answers itself.

A DUT never sees these: the bridge answers >= 0xC0 and forwards everything
below it untouched. They are in the standard so a product does not claim an
opcode the transport layer has already taken.
"""
from __future__ import annotations

import re

from . import sources

_SRC = ("CFS-SUITE-BRIDGE", "pc_app/cfsbridge/commands.py")
# `\s` includes '\n', so a bare `\s*` before the optional trailing comment
# would cross the line break and pick up a comment that belongs to the
# *next* line (a following opcode's leading comment, or a section-header
# comment) rather than a same-line trailing comment. Restricted to
# same-line whitespace ([ \t]) throughout so a note is only ever what
# trails the assignment on its own line.
_RE = re.compile(
    r"^(CMD_[A-Z0-9_]+)[ \t]*=[ \t]*0x([0-9A-Fa-f]{2})[ \t]*(?:#[ \t]*(.*))?$",
    re.M,
)

BAND_BASE = 0xC0


def extract() -> list[dict]:
    text = sources.read_committed(*_SRC)
    out = []
    for name, hexid, note in _RE.findall(text):
        cmd_id = int(hexid, 16)
        if cmd_id < BAND_BASE:
            continue
        out.append({"id": cmd_id, "name": name, "note": (note or "").strip()})
    out.sort(key=lambda c: c["id"])
    return out
