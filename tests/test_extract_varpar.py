import json

from tools.extract import varpar

FORBIDDEN_IN_PUBLIC = [350, 3400, 2000, 8000, 300, 180000, 1000]


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


def test_public_json_contains_no_forbidden_number():
    blob = json.dumps(varpar.extract(internal=False))
    for n in FORBIDDEN_IN_PUBLIC:
        assert str(n) not in blob, f"{n} leaked into the public appendix"


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
