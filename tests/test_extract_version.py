import subprocess

import pytest
from tools.extract import sources, version


def test_extract_returns_current_cmd_set_version():
    assert version.extract() == (4, 1, 0)


def test_collect_sees_every_known_copy():
    """One source per known CMD_SET_VERSION copy -- named explicitly so
    dropping any of them (or silently merging two) fails this test."""
    expected_keys = {
        "CFS-ECIG-SUITE/FW/App/Inc/app_proto.h",
        "CFS-SUITE-BRIDGE/fw/brd01/App/Inc/app_version.h",
        "CFS-SUITE-BRIDGE/fw/brd02/App/Inc/app_version.h",
        "CFS-SUITE-BRIDGE/fw_dut/cwm2032/App/Inc/app_proto.h",
        "CFS-SUITE-BRIDGE/fw_dut/cwm1016/App/Inc/app_proto.h",
        "CFS-SUITE-BRIDGE/fw_dut/cwm0508/App/Inc/app_proto.h",
        "CFS-SUITE-BRIDGE/fw_dut/cwm30c8/App/Inc/app_proto.h",
        "CFS-SUITE-BRIDGE/fw_dut/cwm25c8/App/Inc/app_proto.h",
        "CFS-ECIG-SUITE/pc_app/conf/cmd_set.json",
        "CFS-SUITE-BRIDGE/pc_app/cfsbridge/commands.py",
        "CFS-SUITE-BRIDGE/fw/brd01/board.txt",
        "CFS-SUITE-BRIDGE/fw/brd02/board.txt",
    }
    assert set(version._collect().keys()) == expected_keys


def test_board_txt_wrong_value_fails_extract(monkeypatch):
    """A drifted board.txt must stop the build exactly like a drifted C
    header or JSON key does -- proves the two new _collect() entries are
    load-bearing, not decorative."""
    real = version._collect

    def fake():
        got = real()
        got["CFS-SUITE-BRIDGE/fw/brd02/board.txt"] = (2, 9, 0)
        return got

    monkeypatch.setattr(version, "_collect", fake)
    with pytest.raises(version.VersionMismatch) as e:
        version.extract()
    assert "2.9.0" in str(e.value)


def test_from_board_txt_parses_real_line_and_skips_commented_mention():
    # brd02's actual shape: a comment naming "cmd_set" in prose (no "="
    # on that line) above the real "cmd_set = M.m.p" line. The parser must
    # find the real one and not be fooled by the mention.
    text = (
        "# board.txt for brd02\n"
        "#   cmd_set      -> App/Inc/app_version.h\n"
        "board_id            = 0x02\n"
        "fw_version          = 3.0.3\n"
        "cmd_set             = 2.11.0\n"
    )
    assert version._from_board_txt(text) == (2, 11, 0)


def test_from_board_txt_raises_when_line_missing():
    with pytest.raises(version.VersionMismatch):
        version._from_board_txt("board_id = 0x01\nfw_version = 3.0.0\n")


def test_as_string():
    assert version.as_string((2, 11, 0)) == "2.11.0"


# The three product repos, in the same "<repo>/<relpath>" spelling _C_HEADERS
# and friends use (repo_path() resolves each against the sibling checkout).
_PRODUCT_REPOS = ["CFS-ECIG-SUITE/FW", "CFS-ECIG-SUITE/pc_app", "CFS-SUITE-BRIDGE"]

