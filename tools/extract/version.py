"""Derive the CMD_SET version instead of declaring one.

This repository holds no copy of the number. It reads the eight copies that
the product repos' own tests can each see only part of, and refuses to build
when they disagree -- which makes the document build the only place all
eight are compared at once.
"""
from __future__ import annotations

import json
import re

from . import sources

Version = tuple[int, int, int]

# The full set of CMD_SET_VERSION_MAJOR/MINOR/PATCH C headers across both
# product repos. app_proto.h's own comment block names five of these (itself
# plus the two bridge fw/brd0*/app_version.h headers plus the two remaining
# fw_dut/* firmwares) and explicitly notes that the three fw_dut/* copies are
# ones the ECIG repo's own tests cannot hold; CFS-SUITE-BRIDGE's test holds
# those three plus its own two, but not the ECIG one. Neither product-repo
# test sees all eight at once -- this build does.
#
# A ninth site declares the same macros: CFS-SUITE-BRIDGE's
# fw_dut/ref_cwm2032_working_uart_swd_together/Project/Inc/app_proto_defs.h.
# It is deliberately NOT listed here -- that tree is a frozen reference
# snapshot kept for comparison, not a product, and requiring it to agree
# would break the build the first time someone bumps a real copy and
# correctly leaves the reference alone. See
# tests/test_extract_version.py::test_no_undeclared_copy_appeared, which
# greps all three product repos and fails if an undeclared site appears.
_C_HEADERS = [
    ("CFS-ECIG-SUITE/FW", "App/Inc/app_proto.h"),
    ("CFS-SUITE-BRIDGE", "fw/brd01/App/Inc/app_version.h"),
    ("CFS-SUITE-BRIDGE", "fw/brd02/App/Inc/app_version.h"),
    ("CFS-SUITE-BRIDGE", "fw_dut/cwm2032/App/Inc/app_proto.h"),
    ("CFS-SUITE-BRIDGE", "fw_dut/cwm1016/App/Inc/app_proto.h"),
    ("CFS-SUITE-BRIDGE", "fw_dut/cwm0508/App/Inc/app_proto.h"),
]
_ECIG_JSON = ("CFS-ECIG-SUITE/pc_app", "conf/cmd_set.json")
_BRIDGE_PY = ("CFS-SUITE-BRIDGE", "pc_app/cfsbridge/commands.py")


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


def _collect() -> dict[str, Version]:
    found = {
        "/".join(src): _from_c_header(sources.read_committed(*src))
        for src in _C_HEADERS
    }
    found["/".join(_ECIG_JSON)] = _from_cmd_set_json(sources.read_committed(*_ECIG_JSON))
    found["/".join(_BRIDGE_PY)] = _from_bridge_py(sources.read_committed(*_BRIDGE_PY))
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
