import pytest
from tools.extract import sources


def test_repo_path_resolves_sibling_repo():
    p = sources.repo_path("CFS-ECIG-SUITE/FW")
    assert p.is_dir()
    assert (p / ".git").exists()


def test_read_committed_returns_head_content():
    text = sources.read_committed("CFS-ECIG-SUITE/FW", "App/Inc/app_proto.h")
    assert "CMD_SET_VERSION_MAJOR" in text


def test_read_committed_ignores_working_tree():
    """conf/cmd_set.json is currently overwritten in the working tree with a
    BP2601 copy that has no cmd_set_version key. Reading HEAD must still see
    the ECIG file. This is the whole reason this layer exists."""
    text = sources.read_committed("CFS-ECIG-SUITE/pc_app", "conf/cmd_set.json")
    assert '"cmd_set_version"' in text


def test_missing_source_raises():
    with pytest.raises(sources.SourceMissing):
        sources.read_committed("CFS-ECIG-SUITE/FW", "App/Inc/nope.h")
