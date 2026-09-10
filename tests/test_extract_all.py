import json
from pathlib import Path

from tools.extract import __main__ as extract_all


def test_writes_all_generated_files(tmp_path: Path):
    written = extract_all.run(tmp_path, internal=False)
    assert set(written) == {"version.json", "opcodes.json", "varpar.json", "bridge.json"}
    for p in written.values():
        assert p.exists()


def test_version_json_shape(tmp_path: Path):
    extract_all.run(tmp_path, internal=False)
    d = json.loads((tmp_path / "version.json").read_text(encoding="utf-8"))
    assert d["cmd_set_version"] == "2.11.0"
    assert d["edition"] == "public"


def test_internal_edition_is_labelled(tmp_path: Path):
    extract_all.run(tmp_path, internal=True)
    d = json.loads((tmp_path / "version.json").read_text(encoding="utf-8"))
    assert d["edition"] == "internal"
