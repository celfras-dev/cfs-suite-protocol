"""Derive the CMD_SET version instead of declaring one.

This repository holds no copy of the number. It reads every copy that the
product repos' own tests can each see only part of, and refuses to build
when they disagree -- which makes the document build the only place all of
them are compared at once.

Do not write down how many copies there are, here or anywhere else in this
module (comments, test names, assertions). Every written total of these
copies has been wrong before -- the product repos' own tests say so in
their own comments -- and this project has now got it wrong repeatedly too,
most recently by missing two board.txt copies entirely (see below). Assert
on the *set* of sources, never on its size.
"""
from __future__ import annotations

import json
import re

from . import sources

Version = tuple[int, int, int]

# Every real CMD_SET_VERSION copy this build reads and compares, across
# both product repos and every syntax currently in use for it (C
# #define trio, Python tuple, JSON key, plain-text "key = value" line).
# The authoritative list of copies -- including which similarly-named
# things are DELIBERATELY NOT copies, such as the bridge boards'
# BOOT_CMD_SET_VERSION_* (the bootloaders' own, separately-frozen number)
# -- is the header comment above CMD_SET_VERSION in CFS-SUITE-BRIDGE's
# pc_app/cfsbridge/commands.py. Read that before changing this list; it is
# the record of what belongs here and why, not this file's short version
# of it.
#
# Neither product-repo test sees every copy at once -- this build does.
# tests/test_extract_version.py::test_no_undeclared_copy_appeared is the
# guard against a copy going unnoticed here: it greps the three product
# repos for anything that looks like a CMD_SET_VERSION-ish declaration and
# fails if the match set changes. That guard was written to catch exactly
# this failure mode and still missed the two fw/brd0*/board.txt copies
# below, because its pattern enumerated known syntaxes (a C #define, a
# Python tuple, a JSON key) instead of describing what a declaration looks
# like independent of language -- a `key = value` text line matched none
# of them. The fixed pattern and the reasoning for it are in that test's
# own comment; don't re-narrow it back to an enumeration.
#
# Another site declares the same C macros: CFS-SUITE-BRIDGE's
# fw_dut/ref_cwm2032_working_uart_swd_together/Project/Inc/app_proto_defs.h.
# It is deliberately NOT listed here -- that tree is a frozen reference
# snapshot kept for comparison, not a product, and requiring it to agree
# would break the build the first time someone bumps a real copy and
# correctly leaves the reference alone.
_C_HEADERS = [
    ("CFS-ECIG-SUITE/FW", "App/Inc/app_proto.h"),
    ("CFS-SUITE-BRIDGE", "fw/brd01/App/Inc/app_version.h"),
    ("CFS-SUITE-BRIDGE", "fw/brd02/App/Inc/app_version.h"),
    ("CFS-SUITE-BRIDGE", "fw_dut/cwm2032/App/Inc/app_proto.h"),
    ("CFS-SUITE-BRIDGE", "fw_dut/cwm1016/App/Inc/app_proto.h"),
    ("CFS-SUITE-BRIDGE", "fw_dut/cwm0508/App/Inc/app_proto.h"),
    ("CFS-SUITE-BRIDGE", "fw_dut/cwm30c8/App/Inc/app_proto.h"),
    ("CFS-SUITE-BRIDGE", "fw_dut/cwm25c8/App/Inc/app_proto.h"),
]
_ECIG_JSON = ("CFS-ECIG-SUITE/pc_app", "conf/cmd_set.json")
_BRIDGE_PY = ("CFS-SUITE-BRIDGE", "pc_app/cfsbridge/commands.py")

# The two board.txt copies (added 2026-09-10 -- see the module and
# _C_HEADERS comments above for why they were missed for so long). Each
# carries one "cmd_set             = M.m.p" line; brd02's file also has a
# commented-out line that mentions "cmd_set" in prose (pointing a reader at
# the header it was copied from) without an "=" on it, which _from_board_txt
# must not mistake for the real one.
_BOARD_TXT = [
    ("CFS-SUITE-BRIDGE", "fw/brd01/board.txt"),
    ("CFS-SUITE-BRIDGE", "fw/brd02/board.txt"),
]


class VersionMismatch(Exception):
    """The CMD_SET copies disagree; the document must not pick a winner."""


def as_string(v: Version) -> str:
    return "%d.%d.%d" % v


def _from_c_header(text: str) -> Version:
    out = []
    for part in ("MAJOR", "MINOR", "PATCH"):
        m = re.search(rf"^\s*#define\s+CMD_SET_VERSION_{part}\s+(\d+)", text, re.M)
        if not m:
            raise VersionMismatch(f"CMD_SET_VERSION_{part} not found in header")
        out.append(int(m.group(1)))
    return tuple(out)  # type: ignore[return-value]


def _from_cmd_set_json(text: str) -> Version:
    d = json.loads(text)["cmd_set_version"]
    return (int(d["major"]), int(d["minor"]), int(d["patch"]))


def _from_bridge_py(text: str) -> Version:
    m = re.search(r"^CMD_SET_VERSION\s*=\s*\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)", text, re.M)
    if not m:
        raise VersionMismatch("CMD_SET_VERSION tuple not found in commands.py")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _from_board_txt(text: str) -> Version:
    # Anchored the same way the other parsers are: `^\s*` allows leading
    # indentation but nothing else, so brd02's commented-out mention (which
    # starts with "#") cannot match -- same-line discipline, not a comment
    # filter bolted on afterward.
    m = re.search(r"^\s*cmd_set\s*=\s*(\d+)\.(\d+)\.(\d+)\s*$", text, re.M)
    if not m:
        raise VersionMismatch("cmd_set = M.m.p line not found in board.txt")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _collect() -> dict[str, Version]:
    found = {
        "/".join(src): _from_c_header(sources.read_committed(*src))
        for src in _C_HEADERS
    }
    found["/".join(_ECIG_JSON)] = _from_cmd_set_json(sources.read_committed(*_ECIG_JSON))
    found["/".join(_BRIDGE_PY)] = _from_bridge_py(sources.read_committed(*_BRIDGE_PY))
    for src in _BOARD_TXT:
        found["/".join(src)] = _from_board_txt(sources.read_committed(*src))
    return found


def extract() -> Version:
    found = _collect()
    distinct = set(found.values())
    if len(distinct) != 1:
        lines = "\n".join(f"  {as_string(v)}  {k}" for k, v in sorted(found.items()))
        raise VersionMismatch(
            "CMD_SET copies disagree -- fix the product repos first:\n" + lines
        )
    return distinct.pop()
