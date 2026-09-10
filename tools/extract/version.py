"""Derive the CMD_SET version instead of declaring one.

This repository holds no copy of the number. It reads the three copies that
the product repos' own tests can each see only half of, and refuses to build
when they disagree -- which makes the document build the only place all
three are compared at once.
"""
from __future__ import annotations

import json
import re

from . import sources

Version = tuple[int, int, int]

_ECIG_HEADER = ("CFS-ECIG-SUITE/FW", "App/Inc/app_proto.h")
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
    return {
        "/".join(_ECIG_HEADER): _from_c_header(sources.read_committed(*_ECIG_HEADER)),
        "/".join(_ECIG_JSON): _from_cmd_set_json(sources.read_committed(*_ECIG_JSON)),
        "/".join(_BRIDGE_PY): _from_bridge_py(sources.read_committed(*_BRIDGE_PY)),
    }


def extract() -> Version:
    found = _collect()
    distinct = set(found.values())
    if len(distinct) != 1:
        lines = "\n".join(f"  {as_string(v)}  {k}" for k, v in sorted(found.items()))
        raise VersionMismatch(
            "CMD_SET copies disagree -- fix the product repos first:\n" + lines
        )
    return distinct.pop()
