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


def test_fw_host_only_frames_keep_leading_marker_in_note():
    """CMD_LOG_FRAME, CMD_LOG_BURST_FRAME and CMD_TUNING_REPORT_FRAME have no
    'req' keyword in their comment -- they open with a '(fw->host only...)'
    parenthetical instead. _split_shapes must preserve that fw->host marker
    in note (not silently drop it), report an empty req for them (there is
    no request -- these are unsolicited frames), and still get resp right."""
    by_id = {c["id"]: c for c in opcodes.extract()}

    log_frame = by_id[0x30]
    assert log_frame["req"] == ""
    assert "fw->host only" in log_frame["note"]
    assert log_frame["resp"] == '[OK][text bytes]'

    burst_frame = by_id[0x41]
    assert burst_frame["req"] == ""
    assert "fw->host only" in burst_frame["note"]
    assert "tick_ms u32" in burst_frame["resp"]

    tuning_report = by_id[0x71]
    assert tuning_report["req"] == ""
    assert "fw->host only" in tuning_report["note"]
    assert "tick_ms u32" in tuning_report["resp"]
    # The trailing '-- ...' note on this one must survive alongside the
    # leading fw->host marker, not replace it.
    assert "same shape family as CMD_LOG_BURST_FRAME" in tuning_report["note"]


def test_comment_does_not_bridge_across_a_newline_to_a_later_define(monkeypatch):
    """A #define with no trailing comment must not pick up a `//` comment
    that sits on its own line below it.

    Each opcode regex is `...0x([0-9A-Fa-f]{2})u?<gap>(?://\\s*(.*))?$`. If
    `<gap>` is `\\s*` (matches newlines), a comment-less #define can absorb a
    stray comment line that lies between it and the next #define -- and that
    stray line is exactly the kind of comment a header author writes to
    document the *next* opcode, not the one above it. `<gap>` must be
    `[ \\t]*` (same line only) so an uncommented #define always comes back
    empty, regardless of what text follows it on later lines.

    One synthetic header covers CMD, ERR and OPMODE in one shot, since
    `extract()`/`errors()`/`op_modes()` all read through the same `_text()`
    hook and the fix is the identical `\\s*` -> `[ \\t]*` swap in all three
    regexes.
    """
    snippet = (
        "#define CMD_A 0x01u\n"
        "// req [len u8] resp [OK]\n"
        "#define CMD_B 0x02u  // req [own] resp [own]\n"
        "\n"
        "#define ERR_FOO 0x00u\n"
        "// note that belongs to ERR_BAR\n"
        "#define ERR_BAR 0x01u  // bar's own note\n"
        "\n"
        "#define OPMODE_FOO 0x00u\n"
        "// note that belongs to OPMODE_BAR\n"
        "#define OPMODE_BAR 0x01u  // bar's own note\n"
    )
    monkeypatch.setattr(opcodes, "_text", lambda: snippet)

    by_id = {c["id"]: c for c in opcodes.extract()}
    assert by_id[0x01]["req"] == ""
    assert by_id[0x01]["resp"] == ""
    assert by_id[0x01]["note"] == ""
    assert by_id[0x02]["req"] == "[own]"
    assert by_id[0x02]["resp"] == "[own]"

    by_code = {e["code"]: e for e in opcodes.errors()}
    assert by_code[0x00]["note"] == ""
    assert by_code[0x01]["note"] == "bar's own note"

    by_val = {m["value"]: m for m in opcodes.op_modes()}
    assert by_val[0x00]["note"] == ""
    assert by_val[0x01]["note"] == "bar's own note"


def test_normal_req_resp_comments_note_is_unaffected():
    """The fw->host-only fix must not leak spurious leading text into the
    note of an ordinary 'req ... resp ...' comment, whether or not it has
    a trailing '-- note'."""
    by_id = {c["id"]: c for c in opcodes.extract()}

    ping = by_id[0x01]  # no trailing '-- note' at all
    assert ping["note"] == ""

    set_tuning_par = by_id[0x73]  # trailing '-- no session required'
    assert set_tuning_par["note"] == "no session required"