# Describes what a CMD_SET_VERSION-ish declaration looks like, not which
# language it is written in -- deliberately NOT one alternative per known
# syntax. The previous version of this pattern enumerated three syntaxes (a
# C #define, a Python tuple, a JSON key) and missed a fourth it hadn't seen
# yet: a plain-text "key = value" line (fw/brd0*/board.txt's "cmd_set
# = 2.11.0"). That is the failure this guard exists to catch, and it went
# through anyway because the guard's own pattern was itself an enumeration.
#
# The two alternatives below are organized by what disambiguates a real
# declaration from a mention, not by syntax:
#   - an identifier containing "cmd_set_version" (in any case/spelling --
#     this alone covers the C macro trio, the Python tuple, and the JSON
#     key, since all three spell that root) immediately followed by an
#     assignment-like operator (':' or '=') or by a bare value (whitespace
#     then a digit, which is how a C #define separates name from value);
#   - OR the bare word "cmd_set" (no "_version") immediately followed by
#     '=' or ':' and a dotted M.m.p value -- this is what board.txt uses,
#     and requiring the dotted-triple shape is what keeps it from matching
#     every unrelated variable named "cmd_set" (e.g. "the loaded command
#     table") elsewhere in these repos.
# This still isn't exhaustive -- no regex can be -- but it no longer
# assumes it already knows every shape a declaration can take, and it is
# expected to catch mentions along with declarations (see the expected set
# below, which is exactly what test_no_undeclared_copy_appeared is for:
# telling the two apart once, by hand, and naming the result).
_DECLARATION_PATTERN = (
    r"cmd_set_version\w*\b['\"]?\s*(?:[:=]|(?=\s+\d))"
    r"|\bcmd_set\b\s*[:=]\s*\d+\.\d+\.\d+"
)


def _grep_declaration_sites() -> set[str]:
    found = set()
    for repo in _PRODUCT_REPOS:
        repo_dir = sources.repo_path(repo)
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "grep", "-liP", _DECLARATION_PATTERN, "HEAD", "--"],
            capture_output=True, text=True,
        )
        # git grep exits 1 with empty stdout when nothing matches; only treat
        # a genuine error (exit >1, or exit 1 with stderr) as a failure.
        if result.returncode not in (0, 1) or (result.returncode == 1 and result.stderr):
            raise RuntimeError(f"git grep failed in {repo}: {result.stderr}")
        for line in result.stdout.splitlines():
            relpath = line.removeprefix("HEAD:")
            found.add(f"{repo}/{relpath}")
    return found


