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


def test_comment_does_not_cross_line_into_next_entry():
    # Regression for the `\s*` -> `[ \t]*` fix: `\s*` before the trailing
    # comment group crosses newlines, so an entry with no same-line
    # comment would silently inherit whatever comment text follows it in
    # the source -- a following opcode's leading block comment, or a
    # section-header comment. Each of these five has no same-line `#` in
    # commands.py, so its note must come back empty:
    #
    #   CMD_B_GET_SNAPSHOT = 0xC4                    (no trailing comment;
    #       next line is CMD_SET_SWD_SPEED's leading comment block)
    #   CMD_SET_SWD_SPEED = 0xC5                     (no trailing comment;
    #       next line is CMD_SET_TARGET's leading comment block)
    #   CMD_AP_WRITE = 0xDB                          (no trailing comment;
    #       next line is the "# 0xE0  core control" section header)
    #   CMD_CORE_RUN_DETACH = 0xE4                   (no trailing comment;
    #       next line is the "# 0xE8  bridge self-update" section header)
    #   CMD_FLASH_READ = 0xF3                        (no trailing comment;
    #       next lines are CMD_FLASH_READ_EX's leading comment block)
    by_id = {c["id"]: c for c in bridge.extract()}
    for cmd_id, name in (
        (0xC4, "CMD_B_GET_SNAPSHOT"),
        (0xC5, "CMD_SET_SWD_SPEED"),
        (0xDB, "CMD_AP_WRITE"),
        (0xE4, "CMD_CORE_RUN_DETACH"),
        (0xF3, "CMD_FLASH_READ"),
    ):
        entry = by_id[cmd_id]
        assert entry["name"] == name
        assert entry["note"] == "", (
            f"{name} (0x{cmd_id:02X}) picked up a note that isn't on its "
            f"own line: {entry['note']!r}"
        )

    # Entries that DO have a same-line trailing comment must keep it --
    # otherwise a parser that just drops every note would pass the above
    # for the wrong reason.
    for cmd_id, name, snippet in (
        (0xC2, "CMD_B_GET_CAPS", "reserved"),
        (0xCC, "CMD_TGT_NRST", "assert u8"),
        (0xF4, "CMD_FLASH_MASS_ERASE", "reserved"),
        (0xF5, "CMD_FLASH_READ_EX", "addr u32"),
    ):
        entry = by_id[cmd_id]
        assert entry["name"] == name
        assert snippet in entry["note"], (
            f"{name} (0x{cmd_id:02X}) lost its same-line comment: "
            f"{entry['note']!r}"
        )
