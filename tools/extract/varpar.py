"""Appendix A -- the ECIG var/par id maps.

Public editions carry ids, names, units and access only. The values a
product bakes in (dry-puff thresholds, protection limits) are product data,
not protocol: a standard defines what id 14 means, not that this product
writes 350 into it. min/max are dropped from both editions -- they are the
host GUI's spinbox limits, not part of the wire contract.
"""
from __future__ import annotations

import json

from . import sources

_VAR = ("CFS-ECIG-SUITE/pc_app", "conf/var_map.json")
_PAR = ("CFS-ECIG-SUITE/pc_app", "conf/par_map.json")

_WIDTHS = ("par8", "par16", "par32")


def _clean_name(raw: str) -> tuple[str, str]:
    """'VDD (ro)' -> ('VDD', 'ro'); anything else -> (name, 'rw')."""
    name = raw.strip()
    if name.endswith("(ro)"):
        return name[:-4].strip(), "ro"
    return name, "rw"


def _par(internal: bool) -> dict:
    doc = json.loads(sources.read_committed(*_PAR))
    out: dict[str, list] = {}
    for width in _WIDTHS:
        rows = []
        for sid, e in sorted(doc.get(width, {}).items(), key=lambda kv: int(kv[0])):
            name, access = _clean_name(e["name"])
            if e.get("readonly"):
                access = "ro"
            row = {"id": int(sid), "name": name,
                   "unit": e.get("unit", ""), "access": access}
            if internal and "default" in e:
                row["default"] = e["default"]
            rows.append(row)
        out[width] = rows
    return out


def _var() -> dict:
    doc = json.loads(sources.read_committed(*_VAR))
    out: dict[str, list] = {}
    for width in ("var8", "var16", "var32"):
        rows = []
        for sid, e in sorted(doc.get(width, {}).items(), key=lambda kv: int(kv[0])):
            name, _ = _clean_name(e["name"])
            rows.append({"id": int(sid), "name": name, "unit": e.get("unit", "")})
        out[width] = rows
    return out


def extract(internal: bool = False) -> dict:
    return {"var": _var(), "par": _par(internal)}
