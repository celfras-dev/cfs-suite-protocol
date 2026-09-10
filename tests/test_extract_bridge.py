from tools.extract import bridge


def test_bridge_band_commands():
    by_id = {c["id"]: c["name"] for c in bridge.extract()}
    assert by_id[0xC0] == "CMD_B_PING"
    assert by_id[0xC1] == "CMD_B_INFO"
    assert by_id[0xC7] == "CMD_B_GET_VERSION"


def test_every_entry_is_in_the_reserved_band():
    for c in bridge.extract():
        assert c["id"] >= 0xC0, f"{c['name']} is below the 0xC0 bridge band"


def test_reserved_but_unimplemented_is_marked():
    caps = next(c for c in bridge.extract() if c["id"] == 0xC2)
    assert "reserved" in caps["note"].lower()
