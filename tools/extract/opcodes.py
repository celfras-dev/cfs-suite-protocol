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
    r"^\s*#define\s+(CMD_(?!SET_VERSION_)[A-Z0-9_]+)\s+0x([0-9A-Fa-f]{2})u?\s*(?://\s*(.*))?$",
    re.M,
)
_ERR_RE = re.compile(
    r"^\s*#define\s+(ERR_[A-Z_]+)\s+0x([0-9A-Fa-f]{2})u?\s*(?://\s*(.*))?$", re.M
)
_MODE_RE = re.compile(
    r"^\s*#define\s+(OPMODE_[A-Z_]+)\s+0x([0-9A-Fa-f]{2})u?\s*(?://\s*(.*))?$", re.M
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