def test_no_undeclared_copy_appeared():
    """Grep all three product repos for anything that looks like a
    CMD_SET_VERSION-ish declaration and compare against the explicit,
    named set this build already knows about.

    This is a guard against the documented failure mode: a written total
    of "how many copies there are" always goes stale. If a new file starts
    matching the pattern, this test fails and names it -- decide whether
    it belongs in `_collect()` (a real product copy that must agree) or
    alongside the excluded/mention-only paths below (not a real copy: a
    frozen reference snapshot, a separately-versioned bootloader number
    that looks similar on purpose, or code/docs that only reads, compares,
    or talks about the value rather than declaring it).

    This pattern has already let a real copy through once -- see its own
    comment above -- specifically because it enumerated syntaxes instead
    of describing a declaration. Do not narrow it back to an enumeration
    to make this list shorter.
    """
    # Every real copy _collect() reads and compares.
    expected = {"/".join(src) for src in version._C_HEADERS}
    expected.add("/".join(version._ECIG_JSON))
    expected.add("/".join(version._BRIDGE_PY))
    expected.update("/".join(src) for src in version._BOARD_TXT)

    # Deliberately excluded: not real copies, on purpose.
    expected.update(
        {
            # A frozen reference snapshot, not a product -- requiring it to
            # agree would break the build the moment a real copy is bumped
            # and the reference is correctly left alone.
            # The bridge bootloaders' OWN number (BOOT_CMD_SET_VERSION_*),
            # frozen at the last shared revision they implement and
            # deliberately NOT the same value as CMD_SET_VERSION -- see the
            # "DELIBERATELY NOT ONE OF THESE COPIES" section of the header
            # comment above CMD_SET_VERSION in CFS-SUITE-BRIDGE's
            # pc_app/cfsbridge/commands.py, which is the authoritative
            # source for this distinction.
            "CFS-SUITE-BRIDGE/fw/brd01/Boot/Inc/boot_version.h",
            "CFS-SUITE-BRIDGE/fw/brd02/Boot/Inc/boot_version.h",
        }
    )

    # Mention-only: these match the pattern (they read, compare, hold as a
    # runtime/fake field, or write up in prose the same identifier/value)
    # but do not themselves declare a version, so they are not in
    # `_collect()`.
    expected.update(
        {
            "CFS-ECIG-SUITE/pc_app/tests/test_cmd_set_version.py",
            # BridgeIdentity's field holds whatever a live bridge reports
            # at runtime; it is a display value, not a source of truth.
            "CFS-ECIG-SUITE/pc_app/cfs_suite/gui/bridge_identity.py",
            # A test fake's hardcoded stand-in value, not a real copy.
            "CFS-ECIG-SUITE/pc_app/tests/bridge_fakes.py",
            # Comparison assertions ("C.CMD_SET_VERSION == (...)"), not
            # declarations -- the "==" in each is what the pattern's "="
            # branch actually matched.
            "CFS-SUITE-BRIDGE/pc_app/tests/test_commands_match_firmware.py",
            "CFS-SUITE-BRIDGE/pc_app/tests/test_dut_cmd_set.py",
            # tools/protocol_check.py READS the published standard and this
            # repository's copies to say whether they agree; it declares nothing.
            "CFS-SUITE-BRIDGE/pc_app/tools/protocol_check.py",
            # Planning/spec prose that quotes a real declaration line or a
            # field signature, written up for a reader rather than read by
            # any tool.
            "CFS-ECIG-SUITE/pc_app/docs/superpowers/plans/"
            "2026-08-31-cwm30c8-bridge-download.md",
            "CFS-ECIG-SUITE/pc_app/docs/superpowers/specs/"
            "2026-08-31-cwm30c8-bridge-download-design.md",
            "CFS-SUITE-BRIDGE/docs/superpowers/plans/"
            "2026-09-01-bridge-suite-unification.md",
            "CFS-SUITE-BRIDGE/docs/superpowers/plans/"
            "2026-09-04-brd02-runtime-pinmap.md",
            "CFS-SUITE-BRIDGE/docs/superpowers/plans/"
            "2026-09-08-brd03-dut-vdd.md",
            "CFS-SUITE-BRIDGE/docs/superpowers/plans/"
            "2026-09-11-brd02-cmsis-dap-persona.md",
            # The (since deleted) ref_cwm2032 alignment plan and spec, tracked
            # in the bridge repo since its docs/ re-include fix; prose only.
            "CFS-SUITE-BRIDGE/docs/superpowers/plans/"
            "2026-09-08-ref-cwm2032-proto-alignment.md",
            "CFS-SUITE-BRIDGE/docs/superpowers/specs/"
            "2026-09-07-ref-cwm2032-proto-alignment-design.md",
            "CFS-SUITE-BRIDGE/docs/superpowers/specs/"
            "2026-09-01-bridge-suite-unification-design.md",
            "CFS-SUITE-BRIDGE/pc_app/docs/superpowers/plans/"
            "2026-09-01-option-bytes-gui.md",
            # The CWM25C8 target spec/plan (prose quoting the 4.1.0 bump) and
            # its host test, which asserts "C.CMD_SET_VERSION == (4, 1, 0)".
            "CFS-SUITE-BRIDGE/docs/superpowers/plans/"
            "2026-09-15-cwm25c8-dut-target.md",
            "CFS-SUITE-BRIDGE/docs/superpowers/specs/"
            "2026-09-15-cwm25c8-dut-target-design.md",
            "CFS-SUITE-BRIDGE/pc_app/tests/test_cwm25c8.py",
        }
    )

    found = _grep_declaration_sites()

    new = found - expected
    missing = expected - found
    assert not new and not missing, (
        "CMD_SET version declaration sites changed since this test was "
        "written.\n"
        + (
            f"  NEW (not in the expected set -- decide: add to _collect(), "
            f"or to the excluded/mention-only set here):\n"
            + "".join(f"    {p}\n" for p in sorted(new))
            if new
            else ""
        )
        + (
            f"  MISSING (expected but not found by git grep -- file moved, "
            f"renamed, or removed; update this test and _collect() to match):\n"
            + "".join(f"    {p}\n" for p in sorted(missing))
            if missing
            else ""
        )
    )


def test_mismatch_raises(monkeypatch):
    """A drifted copy must stop the build, not produce a document that
    quietly picks one of the three numbers."""
    real = version._collect

    def fake():
        got = real()
        got["CFS-SUITE-BRIDGE/pc_app/cfsbridge/commands.py"] = (2, 10, 0)
        return got

    monkeypatch.setattr(version, "_collect", fake)
    with pytest.raises(version.VersionMismatch) as e:
        version.extract()
    assert "2.10.0" in str(e.value)
