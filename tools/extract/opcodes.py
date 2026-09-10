"""Pull the opcode table out of app_proto.h.

The table is the part of the protocol document that went stale twice
(2.10.0 and 2.11.0), and it is mechanically derivable. Prose is written by
hand; tables are generated, so all three language editions share one.
"""
from __future__ import annotations

import re

from . import sources

_HEADER = ("CFS-ECIG-SUITE/FW", "App/Inc/app_proto.h")

# CMD_SET_VERSION_* are #defines in the same file and are not commands. They
# are also decimal (no "0x" prefix), so the 0x-requiring pattern below would
# skip them anyway; the lookahead is kept as the explicit, readable guard.
_CMD_RE = re.compile(
    r"^\s*#define\s+(CMD_(?!SET_VERSION_)[A-Z0-9_]+)\s+0x([0-9A-Fa-f]{2})u?[ \t]*(?://\s*(.*))?$",
    re.M,
)
_ERR_RE = re.compile(
    r"^\s*#define\s+(ERR_[A-Z_]+)\s+0x([0-9A-Fa-f]{2})u?[ \t]*(?://\s*(.*))?$", re.M
)
_MODE_RE = re.compile(
    r"^\s*#define\s+(OPMODE_[A-Z_]+)\s+0x([0-9A-Fa-f]{2})u?[ \t]*(?://\s*(.*))?$", re.M
)
# VER_SEL_* (CMD_GET_VERSION's [sel u8] selectors) and LOG_FIELD_* (the
# CMD_LOG_BURST_START fields_mask bits) are standard values in the same
# shared block as the opcodes above -- see app_proto.h's own comment there.
# Same same-line comment discipline as _CMD_RE/_ERR_RE/_MODE_RE: the gap
# before the trailing comment is `[ \t]*`, never `\s*`, so a comment-less
# #define cannot absorb a stray `//` line meant for the next one.
_VER_SEL_RE = re.compile(
    r"^\s*#define\s+(VER_SEL_[A-Z0-9_]+)\s+0x([0-9A-Fa-f]{2})u?[ \t]*(?://\s*(.*))?$",
    re.M,
)
_LOG_FIELD_RE = re.compile(
    r"^\s*#define\s+(LOG_FIELD_[A-Z0-9_]+)\s+0x([0-9A-Fa-f]{2})u?[ \t]*(?://\s*(.*))?$",
    re.M,
)
# The burst period/duration/field-count bounds sit in the same shared block
# and are plain decimal (no "0x" prefix), unlike everything else in this
# module -- hence the separate `(\d+)` capture rather than reusing the hex
# group above.
_BURST_LIMIT_RE = re.compile(
    r"^\s*#define\s+(BURST_[A-Z0-9_]+)\s+(\d+)u?[ \t]*(?://\s*(.*))?$", re.M
)

_GROUPS = [
    (0x01, 0x0F, "core"),
    (0x10, 0x1F, "device"),
    (0x20, 0x2F, "register"),
    (0x30, 0x3F, "log"),
    (0x40, 0x4F, "burst"),
    (0x50, 0x5F, "var_par"),
    (0x60, 0x6F, "display"),
    (0x70, 0x7F, "tuning"),
    (0xC0, 0xFF, "bridge"),
]


def _group_for(cmd_id: int) -> str:
    for lo, hi, name in _GROUPS:
        if lo <= cmd_id <= hi:
            return name
    return "unassigned"


def _split_shapes(comment: str) -> tuple[str, str, str]:
    """Split '// [prefix] req [...] resp [...] -- note' into its three parts.

    Most comments are 'req [...] resp [...]', optionally followed by a
    '-- note'. A few (CMD_LOG_FRAME, CMD_LOG_BURST_FRAME,
    CMD_TUNING_REPORT_FRAME) are fw->host-only frames with no 'req' keyword
    at all -- they open with a parenthetical like '(fw->host only, seq=0)'
    instead. That leading text, and any comment with neither keyword, is
    kept as note rather than silently dropped.
    """
    if not comment:
        return "", "", ""
    comment, _, dash_note = comment.partition("--")
    req_m = re.search(r"\breq\b(.*?)(?=\bresp\b|$)", comment, re.S)
    resp_m = re.search(r"\bresp\b(.*)$", comment, re.S)
    req = req_m.group(1).strip() if req_m else ""
    resp = resp_m.group(1).strip() if resp_m else ""
    prefix_end = min((m.start() for m in (req_m, resp_m) if m), default=len(comment))
    prefix = comment[:prefix_end].strip()
    note = " ".join(part for part in (prefix, dash_note.strip()) if part)
    return req, resp, note


def _text() -> str:
    return sources.read_committed(*_HEADER)


def extract() -> list[dict]:
    out = []
    for name, hexid, comment in _CMD_RE.findall(_text()):
        cmd_id = int(hexid, 16)
        req, resp, note = _split_shapes((comment or "").strip())
        out.append({
            "id": cmd_id, "name": name, "req": req, "resp": resp,
            "note": note, "group": _group_for(cmd_id),
        })
    out.sort(key=lambda c: c["id"])
    return out


def errors() -> list[dict]:
    return sorted(
        ({"code": int(h, 16), "name": n, "note": (c or "").strip()}
         for n, h, c in _ERR_RE.findall(_text())),
        key=lambda e: e["code"],
    )


def op_modes() -> list[dict]:
    return sorted(
        ({"value": int(h, 16), "name": n, "note": (c or "").strip()}
         for n, h, c in _MODE_RE.findall(_text())),
        key=lambda m: m["value"],
    )


def ver_selectors() -> list[dict]:
    """Job 1: the CMD_GET_VERSION [sel u8] selector values -- standard,
    not product, values (app_proto.h's own comment block says this region
    is shared byte-for-byte across projects)."""
    return sorted(
        ({"value": int(h, 16), "name": n, "note": (c or "").strip()}
         for n, h, c in _VER_SEL_RE.findall(_text())),
        key=lambda s: s["value"],
    )


def log_fields() -> list[dict]:
    """Job 2: the CMD_LOG_BURST_START fields_mask bit assignments. Which
    bits a given product has wired to a real reading is project vocabulary
    and stays out of this table; the bit assignments themselves are
    standard."""
    return sorted(
        ({"bit": int(h, 16), "name": n, "note": (c or "").strip()}
         for n, h, c in _LOG_FIELD_RE.findall(_text())),
        key=lambda f: f["bit"],
    )


def burst_limits() -> list[dict]:
    """Job 3: BURST_PERIOD_MS_MIN/MAX, BURST_DURATION_MS_MIN/MAX and
    BURST_MAX_FIELDS -- the CMD_LOG_BURST_START argument bounds. Matched
    generically on the BURST_ prefix (mechanical, not a hand-picked list),
    which also happens to sweep up BURST_DURATION_MS_INFINITE from the same
    block; that is harmless, it is just as much a standard constant as the
    other five.

    Sorted by name (there is no natural id/value ordering across these
    unrelated constants, unlike the hex-keyed tables above)."""
    return sorted(
        ({"name": n, "value": int(v), "note": (c or "").strip()}
         for n, v, c in _BURST_LIMIT_RE.findall(_text())),
        key=lambda b: b["name"],
    )
