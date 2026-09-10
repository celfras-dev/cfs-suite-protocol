from tools.extract import opcodes


def test_core_commands_present():
    by_id = {c["id"]: c["name"] for c in opcodes.extract()}
    assert by_id[0x01] == "CMD_PING"
    assert by_id[0x05] == "CMD_GET_VERSION"
    assert by_id[0x40] == "CMD_LOG_BURST_START"
    assert by_id[0x5B] == "CMD_PAR32_GET"
    assert by_id[0x74] == "CMD_GET_TUNING_PAR"


def test_version_define_is_not_an_opcode():
    """CMD_SET_VERSION_MAJOR sits among the #defines and must not be
    mistaken for a command."""
    names = {c["name"] for c in opcodes.extract()}
    assert not any(n.startswith("CMD_SET_VERSION") for n in names)


def test_request_and_response_shapes_captured():
    ping = next(c for c in opcodes.extract() if c["id"] == 0x01)
    assert "PONG" in ping["resp"]
    burst = next(c for c in opcodes.extract() if c["id"] == 0x40)
    assert "fields_mask" in burst["req"]


def test_error_codes():
    by_code = {e["code"]: e["name"] for e in opcodes.errors()}
    assert by_code == {
        0x00: "ERR_OK", 0x01: "ERR_BAD_LEN", 0x02: "ERR_BAD_CRC",
        0x03: "ERR_BAD_ARGS", 0x04: "ERR_NOT_READY", 0x05: "ERR_UNKNOWN",
    }


def test_op_modes():
    by_val = {m["value"]: m["name"] for m in opcodes.op_modes()}
    assert by_val[0x00] == "OPMODE_ISP"
    assert by_val[0x01] == "OPMODE_NORMAL"
    assert by_val[0x02] == "OPMODE_DEBUG"
    assert by_val[0x04] == "OPMODE_TEST"
