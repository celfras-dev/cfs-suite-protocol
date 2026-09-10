import pytest
from tools.extract import version


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
