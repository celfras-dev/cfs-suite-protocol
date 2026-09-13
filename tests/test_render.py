import json
from pathlib import Path

import pytest

from tools import render

GEN = Path("spec/_generated")


@pytest.fixture
def gen():
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in GEN.glob("*.json")}


def test_placeholder_becomes_a_table(gen):
    html = render.render_page("en", "# T\n\n{{table:opcodes:core}}\n", gen, for_print=False)
    assert "<table" in html
    assert "CMD_PING" in html
    assert "{{table:" not in html


def test_group_filter_excludes_other_groups(gen):
    core_names = {c["name"] for c in gen["opcodes"]["commands"] if c["group"] == "core"}
    tuning_names = {c["name"] for c in gen["opcodes"]["commands"] if c["group"] == "tuning"}
    assert core_names and tuning_names and core_names.isdisjoint(tuning_names)

    core_html = render.render_page("en", "{{table:opcodes:core}}", gen, for_print=False)
    tuning_html = render.render_page("en", "{{table:opcodes:tuning}}", gen, for_print=False)

    assert core_html != tuning_html
    for name in core_names:
        assert name in core_html
        assert name not in tuning_html
    for name in tuning_names:
        assert name in tuning_html
        assert name not in core_html


def test_unknown_placeholder_raises(gen):
    with pytest.raises(render.UnknownTable):
        render.render_page("en", "{{table:nope}}", gen, for_print=False)


@pytest.mark.parametrize(
    "malformed",
    [
        "{{table:opcodes:CORE}}",
        "{{table:opcodes-core}}",
        "{{ table:opcodes:core }}",
        "{{table:par16}}",
    ],
)
def test_malformed_placeholder_raises_not_ships_as_text(gen, malformed):
    with pytest.raises(render.UnknownTable):
        render.render_page("en", malformed, gen, for_print=False)


def test_placeholder_inside_fenced_code_block_is_left_literal(gen):
    md = "# T\n\n```\nUse {{table:opcodes:core}} to embed a table.\n```\n"
    html = render.render_page("en", md, gen, for_print=False)
    assert "{{table:opcodes:core}}" in html
    assert "<table" not in html


def test_language_font_stack_is_applied(gen):
    zh = render.render_page("zh", "# T", gen, for_print=True)
    assert "Microsoft YaHei" in zh
    ko = render.render_page("ko", "# T", gen, for_print=True)
    assert "Malgun Gothic" in ko
    assert "Microsoft YaHei" not in ko.split("</style>")[0]


def test_version_reaches_the_page(gen):
    html = render.render_page("en", "# T", gen, for_print=True)
    assert "3.1.0" in html


def test_ver_selectors_table(gen):
    html = render.render_page("en", "{{table:ver_selectors}}", gen, for_print=False)
    assert "VER_SEL_FW" in html
    assert "VER_SEL_CMD_SET" in html
    assert "0x00" in html
    assert "0x01" in html


def test_log_fields_table(gen):
    html = render.render_page("en", "{{table:log_fields}}", gen, for_print=False)
    assert "LOG_FIELD_VDD" in html
    assert "LOG_FIELD_RAT" in html
    assert "0x40" in html


def test_burst_limits_table(gen):
    html = render.render_page("en", "{{table:burst_limits}}", gen, for_print=False)
    assert "BURST_PERIOD_MS_MAX" in html
    assert "1000" in html
    assert "BURST_MAX_FIELDS" in html
    assert "16" in html


def test_no_notes_suffix_drops_the_note_column(gen):
    """Job 4: an explicit call-site suffix must drop the Notes/Meaning
    column entirely -- for a kind with no group/width argument (the suffix
    lands in the placeholder's second segment) and for one that also takes
    a real argument (the suffix then needs a third segment)."""
    with_notes = render.render_page("en", "{{table:op_modes}}", gen, for_print=False)
    without_notes = render.render_page("en", "{{table:op_modes:no_notes}}", gen, for_print=False)
    assert "Meaning" in with_notes
    assert "Meaning" not in without_notes
    # The identifiers themselves must still be there -- only the note text
    # (and its header) is gone, not the whole table.
    assert "OPMODE_ISP" in without_notes
    # OPMODE_ISP's real note names an FSM state and a driver function --
    # exactly the product-internal detail no_notes exists to drop.
    assert "ST_ISP_MODE" in with_notes
    assert "ST_ISP_MODE" not in without_notes

    with_notes_grp = render.render_page("en", "{{table:opcodes:core}}", gen, for_print=False)
    without_notes_grp = render.render_page(
        "en", "{{table:opcodes:core:no_notes}}", gen, for_print=False
    )
    assert "Notes" in with_notes_grp
    assert "Notes" not in without_notes_grp
    assert "CMD_PING" in without_notes_grp


def test_no_notes_typo_still_raises_unknown_table(gen):
    """The malformed-placeholder guard must keep working for the new
    syntax: a misspelled modifier is a call-site typo, not silent text."""
    with pytest.raises(render.UnknownTable):
        render.render_page("en", "{{table:op_modes:no_note}}", gen, for_print=False)
    with pytest.raises(render.UnknownTable):
        render.render_page("en", "{{table:opcodes:core:no_note}}", gen, for_print=False)
