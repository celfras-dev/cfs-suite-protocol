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
    assert "2.11.0" in html
