import json
import re
import subprocess
from pathlib import Path

from tools.extract import __main__ as extract_all

# The repo root of *this* repo (CFS-SUITE-PROTOCOL) -- not
# tools.extract.sources.PROJECT_ROOT, which points one level up, at the
# directory holding the sibling product repos sources.py reads from.
_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_writes_all_generated_files(tmp_path: Path):
    written = extract_all.run(tmp_path, internal=False)
    assert set(written) == {"version.json", "opcodes.json", "varpar.json", "bridge.json"}
    for p in written.values():
        assert p.exists()


def test_version_json_shape(tmp_path: Path):
    extract_all.run(tmp_path, internal=False)
    d = json.loads((tmp_path / "version.json").read_text(encoding="utf-8"))
    assert d["cmd_set_version"] == "4.1.0"
    assert d["edition"] == "public"


def test_internal_edition_is_labelled(tmp_path: Path):
    extract_all.run(tmp_path, internal=True)
    d = json.loads((tmp_path / "version.json").read_text(encoding="utf-8"))
    assert d["edition"] == "internal"


def test_internal_run_actually_carries_defaults(tmp_path: Path):
    """The label alone doesn't prove the payload matches it -- a run() that
    hardcoded varpar.extract(internal=False) regardless of the flag would
    still pass test_internal_edition_is_labelled. Check content, not label."""
    extract_all.run(tmp_path, internal=True)
    d = json.loads((tmp_path / "varpar.json").read_text(encoding="utf-8"))
    rows = [r for width in d["par"].values() for r in width]
    assert rows, "no par rows extracted at all -- can't assert anything about defaults"
    assert any("default" in r for r in rows)


def test_public_run_carries_no_defaults(tmp_path: Path):
    extract_all.run(tmp_path, internal=False)
    d = json.loads((tmp_path / "varpar.json").read_text(encoding="utf-8"))
    rows = [r for width in d["par"].values() for r in width]
    assert rows, "no par rows extracted at all -- can't assert anything about defaults"
    assert not any("default" in r for r in rows)


def _forbidden_values() -> set:
    """Every value the product bakes in, taken from the source rather than a
    hand-written list (see tests/test_extract_varpar.py's forbidden_values,
    which this mirrors) -- minus tools.build.PROTOCOL_VALUE_EXEMPTIONS.

    Committed spec/_generated/opcodes.json now legitimately contains 1000
    (BURST_PERIOD_MS_MAX, a real standard constant, see opcodes.py's
    burst_limits()), which is also LED_BREATH_PERIOD_MS's product default.
    Without the exemption this scan cannot tell those two facts apart, same
    as the PDF/site leak gate in tools/build.py -- so this must go through
    build.leak_gate_values(), not a bare forbidden-defaults set, exactly
    like tests/test_public_leak.py does.
    """
    from tools import build
    return build.leak_gate_values()


def test_committed_generated_files_are_the_public_edition():
    """Guards the thing that actually gets published: the *committed*
    spec/_generated/*.json, not whatever `run()` would produce right now.
    An operator who runs `python -m tools.extract --internal` and commits
    the result would leak product thresholds while every other test in this
    suite (which all call run() themselves, in a tmp_path) stays green.

    This reads `git show HEAD:<path>`, i.e. the committed blob, not the
    working tree. It will therefore fail if spec/_generated has uncommitted
    changes that differ from HEAD -- that is intended: a dirty
    spec/_generated is exactly the state this test exists to catch before
    it becomes a commit.
    """
    out = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "ls-files", "spec/_generated"],
        capture_output=True, check=True, text=True,
    )
    tracked = [line for line in out.stdout.splitlines() if line.endswith(".json")]
    assert tracked, "no tracked JSON found under spec/_generated"

    blobs = {}
    for relpath in tracked:
        show = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "show", f"HEAD:{relpath}"],
            capture_output=True, check=True, text=True,
        )
        blobs[relpath] = show.stdout

    version_path = next(p for p in tracked if p.endswith("version.json"))
    version_doc = json.loads(blobs[version_path])
    assert version_doc["edition"] == "public", \
        f"{version_path} is labelled {version_doc['edition']!r}, not public"

    forbidden = _forbidden_values()
    assert forbidden, "forbidden-defaults derivation found nothing -- leak check would be vacuous"

    for relpath, blob in blobs.items():
        for n in forbidden:
            if re.search(rf'(?<![\d.]){n}(?![\d.])', blob):
                raise AssertionError(f"{n} leaked into committed {relpath}")


def test_opcodes_json_carries_the_new_standard_tables(tmp_path: Path):
    """Jobs 1-3: ver_selectors, log_fields and burst_limits must reach the
    generated opcodes.json alongside commands/errors/op_modes, or the
    renderer has nothing to build the new placeholders from."""
    extract_all.run(tmp_path, internal=False)
    d = json.loads((tmp_path / "opcodes.json").read_text(encoding="utf-8"))
    assert {"commands", "errors", "op_modes",
            "ver_selectors", "log_fields", "burst_limits"} <= set(d)
    assert any(s["name"] == "VER_SEL_FW" for s in d["ver_selectors"])
    assert any(f["name"] == "LOG_FIELD_VDD" for f in d["log_fields"])
    assert any(b["name"] == "BURST_PERIOD_MS_MAX" for b in d["burst_limits"])
