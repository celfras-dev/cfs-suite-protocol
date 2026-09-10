import json
import re

from tools.extract import varpar


def forbidden_values() -> set:
    """Every value the product bakes in, taken from the source rather than a
    hand-written list. A hand-written one was already wrong once: it missed
    CHG_TIMEOUT_TH and LONG_PUFF_TH. (Not naming their actual values here --
    see tools/build.py's forbidden_public_values(), which makes the same
    point the same way, for why.)"""
    return {r["default"]
            for rows in varpar.extract(internal=True)["par"].values()
            for r in rows if "default" in r}


def test_public_has_ids_names_units():
    d = varpar.extract(internal=False)
    p16 = {e["id"]: e for e in d["par"]["par16"]}
    assert p16[14]["name"] == "DRY_PUFF_ABS_TEMP_TH"
    assert p16[14]["unit"] == "degC"
    assert p16[4]["name"] == "UVLO_HEAT_INIT_TH"


def test_public_carries_no_default_values():
    d = varpar.extract(internal=False)
    for width in ("par8", "par16", "par32"):
        for e in d["par"][width]:
            assert "default" not in e, f"{e['name']} leaked a default"


def test_forbidden_values_found_real_defaults():
    # Guards against the derivation silently finding nothing (an empty or
    # trivially small set would make the leak test below vacuous). Check for
    # two specific known-present fields rather than a count -- a count is
    # exactly the kind of fact that goes stale (see the hand-written list
    # this replaced). Looked up by name at runtime, not written as a
    # literal here, so this file does not itself become a place a real
    # product default lives in text (see tests/test_tracked_source_leak.py).
    d = varpar.extract(internal=True)
    by_name = {e["name"]: e for rows in d["par"].values() for e in rows}
    values = forbidden_values()
    assert by_name["DRY_PUFF_ABS_TEMP_TH"]["default"] in values
    assert by_name["CHG_TIMEOUT_TH"]["default"] in values


def test_public_json_contains_no_forbidden_number():
    blob = json.dumps(varpar.extract(internal=False))
    for n in forbidden_values():
        assert not re.search(rf'(?<![\d.]){n}(?![\d.])', blob), \
            f"{n} leaked into the public appendix"


def test_internal_carries_defaults():
    # Cross-checked against the raw source directly rather than against a
    # literal written here, so this test does not itself carry a real
    # product default as text (see tests/test_tracked_source_leak.py).
    from tools.extract import sources

    raw = json.loads(sources.read_committed(
        "CFS-ECIG-SUITE/pc_app", "conf/par_map.json"))
    d = varpar.extract(internal=True)
    p16 = {e["id"]: e for e in d["par"]["par16"]}
    assert p16[14]["default"] == raw["par16"]["14"]["default"]
    assert p16[4]["default"] == raw["par16"]["4"]["default"]


def test_readonly_flag_survives():
    d = varpar.extract(internal=False)
    p16 = {e["id"]: e for e in d["par"]["par16"]}
    assert p16[0]["access"] == "ro"      # VDD (ro)
    assert p16[3]["access"] == "rw"      # LED_BREATH_PERIOD_MS


def test_var_slots_are_read_only_view():
    d = varpar.extract(internal=False)
    names = {e["name"] for e in d["var"]["var8"]}
    assert "EXT_CTRL_STATUS" in names
