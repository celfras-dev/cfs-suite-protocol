import json
import re

from tools.extract import varpar


def forbidden_values() -> set:
    """Every value the product bakes in, taken from the source rather than a
    hand-written list. A hand-written one was already wrong once: it missed
    CHG_TIMEOUT_TH (600) and LONG_PUFF_TH (10000)."""
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
    # specific known-present values rather than a count -- a count is exactly
    # the kind of fact that goes stale (see the hand-written list this
    # replaced).
    values = forbidden_values()
    assert 350 in values      # DRY_PUFF_ABS_TEMP_TH
    assert 600 in values      # CHG_TIMEOUT_TH


def test_public_json_contains_no_forbidden_number():
    blob = json.dumps(varpar.extract(internal=False))
    for n in forbidden_values():
        assert not re.search(rf'(?<![\d.]){n}(?![\d.])', blob), \
            f"{n} leaked into the public appendix"


def test_internal_carries_defaults():
    d = varpar.extract(internal=True)
    p16 = {e["id"]: e for e in d["par"]["par16"]}
    assert p16[14]["default"] == 350
    assert p16[4]["default"] == 3400


def test_readonly_flag_survives():
    d = varpar.extract(internal=False)
    p16 = {e["id"]: e for e in d["par"]["par16"]}
    assert p16[0]["access"] == "ro"      # VDD (ro)
    assert p16[3]["access"] == "rw"      # LED_BREATH_PERIOD_MS


def test_var_slots_are_read_only_view():
    d = varpar.extract(internal=False)
    names = {e["name"] for e in d["var"]["var8"]}
    assert "EXT_CTRL_STATUS" in names
