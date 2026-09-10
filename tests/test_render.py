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
    html = render.render_page("en", "{{table:opcodes:core}}", gen, for_print=False)
    assert "CMD_PING" in html
    assert "CMD_GET_TUNING_PAR" not in html


def test_unknown_placeholder_raises(gen):
    with pytest.raises(render.UnknownTable):
        render.render_page("en", "{{table:nope}}", gen, for_print=False)


def test_language_font_stack_is_applied(gen):
    zh = render.render_page("zh", "# T", gen, for_print=True)
    assert "Microsoft YaHei" in zh
    ko = render.render_page("ko", "# T", gen, for_print=True)
    assert "Malgun Gothic" in ko
    assert "Microsoft YaHei" not in ko.split("</style>")[0]


def test_version_reaches_the_page(gen):
    html = render.render_page("en", "# T", gen, for_print=True)
    assert "2.11.0" in html
