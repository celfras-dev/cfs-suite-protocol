import subprocess

import pytest
from tools.extract import sources, version


def test_extract_returns_current_cmd_set_version():
    assert version.extract() == (2, 11, 0)


def test_collect_sees_all_eight_copies():
    """One source per known CMD_SET_VERSION copy -- named explicitly so
    dropping any of them (or silently merging two) fails this test."""
    expected_keys = {
        "CFS-ECIG-SUITE/FW/App/Inc/app_proto.h",
        "CFS-SUITE-BRIDGE/fw/brd01/App/Inc/app_version.h",
        "CFS-SUITE-BRIDGE/fw/brd02/App/Inc/app_version.h",
        "CFS-SUITE-BRIDGE/fw_dut/cwm2032/App/Inc/app_proto.h",
        "CFS-SUITE-BRIDGE/fw_dut/cwm1016/App/Inc/app_proto.h",
        "CFS-SUITE-BRIDGE/fw_dut/cwm0508/App/Inc/app_proto.h",
        "CFS-ECIG-SUITE/pc_app/conf/cmd_set.json",
        "CFS-SUITE-BRIDGE/pc_app/cfsbridge/commands.py",
    }
    assert set(version._collect().keys()) == expected_keys


def test_as_string():
    assert version.as_string((2, 11, 0)) == "2.11.0"


# The three product repos, in the same "<repo>/<relpath>" spelling _C_HEADERS
# and friends use (repo_path() resolves each against the sibling checkout).
_PRODUCT_REPOS = ["CFS-ECIG-SUITE/FW", "CFS-ECIG-SUITE/pc_app", "CFS-SUITE-BRIDGE"]

# Catches all three declaration syntaxes: the C #define trio, the Python
# tuple assignment, and the JSON key (which also catches code/tests that
# merely read or regex-match that key -- see the mention-only entries below).
_DECLARATION_PATTERN = (
    r'^\s*#define\s+CMD_SET_VERSION_(MAJOR|MINOR|PATCH)'
    r'|^CMD_SET_VERSION\s*='
    r'|"cmd_set_version"'
)


def _grep_declaration_sites() -> set[str]:
    found = set()
    for repo in _PRODUCT_REPOS:
        repo_dir = sources.repo_path(repo)
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "grep", "-lE", _DECLARATION_PATTERN, "HEAD", "--"],
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
    """Grep all three product repos for every CMD_SET version definition
    site and compare against the explicit, named set this build already
    knows about.

    This is a guard against the documented failure mode: a written total
    of "how many copies there are" always goes stale (it already has,
    twice in two days, when a board joined and was withdrawn). If a new
    file starts declaring the version, this test fails and names it --
    decide whether it belongs in `_collect()` (a real product copy that
    must agree) or alongside the excluded/mention-only paths below (not
    a real copy: a frozen reference snapshot, or code that only reads or
    regex-matches the key rather than declaring it).
    """
    # The eight copies _collect() reads and compares.
    expected = {"/".join(src) for src in version._C_HEADERS}
    expected.add("/".join(version._ECIG_JSON))
    expected.add("/".join(version._BRIDGE_PY))

    # Deliberately excluded: a frozen reference snapshot, not a product --
    # requiring it to agree would break the build the moment a real copy is
    # bumped and the reference is correctly left alone.
    expected.add(
        "CFS-SUITE-BRIDGE/fw_dut/ref_cwm2032_working_uart_swd_together/"
        "Project/Inc/app_proto_defs.h"
    )

    # Mention-only: these match the grep pattern (they read or regex-match
    # "cmd_set_version"/"CMD_SET_VERSION") but do not themselves declare a
    # version, so they are not in _collect().
    expected.add("CFS-ECIG-SUITE/pc_app/cfs_suite/cmd_set.py")
    expected.add("CFS-ECIG-SUITE/pc_app/tests/test_cmd_set_version.py")

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
