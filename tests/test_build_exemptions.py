"""Job 3's hard part: BURST_PERIOD_MS_MAX (1000) collides, as a bare number,
with LED_BREATH_PERIOD_MS's product default (also 1000) -- the leak gate in
tools/build.py matches numbers, not what they mean. PROTOCOL_VALUE_EXEMPTIONS
names the (value, constant) pairs that are allowed through for that reason,
and this file proves the exemption is checked against real firmware source
rather than merely asserted in a comment.
"""
from __future__ import annotations

import pytest

from tools import build


def test_the_collision_is_real():
    """Establishes the premise: 1000 really is both a forbidden product
    default and the value build.PROTOCOL_VALUE_EXEMPTIONS excuses. If this
    ever stops being true the rest of this file is testing a fiction."""
    assert 1000 in build.forbidden_public_values()
    assert 1000 in build.exempted_public_values()


def test_leak_gate_values_excludes_exempted_numbers():
    """The gate a build actually runs must be forbidden minus exempted --
    never forbidden_public_values() bare, which still legitimately includes
    1000 (it IS a real product default; it just also has a legitimate
    protocol meaning)."""
    gate = build.leak_gate_values()
    assert 1000 not in gate
    assert 1000 in build.forbidden_public_values()
    # Nothing else got swept up by accident.
    assert gate == build.forbidden_public_values() - {1000}


def test_burst_limits_table_would_have_tripped_the_bare_gate():
    """Proves the exemption is load-bearing, not decorative: render the
    actual Job 3 placeholder and confirm the forbidden number really does
    appear in the output the leak gate scans -- so leak_gate_values(), not
    forbidden_public_values(), is what test_public_leak.py must use."""
    from tools import render
    from tools.extract import opcodes

    gen = {"opcodes": {"burst_limits": opcodes.burst_limits()}}
    html = render.expand_tables("{{table:burst_limits}}", gen)
    assert "1000" in html

    # With the bare (un-exempted) forbidden set, this render would fail a
    # leak scan; with the gate value set, it must pass.
    import re
    bare_hit = any(
        re.search(rf"(?<![\d.]){v}(?![\d.])", html)
        for v in build.forbidden_public_values()
    )
    gate_hit = any(
        re.search(rf"(?<![\d.]){v}(?![\d.])", html)
        for v in build.leak_gate_values()
    )
    assert bare_hit, "expected the bare forbidden set to flag this render"
    assert not gate_hit, "the gate value set must not flag an exempted number"


def test_verify_protocol_value_exemptions_passes_against_real_source():
    """The exemption is verified, not merely asserted: this reads
    app_proto.h at HEAD (through the same extractor the document build
    uses) and must find BURST_PERIOD_MS_MAX == 1000 for real."""
    build.verify_protocol_value_exemptions()  # must not raise


def test_stale_constant_name_is_caught(monkeypatch):
    """An invented/renamed constant must break verification, not pass
    silently -- proving the check actually looks, rather than trusting the
    comment next to PROTOCOL_VALUE_EXEMPTIONS."""
    monkeypatch.setattr(
        build, "PROTOCOL_VALUE_EXEMPTIONS",
        ({"value": 1000, "constant": "BURST_PERIOD_MS_MAX_TYPO"},),
    )
    with pytest.raises(Exception):
        build.verify_protocol_value_exemptions()


def test_stale_value_is_caught(monkeypatch):
    """A real constant name but the wrong value (e.g. the firmware bumped
    it and nobody updated the exemption) must also break verification.

    Uses an arbitrary wrong value (4242, deliberately not 1000 -- and
    deliberately not any real product default either, so this line stays
    clean under tests/test_tracked_source_leak.py's tracked-file scan;
    the point of this test is only that it disagrees with the real value,
    not what it is)."""
    monkeypatch.setattr(
        build, "PROTOCOL_VALUE_EXEMPTIONS",
        ({"value": 4242, "constant": "BURST_PERIOD_MS_MAX"},),
    )
    with pytest.raises(Exception):
        build.verify_protocol_value_exemptions()


def test_exemptions_list_stays_minimal():
    """Job 3 needs exactly one exemption. Growing this list is a real
    decision (each entry widens the gate for that number everywhere in the
    document), so pin the count -- a future addition must edit this test
    deliberately, not land as a side effect."""
    assert len(build.PROTOCOL_VALUE_EXEMPTIONS) == 1
