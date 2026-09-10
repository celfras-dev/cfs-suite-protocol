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


def test_ver_selectors():
    """Job 1: VER_SEL_FW/VER_SEL_CMD_SET are standard values (shared
    byte-for-byte across projects per app_proto.h's own comment block) that
    CMD_GET_VERSION's [sel u8] request needs, but nothing extracted them."""
    by_val = {s["value"]: s["name"] for s in opcodes.ver_selectors()}
    assert by_val == {0x00: "VER_SEL_FW", 0x01: "VER_SEL_CMD_SET"}
    fw = next(s for s in opcodes.ver_selectors() if s["name"] == "VER_SEL_FW")
    assert "firmware build" in fw["note"]


def test_log_fields():
    """Job 2: LOG_FIELD_* are the fields_mask bits CMD_LOG_BURST_START's
    request needs to build, and are standard bit assignments even though
    which ones a given product wires up is product-specific."""
    by_bit = {f["bit"]: f["name"] for f in opcodes.log_fields()}
    assert by_bit == {
        0x01: "LOG_FIELD_VDD", 0x02: "LOG_FIELD_VAT", 0x04: "LOG_FIELD_IAT",
        0x08: "LOG_FIELD_PWR", 0x10: "LOG_FIELD_DUTY", 0x20: "LOG_FIELD_PROT",
        0x40: "LOG_FIELD_RAT",
    }


def test_burst_limits():
    """Job 3: the burst period/duration/field-count bounds are standard
    constants in the same shared block as the LOG_FIELD_* bits."""
    by_name = {b["name"]: b["value"] for b in opcodes.burst_limits()}
    assert by_name["BURST_PERIOD_MS_MIN"] == 10
    assert by_name["BURST_PERIOD_MS_MAX"] == 1000
    assert by_name["BURST_DURATION_MS_MIN"] == 100
    assert by_name["BURST_DURATION_MS_MAX"] == 1000000
    assert by_name["BURST_MAX_FIELDS"] == 16


def test_ver_selectors_and_log_fields_share_the_newline_discipline(monkeypatch):
    """Same bug class as test_comment_does_not_bridge_across_a_newline_to_a_
    later_define above, for the two new regexes: a comment-less #define must
    not absorb a stray comment line from below it."""
    snippet = (
        "#define VER_SEL_A 0x00u\n"
        "// note that belongs to VER_SEL_B\n"
        "#define VER_SEL_B 0x01u  // b's own note\n"
        "\n"
        "#define LOG_FIELD_A 0x01u\n"
        "// note that belongs to LOG_FIELD_B\n"
        "#define LOG_FIELD_B 0x02u  // b's own note\n"
        "\n"
        "#define BURST_A 10u\n"
        "// note that belongs to BURST_B\n"
        "#define BURST_B 20u  // b's own note\n"
    )
    monkeypatch.setattr(opcodes, "_text", lambda: snippet)

    by_val = {s["value"]: s for s in opcodes.ver_selectors()}
    assert by_val[0x00]["note"] == ""
    assert by_val[0x01]["note"] == "b's own note"

    by_bit = {f["bit"]: f for f in opcodes.log_fields()}
    assert by_bit[0x01]["note"] == ""
    assert by_bit[0x02]["note"] == "b's own note"

    by_name = {b["name"]: b for b in opcodes.burst_limits()}
    assert by_name["BURST_A"]["note"] == ""
    assert by_name["BURST_B"]["note"] == "b's own note"
