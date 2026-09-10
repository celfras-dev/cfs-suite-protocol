# Celfras Standard Protocol 문서 Implementation Plan

> **HISTORICAL RECORD — copied into this repo 2026-09-10 (Task 15), not
> maintained here.** This is the plan as it stood during execution in
> CFS-ECIG-SUITE; it was edited task-by-task while work proceeded, so several
> of its code blocks (task numbering, exact filenames, intermediate function
> shapes) were superseded by later tasks in the same plan or by review
> findings and no longer match what shipped. It is kept for *why* this repo
> exists and how the work was sequenced, not as a spec of the current build.
> For what the pipeline actually does today, read this repo's own code and
> tests — `tests/` (88 tests as of Task 15) is the current truth, not this
> file's code samples.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CMD_SET 2.11.0 기준의 표준 프로토콜 문서를 EN/KO/ZH PDF + 정적 웹사이트로 빌드하는 새 public repo `CFS-SUITE-PROTOCOL` 을 만들고, 이후 CMD_SET 이 오를 때마다 함께 갱신되도록 규칙을 심는다.

**Architecture:** 산문은 언어별 Markdown 3벌로 손으로 쓰고, 표(opcode·var/par·브릿지 대역)는 세 제품 repo 의 **커밋된** 소스에서 추출해 JSON 으로 떨군 뒤 3개 언어가 공유한다. 렌더러가 md + JSON → 단일 HTML 을 만들고, 그 HTML 하나가 웹사이트와 (Chrome 헤드리스를 거쳐) PDF 양쪽이 된다. 공개판/사내판은 같은 소스에 `--internal` 플래그로 갈리며, 실측값 누출은 빌드 게이트 테스트가 막는다.

**Tech Stack:** Python 3.14 (`markdown`, `jinja2`, `pytest`), Chrome 헤드리스(`--print-to-pdf`), git, `gh` CLI.

## Global Constraints

- 대상 CMD_SET 버전은 **2.11.0**. 이 repo 는 그 번호를 **선언하지 않는다** — `CFS-ECIG-SUITE/FW/App/Inc/app_proto.h` 에서 읽는다. `app_proto.h` 의 사본 목록에 이 repo 를 **추가하지 않는다**.
- 모든 추출은 **워킹 트리가 아니라 커밋된 내용**(`git -C <repo> show HEAD:<path>`)을 읽는다. 현재 `CFS-ECIG-SUITE/pc_app/conf/*.json` 이 `BP2601_org` 사본으로 덮여 있다(uncommitted).
- **공개판 금지 값은 손으로 적지 않고 소스에서 도출한다.** 금지 집합 =
  `varpar.extract(internal=True)` 가 돌려주는 모든 `default` 값. 이 숫자가 `out/public/`
  산출물이나 `site/` 에 나타나면 빌드 실패.

  현재 그 집합은 `{300, 350, 600, 1000, 2000, 3400, 8000, 10000, 180000}` 아홉 개다 —
  **참고용으로만 적어 둔다. 코드에 이 목록을 박지 말 것.** 이 계획의 초안은 손으로 센
  일곱 개를 싣고 있었고 `600`(`CHG_TIMEOUT_TH`)과 `10000`(`LONG_PUFF_TH`)을 빠뜨렸다.
  Task 4 리뷰가 잡았다. 도출하면 `par_map.json` 에 default 가 하나 늘어도 게이트가
  저절로 따라온다.
- `out/internal/` 은 `.gitignore` 에 등재한다. 사내판이 public repo 에 들어갈 수 없어야 한다.
- 언어별 폰트 스택을 따로 준다 — ko `"Noto Sans KR","Malgun Gothic"` / zh `"Microsoft YaHei","Noto Sans SC"` / en `"Segoe UI",Arial`. 한 스택 공유 시 중국어 `文` 이 U+2F00 로 떨어진다(실측).
- 코드·주석·커밋 메시지는 **영어**. 문서 산문과 계획/스펙은 한글 허용(제품 규칙).
- repo 위치: `D:/BaiduSyncdisk/Company/LianZhi/Project/CFS-SUITE-PROTOCOL`
- 이 repo 는 worktree 규칙 대상이 아니다 — 신규 repo 이고 다른 세션이 쓰지 않는다. `main` 에 직접 커밋한다.

---

### Task 1: Repo 골격과 소스 접근 계층

**Files:**
- Create: `CFS-SUITE-PROTOCOL/.gitignore`
- Create: `CFS-SUITE-PROTOCOL/requirements.txt`
- Create: `CFS-SUITE-PROTOCOL/tools/extract/__init__.py`
- Create: `CFS-SUITE-PROTOCOL/tools/extract/sources.py`
- Test: `CFS-SUITE-PROTOCOL/tests/test_sources.py`

**Interfaces:**
- Produces: `sources.repo_path(name: str) -> Path`, `sources.read_committed(repo: str, relpath: str) -> str`, `sources.SourceMissing(Exception)`

- [ ] **Step 1: repo 와 venv 생성**

```bash
cd "D:/BaiduSyncdisk/Company/LianZhi/Project"
mkdir CFS-SUITE-PROTOCOL && cd CFS-SUITE-PROTOCOL
git init -b main
python -m venv venv
./venv/Scripts/python.exe -m pip install -q markdown jinja2 pytest
printf 'markdown>=3.10\njinja2>=3.1\npytest>=8.0\n' > requirements.txt
```

- [ ] **Step 2: `.gitignore` 작성**

```
venv/
__pycache__/
*.pyc
.pytest_cache/

# Internal-only build output. NEVER commit: it carries product
# threshold values that the public document deliberately omits.
out/internal/

site/
```

- [ ] **Step 3: 실패하는 테스트 작성**

`tests/test_sources.py`:

```python
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
```

- [ ] **Step 4: 테스트가 실패하는지 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_sources.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools'`

- [ ] **Step 5: 최소 구현**

`tools/extract/__init__.py`: 빈 파일.

`tools/extract/sources.py`:

```python
"""Read source files from the sibling product repos.

Everything is read from the committed tree (``git show HEAD:<path>``),
never from the working tree. A bench session routinely swaps
CFS-ECIG-SUITE/pc_app/conf/*.json for another board's copy; reading the
working tree would put that board's tables into the standard document.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class SourceMissing(Exception):
    """A source repo or a path inside it could not be read."""


def repo_path(name: str) -> Path:
    p = PROJECT_ROOT / name
    if not p.is_dir():
        raise SourceMissing(f"source repo not found: {p}")
    return p


def read_committed(repo: str, relpath: str) -> str:
    root = repo_path(repo)
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "show", f"HEAD:{relpath}"],
            capture_output=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        raise SourceMissing(
            f"{repo}:{relpath} is not in HEAD ({e.stderr.decode(errors='replace').strip()})"
        ) from e
    return out.stdout.decode("utf-8")
```

`tests/` 에서 `tools` 를 import 할 수 있도록 `pyproject.toml` 추가:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_sources.py -v`
Expected: PASS (4 passed)

- [ ] **Step 7: 커밋**

```bash
git add .gitignore requirements.txt pyproject.toml tools tests
git commit -m "Read product sources from HEAD, not the working tree"
```

---

### Task 2: CMD_SET 버전 추출과 3-repo 교차 검증

세 repo 에 흩어진 번호를 한자리에서 대조하는 유일한 지점이다. 기존 두 테스트는 각각 자기 repo 안만 본다.

**Files:**
- Create: `CFS-SUITE-PROTOCOL/tools/extract/version.py`
- Create: `CFS-SUITE-PROTOCOL/VERSION`
- Test: `CFS-SUITE-PROTOCOL/tests/test_extract_version.py`

**Interfaces:**
- Consumes: `sources.read_committed`
- Produces: `version.extract() -> tuple[int,int,int]`, `version.VersionMismatch(Exception)`, `version.as_string(v) -> str`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_extract_version.py`:

```python
import pytest
from tools.extract import version


def test_extract_returns_current_cmd_set_version():
    assert version.extract() == (2, 11, 0)


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
```

- [ ] **Step 2: 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_extract_version.py -v`
Expected: FAIL — `ImportError: cannot import name 'version'`

- [ ] **Step 3: 구현**

`tools/extract/version.py`:

```python
"""Derive the CMD_SET version instead of declaring one.

This repository holds no copy of the number. It reads the three copies that
the product repos' own tests can each see only half of, and refuses to build
when they disagree -- which makes the document build the only place all
three are compared at once.
"""
from __future__ import annotations

import json
import re

from . import sources

Version = tuple[int, int, int]

# All eight copies of the number. app_proto.h's own comment lists five and
# names three more (the DUT test firmwares) that it says this repository's
# tests cannot hold; the bridge repo's test holds those three and not these
# five. Neither test sees all eight -- this build does.
#
# A ninth #define exists and is deliberately NOT here:
# CFS-SUITE-BRIDGE/fw_dut/ref_cwm2032_working_uart_swd_together/
# Project/Inc/app_proto_defs.h. That tree is a frozen reference snapshot,
# not a product; requiring it to agree would break the build the first time
# someone bumps the real copies and correctly leaves the reference alone.
# test_no_undeclared_copy_appeared() below is what keeps this decision
# honest: it greps for every definition site and fails when the set changes,
# so a tenth copy is a failing test rather than a stale comment.
_C_HEADERS = [
    ("CFS-ECIG-SUITE/FW", "App/Inc/app_proto.h"),
    ("CFS-SUITE-BRIDGE", "fw/brd01/App/Inc/app_version.h"),
    ("CFS-SUITE-BRIDGE", "fw/brd02/App/Inc/app_version.h"),
    ("CFS-SUITE-BRIDGE", "fw_dut/cwm2032/App/Inc/app_proto.h"),
    ("CFS-SUITE-BRIDGE", "fw_dut/cwm1016/App/Inc/app_proto.h"),
    ("CFS-SUITE-BRIDGE", "fw_dut/cwm0508/App/Inc/app_proto.h"),
]
_ECIG_JSON = ("CFS-ECIG-SUITE/pc_app", "conf/cmd_set.json")
_BRIDGE_PY = ("CFS-SUITE-BRIDGE", "pc_app/cfsbridge/commands.py")


class VersionMismatch(Exception):
    """The CMD_SET copies disagree; the document must not pick a winner."""


def as_string(v: Version) -> str:
    return "%d.%d.%d" % v


def _from_c_header(text: str) -> Version:
    out = []
    for part in ("MAJOR", "MINOR", "PATCH"):
        m = re.search(rf"^\s*#define\s+CMD_SET_VERSION_{part}\s+(\d+)", text, re.M)
        if not m:
            raise VersionMismatch(f"CMD_SET_VERSION_{part} not found in header")
        out.append(int(m.group(1)))
    return tuple(out)  # type: ignore[return-value]


def _from_cmd_set_json(text: str) -> Version:
    d = json.loads(text)["cmd_set_version"]
    return (int(d["major"]), int(d["minor"]), int(d["patch"]))


def _from_bridge_py(text: str) -> Version:
    m = re.search(r"^CMD_SET_VERSION\s*=\s*\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)", text, re.M)
    if not m:
        raise VersionMismatch("CMD_SET_VERSION tuple not found in commands.py")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _collect() -> dict[str, Version]:
    found = {
        "/".join(src): _from_c_header(sources.read_committed(*src))
        for src in _C_HEADERS
    }
    found["/".join(_ECIG_JSON)] = _from_cmd_set_json(sources.read_committed(*_ECIG_JSON))
    found["/".join(_BRIDGE_PY)] = _from_bridge_py(sources.read_committed(*_BRIDGE_PY))
    return found


def extract() -> Version:
    found = _collect()
    distinct = set(found.values())
    if len(distinct) != 1:
        lines = "\n".join(f"  {as_string(v)}  {k}" for k, v in sorted(found.items()))
        raise VersionMismatch(
            "CMD_SET copies disagree -- fix the product repos first:\n" + lines
        )
    return distinct.pop()
```

- [ ] **Step 4: 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_extract_version.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: `VERSION` 파일 생성**

```bash
./venv/Scripts/python.exe -c "from tools.extract import version; print(version.as_string(version.extract()))" > VERSION
cat VERSION   # 2.11.0
```

- [ ] **Step 6: 커밋**

```bash
git add tools/extract/version.py tests/test_extract_version.py VERSION
git commit -m "Derive CMD_SET version from the product repos, and refuse a mismatch"
```

---

### Task 3: opcode 표 추출

`PROTOCOL.md` 가 stale 해진 지점이 정확히 이 표다. 손으로 쓰지 않는다.

**Files:**
- Create: `CFS-SUITE-PROTOCOL/tools/extract/opcodes.py`
- Test: `CFS-SUITE-PROTOCOL/tests/test_extract_opcodes.py`

**Interfaces:**
- Produces: `opcodes.extract() -> list[dict]` — 각 항목 `{"id": int, "name": str, "req": str, "resp": str, "note": str, "group": str}`; `opcodes.errors() -> list[dict]` — `{"code": int, "name": str, "note": str}`; `opcodes.op_modes() -> list[dict]` — `{"value": int, "name": str, "note": str}`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_extract_opcodes.py`:

```python
from tools.extract import opcodes


def test_core_commands_present():
    by_id = {c["id"]: c["name"] for c in opcodes.extract()}
    assert by_id[0x01] == "CMD_PING"
    assert by_id[0x05] == "CMD_GET_VERSION"
    assert by_id[0x40] == "CMD_LOG_BURST_START"
    assert by_id[0x5B] == "CMD_PAR32_GET"
    assert by_id[0x74] == "CMD_GET_TUNING_PAR"


def test_version_define_is_not_an_opcode():
    """CMD_SET_VERSION_MAJOR sits among the #defines and must not be
    mistaken for a command."""
    names = {c["name"] for c in opcodes.extract()}
    assert not any(n.startswith("CMD_SET_VERSION") for n in names)


def test_request_and_response_shapes_captured():
    ping = next(c for c in opcodes.extract() if c["id"] == 0x01)
    assert "PONG" in ping["resp"]
    burst = next(c for c in opcodes.extract() if c["id"] == 0x40)
    assert "fields_mask" in burst["req"]


def test_error_codes():
    by_code = {e["code"]: e["name"] for e in opcodes.errors()}
    assert by_code == {
        0x00: "ERR_OK", 0x01: "ERR_BAD_LEN", 0x02: "ERR_BAD_CRC",
        0x03: "ERR_BAD_ARGS", 0x04: "ERR_NOT_READY", 0x05: "ERR_UNKNOWN",
    }


def test_op_modes():
    by_val = {m["value"]: m["name"] for m in opcodes.op_modes()}
    assert by_val[0x00] == "OPMODE_ISP"
    assert by_val[0x01] == "OPMODE_NORMAL"
    assert by_val[0x02] == "OPMODE_DEBUG"
    assert by_val[0x04] == "OPMODE_TEST"
```

- [ ] **Step 2: 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_extract_opcodes.py -v`
Expected: FAIL — `cannot import name 'opcodes'`

- [ ] **Step 3: 구현**

`tools/extract/opcodes.py`. `app_proto.h` 의 `#define` 은 전부 다음 모양이다:

```
#define CMD_PING             0x01u  // req []                 resp [OK]["PONG"]
```

주석의 `req ... resp ...` 를 그대로 살린다. `group` 은 id 대역으로 정한다.

```python
"""Pull the opcode table out of app_proto.h.

The table is the part of the protocol document that went stale twice
(2.10.0 and 2.11.0), and it is mechanically derivable. Prose is written by
hand; tables are generated, so all three language editions share one.
"""
from __future__ import annotations

import re

from . import sources

_HEADER = ("CFS-ECIG-SUITE/FW", "App/Inc/app_proto.h")

# CMD_SET_VERSION_* are #defines in the same file and are not commands.
_CMD_RE = re.compile(
    r"^\s*#define\s+(CMD_(?!SET_VERSION_)[A-Z0-9_]+)\s+0x([0-9A-Fa-f]{2})u?\s*(?://\s*(.*))?$",
    re.M,
)
_ERR_RE = re.compile(
    r"^\s*#define\s+(ERR_[A-Z_]+)\s+0x([0-9A-Fa-f]{2})u?\s*(?://\s*(.*))?$", re.M
)
_MODE_RE = re.compile(
    r"^\s*#define\s+(OPMODE_[A-Z_]+)\s+0x([0-9A-Fa-f]{2})u?\s*(?://\s*(.*))?$", re.M
)

_GROUPS = [
    (0x01, 0x0F, "core"),
    (0x10, 0x1F, "device"),
    (0x20, 0x2F, "register"),
    (0x30, 0x3F, "log"),
    (0x40, 0x4F, "burst"),
    (0x50, 0x5F, "var_par"),
    (0x60, 0x6F, "display"),
    (0x70, 0x7F, "tuning"),
    (0xC0, 0xFF, "bridge"),
]


def _group_for(cmd_id: int) -> str:
    for lo, hi, name in _GROUPS:
        if lo <= cmd_id <= hi:
            return name
    return "unassigned"


def _split_shapes(comment: str) -> tuple[str, str, str]:
    """Split '// req [...] resp [...] -- note' into its three parts."""
    if not comment:
        return "", "", ""
    note = ""
    if "--" in comment:
        comment, note = comment.split("--", 1)
    m = re.search(r"\breq\b(.*?)(?=\bresp\b|$)", comment, re.S)
    req = m.group(1).strip() if m else ""
    m = re.search(r"\bresp\b(.*)$", comment, re.S)
    resp = m.group(1).strip() if m else ""
    if not req and not resp:
        note = (comment + " " + note).strip()
    return req, resp, note.strip()


def _text() -> str:
    return sources.read_committed(*_HEADER)


def extract() -> list[dict]:
    out = []
    for name, hexid, comment in _CMD_RE.findall(_text()):
        cmd_id = int(hexid, 16)
        req, resp, note = _split_shapes((comment or "").strip())
        out.append({
            "id": cmd_id, "name": name, "req": req, "resp": resp,
            "note": note, "group": _group_for(cmd_id),
        })
    out.sort(key=lambda c: c["id"])
    return out


def errors() -> list[dict]:
    return sorted(
        ({"code": int(h, 16), "name": n, "note": (c or "").strip()}
         for n, h, c in _ERR_RE.findall(_text())),
        key=lambda e: e["code"],
    )


def op_modes() -> list[dict]:
    return sorted(
        ({"value": int(h, 16), "name": n, "note": (c or "").strip()}
         for n, h, c in _MODE_RE.findall(_text())),
        key=lambda m: m["value"],
    )
```

- [ ] **Step 4: 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_extract_opcodes.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 눈으로 한 번 확인**

```bash
./venv/Scripts/python.exe -c "
from tools.extract import opcodes
for c in opcodes.extract(): print(f\"0x{c['id']:02X} {c['name']:24} {c['group']}\")
"
```

Expected: `0x01 CMD_PING core` 부터 `0x74 CMD_GET_TUNING_PAR tuning` 까지. `CMD_SET_VERSION_*` 이 없어야 한다.

- [ ] **Step 6: 커밋**

```bash
git add tools/extract/opcodes.py tests/test_extract_opcodes.py
git commit -m "Generate the opcode table from app_proto.h"
```

---

### Task 4: var/par 부록 추출 — 공개판에서 실측값을 뺀다

**Files:**
- Create: `CFS-SUITE-PROTOCOL/tools/extract/varpar.py`
- Test: `CFS-SUITE-PROTOCOL/tests/test_extract_varpar.py`

**Interfaces:**
- Produces: `varpar.extract(internal: bool) -> dict` — `{"var": {...}, "par": {"par8": [...], "par16": [...], "par32": [...]}}`. 각 par 항목 `{"id": int, "name": str, "unit": str, "access": str}`, `internal=True` 일 때만 `"default"` 키가 붙는다.

**표준이 정의할 것은 "id 14 는 이 의미다"이지 "우리 제품은 350 을 쓴다"가 아니다.**

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_extract_varpar.py`:

```python
import json

from tools.extract import varpar

def forbidden_values() -> set:
    """Every value the product bakes in, taken from the source rather than a
    hand-written list. A hand-written one was already wrong once: it missed
    CHG_TIMEOUT_TH (600) and LONG_PUFF_TH (10000)."""
    return {r["default"]
            for rows in varpar.extract(internal=True)["par"].values()
            for r in rows if "default" in r}


def test_public_has_ids_names_units():
    d = varpar.extract(internal=False)
    p16 = {e["id"]: e for e in d["par"]["par16"]}
    assert p16[14]["name"] == "DRY_PUFF_ABS_TEMP_TH"
    assert p16[14]["unit"] == "degC"
    assert p16[4]["name"] == "UVLO_HEAT_INIT_TH"


def test_public_carries_no_default_values():
    d = varpar.extract(internal=False)
    for width in ("par8", "par16", "par32"):
        for e in d["par"][width]:
            assert "default" not in e, f"{e['name']} leaked a default"


def test_public_json_contains_no_forbidden_number():
    blob = json.dumps(varpar.extract(internal=False))
    for n in forbidden_values():
        assert str(n) not in blob, f"{n} leaked into the public appendix"


def test_internal_carries_defaults():
    d = varpar.extract(internal=True)
    p16 = {e["id"]: e for e in d["par"]["par16"]}
    assert p16[14]["default"] == 350
    assert p16[4]["default"] == 3400


def test_readonly_flag_survives():
    d = varpar.extract(internal=False)
    p16 = {e["id"]: e for e in d["par"]["par16"]}
    assert p16[0]["access"] == "ro"      # VDD (ro)
    assert p16[3]["access"] == "rw"      # LED_BREATH_PERIOD_MS


def test_var_slots_are_read_only_view():
    d = varpar.extract(internal=False)
    names = {e["name"] for e in d["var"]["var8"]}
    assert "EXT_CTRL_STATUS" in names
```

- [ ] **Step 2: 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_extract_varpar.py -v`
Expected: FAIL — `cannot import name 'varpar'`

- [ ] **Step 3: 구현**

`min`/`max` 는 GUI 스핀박스 한계일 뿐 프로토콜이 아니므로 **양쪽 판 모두에서 버린다**. `min`/`max` 를 실으면 `max: 5000` 같은 값이 금지 숫자와 섞여 누출 검사를 흐린다.

`tools/extract/varpar.py`:

```python
"""Appendix A -- the ECIG var/par id maps.

Public editions carry ids, names, units and access only. The values a
product bakes in (dry-puff thresholds, protection limits) are product data,
not protocol: a standard defines what id 14 means, not that this product
writes 350 into it. min/max are dropped from both editions -- they are the
host GUI's spinbox limits, not part of the wire contract.
"""
from __future__ import annotations

import json

from . import sources

_VAR = ("CFS-ECIG-SUITE/pc_app", "conf/var_map.json")
_PAR = ("CFS-ECIG-SUITE/pc_app", "conf/par_map.json")

_WIDTHS = ("par8", "par16", "par32")


def _clean_name(raw: str) -> tuple[str, str]:
    """'VDD (ro)' -> ('VDD', 'ro'); anything else -> (name, 'rw')."""
    name = raw.strip()
    if name.endswith("(ro)"):
        return name[:-4].strip(), "ro"
    return name, "rw"


def _par(internal: bool) -> dict:
    doc = json.loads(sources.read_committed(*_PAR))
    out: dict[str, list] = {}
    for width in _WIDTHS:
        rows = []
        for sid, e in sorted(doc.get(width, {}).items(), key=lambda kv: int(kv[0])):
            name, access = _clean_name(e["name"])
            if e.get("readonly"):
                access = "ro"
            row = {"id": int(sid), "name": name,
                   "unit": e.get("unit", ""), "access": access}
            if internal and "default" in e:
                row["default"] = e["default"]
            rows.append(row)
        out[width] = rows
    return out


def _var() -> dict:
    doc = json.loads(sources.read_committed(*_VAR))
    out: dict[str, list] = {}
    for width in ("var8", "var16", "var32"):
        rows = []
        for sid, e in sorted(doc.get(width, {}).items(), key=lambda kv: int(kv[0])):
            name, _ = _clean_name(e["name"])
            rows.append({"id": int(sid), "name": name, "unit": e.get("unit", "")})
        out[width] = rows
    return out


def extract(internal: bool = False) -> dict:
    return {"var": _var(), "par": _par(internal)}
```

> `var_map.json` 의 실제 최상위 키 이름을 먼저 확인할 것:
> `./venv/Scripts/python.exe -c "from tools.extract import sources; import json; print(list(json.loads(sources.read_committed('CFS-ECIG-SUITE/pc_app','conf/var_map.json')).keys()))"`
> `var8`/`var16`/`var32` 가 아니면 `_var()` 의 튜플을 실제 키로 바꾼다.

- [ ] **Step 4: 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_extract_varpar.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add tools/extract/varpar.py tests/test_extract_varpar.py
git commit -m "Appendix A: ids and units in public, product values internal only"
```

---

### Task 5: 브릿지 0xC0+ 대역 추출

**Files:**
- Create: `CFS-SUITE-PROTOCOL/tools/extract/bridge.py`
- Test: `CFS-SUITE-PROTOCOL/tests/test_extract_bridge.py`

**Interfaces:**
- Produces: `bridge.extract() -> list[dict]` — `{"id": int, "name": str, "note": str}`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_extract_bridge.py`:

```python
from tools.extract import bridge


def test_bridge_band_commands():
    by_id = {c["id"]: c["name"] for c in bridge.extract()}
    assert by_id[0xC0] == "CMD_B_PING"
    assert by_id[0xC1] == "CMD_B_INFO"
    assert by_id[0xC7] == "CMD_B_GET_VERSION"


def test_every_entry_is_in_the_reserved_band():
    for c in bridge.extract():
        assert c["id"] >= 0xC0, f"{c['name']} is below the 0xC0 bridge band"


def test_reserved_but_unimplemented_is_marked():
    caps = next(c for c in bridge.extract() if c["id"] == 0xC2)
    assert "reserved" in caps["note"].lower()
```

- [ ] **Step 2: 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_extract_bridge.py -v`
Expected: FAIL — `cannot import name 'bridge'`

- [ ] **Step 3: 구현**

`tools/extract/bridge.py`:

```python
"""Appendix C -- the 0xC0+ band the bridge answers itself.

A DUT never sees these: the bridge answers >= 0xC0 and forwards everything
below it untouched. They are in the standard so a product does not claim an
opcode the transport layer has already taken.
"""
from __future__ import annotations

import re

from . import sources

_SRC = ("CFS-SUITE-BRIDGE", "pc_app/cfsbridge/commands.py")
_RE = re.compile(r"^(CMD_[A-Z0-9_]+)\s*=\s*0x([0-9A-Fa-f]{2})\s*(?:#\s*(.*))?$", re.M)

BAND_BASE = 0xC0


def extract() -> list[dict]:
    text = sources.read_committed(*_SRC)
    out = []
    for name, hexid, note in _RE.findall(text):
        cmd_id = int(hexid, 16)
        if cmd_id < BAND_BASE:
            continue
        out.append({"id": cmd_id, "name": name, "note": (note or "").strip()})
    out.sort(key=lambda c: c["id"])
    return out
```

- [ ] **Step 4: 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_extract_bridge.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add tools/extract/bridge.py tests/test_extract_bridge.py
git commit -m "Appendix C: the 0xC0+ band reserved by the bridge"
```

---

### Task 6: 추출 오케스트레이터 — `_generated/*.json`

**Files:**
- Create: `CFS-SUITE-PROTOCOL/tools/extract/__main__.py`
- Create: `CFS-SUITE-PROTOCOL/spec/_generated/.gitkeep`
- Test: `CFS-SUITE-PROTOCOL/tests/test_extract_all.py`

**Interfaces:**
- Consumes: `version.extract`, `opcodes.extract/errors/op_modes`, `varpar.extract`, `bridge.extract`
- Produces: `tools.extract.__main__.run(out_dir: Path, internal: bool) -> dict` — 씌어진 파일명 → 경로

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_extract_all.py`:

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_extract_all.py -v`
Expected: FAIL — `No module named 'tools.extract.__main__'`

- [ ] **Step 3: 구현**

`tools/extract/__main__.py`:

```python
"""Write every generated table into spec/_generated/."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import bridge, opcodes, varpar, version


def run(out_dir: Path, internal: bool = False) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version.json": {
            "cmd_set_version": version.as_string(version.extract()),
            "edition": "internal" if internal else "public",
        },
        "opcodes.json": {
            "commands": opcodes.extract(),
            "errors": opcodes.errors(),
            "op_modes": opcodes.op_modes(),
        },
        "varpar.json": varpar.extract(internal=internal),
        "bridge.json": {"commands": bridge.extract()},
    }
    written = {}
    for name, data in payload.items():
        p = out_dir / name
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
        written[name] = p
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract protocol tables from product repos")
    ap.add_argument("--out", default="spec/_generated", type=Path)
    ap.add_argument("--internal", action="store_true")
    a = ap.parse_args()
    for name, p in run(a.out, a.internal).items():
        print(f"wrote {p}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 통과 확인 + 실제 생성**

```bash
./venv/Scripts/python.exe -m pytest tests/test_extract_all.py -v
./venv/Scripts/python.exe -m tools.extract --out spec/_generated
```

Expected: 3 passed; `spec/_generated/` 에 4개 JSON.

- [ ] **Step 5: 커밋**

`_generated/*.json` 은 공개판이므로 커밋한다(단독 클론에서 소스 repo 없이도 빌드 가능해야 한다).

```bash
git add tools/extract/__main__.py tests/test_extract_all.py spec/_generated
git commit -m "Write the generated tables into spec/_generated"
```

---

### Task 7: 렌더러 — Markdown + 표 → 단일 HTML

**Files:**
- Create: `CFS-SUITE-PROTOCOL/tools/render.py`
- Create: `CFS-SUITE-PROTOCOL/spec/assets/page.html.j2`
- Create: `CFS-SUITE-PROTOCOL/spec/assets/style.css`
- Test: `CFS-SUITE-PROTOCOL/tests/test_render.py`

**Interfaces:**
- Consumes: `spec/_generated/*.json`
- Produces: `render.render_page(lang: str, md_text: str, gen: dict, *, for_print: bool) -> str`, `render.LANG_FONTS: dict[str,str]`

산문 안에 `{{table:opcodes:core}}` 같은 자리표를 두면 렌더러가 생성 표로 바꾼다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_render.py`:

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_render.py -v`
Expected: FAIL — `No module named 'tools.render'`

- [ ] **Step 3: 구현**

`tools/render.py`:

```python
"""Markdown + generated tables -> one HTML page.

The same page is both the website body and the PDF source, so nothing is
written twice. Prose carries {{table:...}} placeholders; every table comes
from spec/_generated so the three language editions cannot drift apart.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import markdown
from jinja2 import Template

ASSETS = Path(__file__).resolve().parent.parent / "spec" / "assets"

LANG_FONTS = {
    "en": '"Segoe UI", Arial, Helvetica, sans-serif',
    "ko": '"Noto Sans KR", "Malgun Gothic", sans-serif',
    "zh": '"Microsoft YaHei", "Noto Sans SC", sans-serif',
}

LANG_TITLE = {
    "en": "Celfras Standard Protocol",
    "ko": "Celfras Standard Protocol",
    "zh": "Celfras Standard Protocol",
}

_PLACEHOLDER = re.compile(r"\{\{table:([a-z_]+)(?::([a-z_0-9]+))?\}\}")


class UnknownTable(Exception):
    """A {{table:...}} placeholder names something not generated."""


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>"
        for r in rows
    )
    return f'<div class="tw"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _build_table(kind: str, arg: str | None, gen: dict) -> str:
    if kind == "opcodes":
        cmds = gen["opcodes"]["commands"]
        if arg:
            cmds = [c for c in cmds if c["group"] == arg]
            if not cmds:
                raise UnknownTable(f"no commands in group {arg!r}")
        return _table(
            ["ID", "Name", "Request", "Response", "Notes"],
            [[f"0x{c['id']:02X}", c["name"], c["req"], c["resp"], c["note"]] for c in cmds],
        )
    if kind == "errors":
        return _table(["Code", "Name", "Meaning"],
                      [[f"0x{e['code']:02X}", e["name"], e["note"]]
                       for e in gen["opcodes"]["errors"]])
    if kind == "op_modes":
        return _table(["Value", "Name", "Meaning"],
                      [[f"0x{m['value']:02X}", m["name"], m["note"]]
                       for m in gen["opcodes"]["op_modes"]])
    if kind == "bridge":
        return _table(["ID", "Name", "Notes"],
                      [[f"0x{c['id']:02X}", c["name"], c["note"]]
                       for c in gen["bridge"]["commands"]])
    if kind in ("par", "var"):
        width = arg or ("par16" if kind == "par" else "var8")
        rows_src = gen["varpar"][kind].get(width)
        if rows_src is None:
            raise UnknownTable(f"no {kind} width {width!r}")
        internal = any("default" in r for r in rows_src)
        headers = ["ID", "Name", "Unit"] + (["Access"] if kind == "par" else [])
        if internal:
            headers.append("Default")
        rows = []
        for r in rows_src:
            row = [r["id"], r["name"], r.get("unit", "")]
            if kind == "par":
                row.append(r.get("access", ""))
            if internal:
                row.append(r.get("default", ""))
            rows.append(row)
        return _table(headers, rows)
    raise UnknownTable(f"unknown table kind {kind!r}")


def expand_tables(md_text: str, gen: dict) -> str:
    def sub(m: re.Match[str]) -> str:
        return _build_table(m.group(1), m.group(2), gen)

    return _PLACEHOLDER.sub(sub, md_text)


def render_page(lang: str, md_text: str, gen: dict, *, for_print: bool) -> str:
    body = markdown.markdown(
        expand_tables(md_text, gen),
        extensions=["tables", "fenced_code", "toc", "attr_list"],
    )
    tpl = Template((ASSETS / "page.html.j2").read_text(encoding="utf-8"))
    return tpl.render(
        lang=lang,
        font_stack=LANG_FONTS[lang],
        title=LANG_TITLE[lang],
        version=gen["version"]["cmd_set_version"],
        edition=gen["version"]["edition"],
        body=body,
        for_print=for_print,
        css=(ASSETS / "style.css").read_text(encoding="utf-8"),
    )
```

- [ ] **Step 4: 템플릿과 스타일 작성**

`spec/assets/page.html.j2`:

```html
<!doctype html>
<html lang="{{ lang }}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} V{{ version }}</title>
<style>
:root { --font-body: {{ font_stack }}; }
{{ css }}
</style>
</head>
<body class="{{ 'print' if for_print else 'web' }}">
{% if for_print %}
<section class="cover">
  <h1>{{ title }}</h1>
  <p class="ver">V{{ version }}</p>
  {% if edition == 'internal' %}<p class="badge-internal">INTERNAL — NOT FOR DISTRIBUTION</p>{% endif %}
</section>
{% endif %}
<main>{{ body }}</main>
</body>
</html>
```

`spec/assets/style.css` — 아래가 전부다. 그대로 쓰면 웹과 인쇄 양쪽이 나온다:

```css
@page { size: A4; margin: 20mm 16mm 18mm; }
body { font-family: var(--font-body); font-size: 10.5pt; line-height: 1.55;
       color: #1b1b1b; margin: 0; }
main { max-width: 52rem; margin: 0 auto; padding: 0 1rem 4rem; }
h1, h2, h3 { line-height: 1.25; }
h2 { border-bottom: 1px solid #ddd; padding-bottom: .3rem; margin-top: 2.2rem; }
code, pre { font-family: Consolas, "Cascadia Mono", monospace; font-size: .92em; }
pre { background: #f6f7f9; padding: .8rem 1rem; border-radius: 4px;
      overflow-x: auto; }
.tw { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: .9em; }
th, td { border: 1px solid #d0d4da; padding: .35rem .6rem;
         text-align: left; vertical-align: top; }
th { background: #f2f4f7; }
tr, table { page-break-inside: auto; }
h2, h3 { page-break-after: avoid; }
.cover { page-break-after: always; padding-top: 32vh; text-align: center; }
.cover h1 { font-size: 2.4rem; margin: 0; }
.cover .ver { font-size: 1.3rem; color: #555; }
.badge-internal { margin-top: 2rem; color: #a1160a; font-weight: 700;
                  letter-spacing: .06em; }
body.print .web-only { display: none; }
```

- [ ] **Step 5: 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_render.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: 커밋**

```bash
git add tools/render.py spec/assets tests/test_render.py
git commit -m "Render markdown plus generated tables into one page"
```

---

### Task 8: PDF 생성기 — Chrome 헤드리스

**Files:**
- Create: `CFS-SUITE-PROTOCOL/tools/pdf.py`
- Test: `CFS-SUITE-PROTOCOL/tests/test_pdf.py`

**Interfaces:**
- Consumes: `render.render_page`
- Produces: `pdf.html_to_pdf(html_text: str, out_path: Path) -> Path`, `pdf.find_browser() -> Path`, `pdf.BrowserMissing(Exception)`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_pdf.py`:

```python
from pathlib import Path

import pypdf
import pytest

from tools import pdf

CJK_PAGE = """<!doctype html><meta charset="utf-8">
<style>@page{size:A4;margin:18mm}
body{font-family:"Microsoft YaHei","Noto Sans SC",sans-serif}</style>
<h1>Celfras Standard Protocol V2.11.0</h1>
<p>帧格式与校验和</p><p>프레임 포맷과 체크섬</p>"""


def test_browser_is_found():
    assert pdf.find_browser().exists()


def test_produces_a_readable_pdf(tmp_path: Path):
    out = pdf.html_to_pdf(CJK_PAGE, tmp_path / "t.pdf")
    assert out.exists() and out.stat().st_size > 5000
    r = pypdf.PdfReader(str(out))
    assert len(r.pages) >= 1
    text = r.pages[0].extract_text()
    assert "Celfras Standard Protocol V2.11.0" in text
```

> `pypdf` 를 dev 의존성에 추가한다: `./venv/Scripts/python.exe -m pip install pypdf` 및 `requirements.txt` 에 `pypdf>=5.0`.

- [ ] **Step 2: 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_pdf.py -v`
Expected: FAIL — `No module named 'tools.pdf'`

- [ ] **Step 3: 구현**

`tools/pdf.py`:

```python
"""HTML -> PDF via headless Chrome.

Chrome/Edge ship with Windows and carry the CJK fonts already installed, so
this needs no toolchain install (no pandoc, no LaTeX, no GTK). The page is
written to a temp file rather than piped, because --print-to-pdf only takes
a URL.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]


class BrowserMissing(Exception):
    """No Chrome or Edge to print with."""


def find_browser() -> Path:
    for p in _CANDIDATES:
        if p.exists():
            return p
    raise BrowserMissing(
        "need Chrome or Edge for --print-to-pdf; looked in:\n  "
        + "\n  ".join(str(p) for p in _CANDIDATES)
    )


def html_to_pdf(html_text: str, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "page.html"
        src.write_text(html_text, encoding="utf-8")
        subprocess.run(
            [
                str(find_browser()),
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--no-pdf-header-footer",
                f"--print-to-pdf={out_path}",
                src.as_uri(),
            ],
            check=True, capture_output=True, timeout=120,
        )
    if not out_path.exists():
        raise RuntimeError(f"browser produced no file at {out_path}")
    return out_path
```

- [ ] **Step 4: 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_pdf.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add tools/pdf.py tests/test_pdf.py requirements.txt
git commit -m "Print pages with headless Chrome, no toolchain install"
```

---

### Task 9: 빌드 CLI 와 누출 게이트

공개 경계를 습관이 아니라 **테스트**로 강제한다.

**Files:**
- Create: `CFS-SUITE-PROTOCOL/tools/build.py`
- Test: `CFS-SUITE-PROTOCOL/tests/test_public_leak.py`

**Interfaces:**
- Consumes: `extract.__main__.run`, `render.render_page`, `pdf.html_to_pdf`
- Produces: `build.build(internal: bool = False, out_root: Path | None = None, langs: tuple[str,...] = ("en","ko","zh")) -> dict` — 반환 `{"version": str, "edition": str, "pdfs": dict[str,Path], "site": dict[str,Path]}`; `build.PDF_NAME_FMT = "Celfras Standard Protocol V{ver} ({LANG}).pdf"`; `build.forbidden_public_values() -> set[int]` (derived from the source, never hand-written)
- `out_root` 는 **모든** 산출물의 뿌리다(테스트가 `tmp_path` 를 주면 repo 를 건드리지 않는다). 기본값은 repo 루트 → PDF `out/<edition>/`, 사이트 `site/`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_public_leak.py`:

```python
import re

import pypdf
import pytest

from tools import build


@pytest.fixture(scope="module")
def public_build(tmp_path_factory):
    return build.build(internal=False, out_root=tmp_path_factory.mktemp("pub"))


def _pdf_text(p):
    return "\n".join(pg.extract_text() or "" for pg in pypdf.PdfReader(str(p)).pages)


def test_all_three_languages_are_built(public_build):
    assert set(public_build["pdfs"]) == {"en", "ko", "zh"}
    for p in public_build["pdfs"].values():
        assert p.exists()


def test_filename_carries_the_cmd_set_version(public_build):
    for lang, p in public_build["pdfs"].items():
        assert p.name.startswith("Celfras Standard Protocol V2.11.0 (")
        assert p.name.endswith(f"({lang.upper()}).pdf")


def test_no_product_threshold_leaks_into_public_pdfs(public_build):
    """The public edition defines what an id means, never what this product
    writes into it. A bare number here is a leak."""
    for lang, p in public_build["pdfs"].items():
        text = _pdf_text(p)
        for value in build.forbidden_public_values():
            assert not re.search(rf"(?<![\d.]){value}(?![\d.])", text), (
                f"{value} leaked into the {lang} public PDF"
            )


def test_no_product_threshold_leaks_into_the_site(public_build):
    for p in public_build["site"].values():
        text = p.read_text(encoding="utf-8")
        for value in build.forbidden_public_values():
            assert not re.search(rf"(?<![\d.]){value}(?![\d.])", text), (
                f"{value} leaked into {p.name}"
            )


def test_internal_edition_is_marked_and_kept_apart(tmp_path):
    got = build.build(internal=True, out_root=tmp_path)
    for p in got["pdfs"].values():
        assert "internal" in str(p.parent).replace("\\", "/")
        assert "INTERNAL" in _pdf_text(p)
```

> 금지 값은 `1000`·`2000`·`300` 처럼 본문 산문에도 자연스럽게 나올 수 있는 숫자다.
> Task 11-13 에서 산문을 쓸 때 그 숫자를 쓰지 말 것 — 예를 들어 baud 는 `1 Mbaud`,
> ring buffer 는 `RB_SIZE` 로 적는다. 이 테스트가 그것을 강제한다.

- [ ] **Step 2: 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_public_leak.py -v`
Expected: FAIL — `No module named 'tools.build'`

- [ ] **Step 3: 구현**

`tools/build.py`:

```python
"""Build the public (and, on request, internal) editions.

Public output goes to out/public and is committed; internal output goes to
out/internal, which .gitignore holds, so the edition carrying product values
cannot reach the public repository by habit or by accident.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from tools import pdf, render
from tools.extract import __main__ as extract_all

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "spec"
LANGS = ("en", "ko", "zh")

PDF_NAME_FMT = "Celfras Standard Protocol V{ver} ({LANG}).pdf"

def forbidden_public_values() -> set[int]:
    """Every value the product bakes in, read from the source.

    Deliberately not a literal tuple. The hand-written one in this plan's
    first draft was already wrong -- it missed CHG_TIMEOUT_TH (600) and
    LONG_PUFF_TH (10000). Deriving it means a new default in par_map.json
    joins the gate on its own.
    """
    from tools.extract import varpar
    return {r["default"]
            for rows in varpar.extract(internal=True)["par"].values()
            for r in rows if "default" in r}


def _load_generated(gen_dir: Path) -> dict:
    return {p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(gen_dir.glob("*.json"))}


def build(internal: bool = False, out_root: Path | None = None,
          langs: tuple[str, ...] = LANGS) -> dict:
    # out_root is the root of every artefact, so a test can hand it a
    # tmp_path and leave the repository untouched.
    out_root = out_root or ROOT
    edition = "internal" if internal else "public"

    # The public generated tables are committed, so a standalone clone can
    # build without the product repos present. The internal ones never are --
    # and they must land somewhere .gitignore already covers. Writing them to
    # out_root/"_generated" would put product defaults in a TOP-LEVEL
    # _generated/ that no ignore rule matches, one `git add -A` from being
    # published. Nest them under out/<edition>/ so the existing
    # `out/internal/` rule holds them.
    gen_dir = (SPEC / "_generated") if (not internal and out_root == ROOT) \
        else (out_root / "out" / edition / "_generated")
    extract_all.run(gen_dir, internal=internal)
    gen = _load_generated(gen_dir)
    ver = gen["version"]["cmd_set_version"]

    pdf_dir = out_root / "out" / edition
    site_dir = out_root / "site"
    site_dir.mkdir(parents=True, exist_ok=True)

    pdfs: dict[str, Path] = {}
    site: dict[str, Path] = {}
    for lang in langs:
        md = (SPEC / f"{lang}.md").read_text(encoding="utf-8")
        page = render.render_page(lang, md, gen, for_print=False)
        sp = site_dir / f"{lang}.html"
        sp.write_text(page, encoding="utf-8")
        site[lang] = sp

        printable = render.render_page(lang, md, gen, for_print=True)
        name = PDF_NAME_FMT.format(ver=ver, LANG=lang.upper())
        pdfs[lang] = pdf.html_to_pdf(printable, pdf_dir / name)

    if not internal:
        dl = site_dir / "downloads"
        dl.mkdir(exist_ok=True)
        for p in pdfs.values():
            shutil.copy2(p, dl / p.name)

    return {"version": ver, "edition": edition, "pdfs": pdfs, "site": site}


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the Celfras Standard Protocol document")
    ap.add_argument("--internal", action="store_true",
                    help="include product default values; output stays out of git")
    a = ap.parse_args()
    got = build(internal=a.internal)
    print(f"{got['edition']} edition V{got['version']}")
    for lang, p in got["pdfs"].items():
        print(f"  {lang}: {p}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 통과 확인**

Task 11-13 의 산문이 아직 없으므로 `spec/{en,ko,zh}.md` 에 최소 스텁을 먼저 둔다:

```bash
for l in en ko zh; do printf '# Celfras Standard Protocol\n\n{{table:errors}}\n' > spec/$l.md; done
./venv/Scripts/python.exe -m pytest tests/test_public_leak.py -v
```

Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add tools/build.py tests/test_public_leak.py spec/en.md spec/ko.md spec/zh.md
git commit -m "Build both editions, and fail the build on a value leak"
```

---

### Task 10: 웹사이트 셸 — 언어 스위처와 다운로드

**Files:**
- Create: `CFS-SUITE-PROTOCOL/spec/assets/index.html.j2`
- Create: `CFS-SUITE-PROTOCOL/examples/README.md`
- Modify: `CFS-SUITE-PROTOCOL/tools/build.py` (`_write_index()` 추가, `build()` 끝에서 호출)
- Test: `CFS-SUITE-PROTOCOL/tests/test_site.py`

**Interfaces:**
- Produces: `build._write_index(site_dir: Path, ver: str, pdfs: dict[str, Path]) -> Path`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_site.py`:

```python
from tools import build


def test_index_links_every_language_and_pdf(tmp_path):
    got = build.build(internal=False, out_root=tmp_path)
    index = (got["site"]["en"].parent / "index.html").read_text(encoding="utf-8")
    for lang in ("en", "ko", "zh"):
        assert f'href="{lang}.html"' in index
    for p in got["pdfs"].values():
        assert p.name in index


def test_examples_slot_is_present_but_not_yet_a_link(tmp_path):
    got = build.build(internal=False, out_root=tmp_path)
    index = (got["site"]["en"].parent / "index.html").read_text(encoding="utf-8")
    assert "example" in index.lower()
    assert 'class="pending"' in index
```

- [ ] **Step 2: 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_site.py -v`
Expected: FAIL — index.html 없음

- [ ] **Step 3: 템플릿 작성**

`spec/assets/index.html.j2`:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Celfras Standard Protocol V{{ ver }}</title>
<style>{{ css }}</style>
</head>
<body class="web">
<main>
  <h1>Celfras Standard Protocol</h1>
  <p class="ver">Version {{ ver }} &mdash; command set {{ ver }}</p>

  <h2>Read</h2>
  <ul class="langs">
    <li><a href="en.html">English</a></li>
    <li><a href="ko.html">한국어</a></li>
    <li><a href="zh.html">中文</a></li>
  </ul>

  <h2>Download</h2>
  <ul class="downloads">
    {% for lang, name in pdf_names %}
    <li><a href="downloads/{{ name|urlencode }}">{{ name }}</a></li>
    {% endfor %}
    <li class="pending">
      Reference implementation &mdash; DUT firmware command-set handler
      <span class="badge">coming soon</span>
      <p class="hint">A portable core (COBS, CRC16, frame dispatch) plus one
      buildable example project. Being optimised and bench-verified first.</p>
    </li>
  </ul>
</main>
</body>
</html>
```

- [ ] **Step 4: `build.py` 에 index 작성 추가**

`tools/build.py` 의 `import` 아래에 추가:

```python
from jinja2 import Template
```

`build()` 의 `if not internal:` 블록 안, `shutil.copy2` 루프 뒤에 추가:

```python
        _write_index(site_dir, ver, pdfs)
```

그리고 모듈 끝에 함수 추가:

```python
def _write_index(site_dir: Path, ver: str, pdfs: dict[str, Path]) -> Path:
    tpl = Template((SPEC / "assets" / "index.html.j2").read_text(encoding="utf-8"))
    out = site_dir / "index.html"
    out.write_text(
        tpl.render(
            ver=ver,
            pdf_names=[(lang, p.name) for lang, p in sorted(pdfs.items())],
            css=(SPEC / "assets" / "style.css").read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )
    return out
```

- [ ] **Step 5: `examples/README.md` 작성**

```markdown
# Reference implementation — coming soon

The DUT-side command-set handler will be published here: a portable core
(COBS framing, CRC16-CCITT-FALSE, frame dispatch) that needs only a byte
put/get from your UART, plus one buildable example project.

It is being optimised and bench-verified first, then restructured to match
the CFS-ECIG-SUITE layer conventions (`drv_*` / `svc_*` / `app_*`) so it
reads the same way as the rest of the platform.
```

- [ ] **Step 6: 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_site.py tests/test_public_leak.py -v`
Expected: PASS (8 passed)

- [ ] **Step 7: 커밋**

```bash
git add spec/assets/index.html.j2 tools/build.py examples/README.md tests/test_site.py
git commit -m "Site shell: language switcher, downloads, and a slot for the example code"
```

---

### Task 11: Part I 본문 (영문)

여기부터는 산문이다. 표는 자리표로만 넣고 절대 손으로 쓰지 않는다.

**Files:**
- Modify: `CFS-SUITE-PROTOCOL/spec/en.md` (스텁을 본문으로 대체)

**Interfaces:**
- Consumes: 자리표 `{{table:opcodes:core}}`, `{{table:opcodes:log}}`, `{{table:opcodes:burst}}`, `{{table:opcodes:var_par}}`, `{{table:errors}}`, `{{table:op_modes}}`

- [ ] **Step 1: 절 구조를 스펙 §4 그대로 작성**

`spec/en.md` 에 Part I 1-10 절. 각 절에 담을 사실은 아래에서 가져온다 — **모두 확인된 값이다**:

| 절 | 내용 | 출처 |
|---|---|---|
| 2 전송 | USART, 8N1, no flow control, 1 Mbaud. 백엔드(DMA/IT)는 구현 자유 — 표준 아님 | `FW/Doc/PROTOCOL.md` §1, 단 IT 서술은 stale 이므로 옮기지 말 것 |
| 3 프레임 | `[LEN16_LE][CMD8][SEQ8][PAYLOAD...][CRC16_LE]`, COBS 프레이밍, LEN = CMD+SEQ+payload+CRC | `PROTOCOL.md` §2 |
| 3 CRC | CRC16-CCITT-FALSE: poly `0x1021`, init `0xFFFF`, no reflect, no xorout | `FW/App/Src/app_crc16.c` |
| 3 SEQ | 요청의 seq 를 응답이 에코. 비요청(fw→host) 프레임은 seq=0 | `PROTOCOL.md` §5·§6 |
| 4 응답 | 응답 payload 는 항상 `[STATUS8][DATA...]`. `0x00` OK / `0x01` ERR(`DATA[0]` = 오류 코드) / `0x02` ERR2 — **정의돼 있으나 아무도 보내지 않는다**, 수신측은 받을 수 있게 둘 것 | `PROTOCOL.md` §2, bridge `commands.py:26-27` |
| 4 오류표 | `{{table:errors}}` — **코어 공간은 `0x00`-`0x0F` 뿐이다** | 생성 |
| 4 오류 확장 | `0x10` 이상은 계층별 확장 공간이고 코어가 정의하지 않는다. 브릿지가 SWD(`0x11`-`0x15`)·플래시(`0x20`,`0x21`,`0xE1`)·업데이트(`0x30`-`0x35`)를 쓴다. 제품은 코어 코드를 재정의하지 말고 `0x10` 이상에서 자기 것을 잡는다 | `app_proto.h:41-46` vs bridge `commands.py:30-60` |
| 5 모드표 | `{{table:op_modes}}` | 생성 |
| 5 모드 규칙 | NORMAL 에서는 PING/INFO/SET_MODE/DBG_ONLINE/RESET 만 처리 | `app_proto.h:84-105` |
| 6 코어 명령 | `{{table:opcodes:core}}` + `{{table:opcodes:device}}` | 생성 |
| 7 로그/버스트 | `{{table:opcodes:log}}` `{{table:opcodes:burst}}` + 핸드셰이크 서술 | `PROTOCOL.md` §5·§6 |
| 8 VAR/PAR | `{{table:opcodes:var_par}}` + "id 맵은 제품이 정의한다" | `PROTOCOL.md` §7 |
| 9 확장 | 미할당 opcode 는 `[ERR][ERR_BAD_ARGS]`. 0xC0+ 는 브릿지 예약 — 제품이 쓰면 안 됨 | `app_proto.h:59`, bridge `commands.py:173` |
| 10 적합성 | 체크리스트 | 신규 |

> **`PROTOCOL.md` §2 의 오류 코드 표를 그대로 베끼지 말 것.** 그 표는 `ERR_I2C_WRITE 0x30`
> 등 `app_proto.h` 가 정의하지 않는 코드를 싣고 있고, 같은 `0x30` 을 브릿지는
> `ERR_UPD_STATE` 로 쓴다. 코어 표는 생성물(`{{table:errors}}`, `app_proto.h` 에서
> 추출)만 쓰고, 그 위는 "계층이 정의하는 확장 공간"으로 서술한다. 이것이 표를 손으로
> 쓰지 않는 이유의 실례다.

- [ ] **Step 2: CRC 시험 벡터를 실제로 계산해 넣을 것**

```bash
./venv/Scripts/python.exe -c "
def crc16(d):
    c=0xFFFF
    for b in d:
        c^=b<<8
        for _ in range(8):
            c=((c<<1)^0x1021)&0xFFFF if c&0x8000 else (c<<1)&0xFFFF
    return c
for s in (b'123456789', bytes([0x01,0x00]), b''):
    print(s, hex(crc16(s)))
"
```

출력된 값을 문서에 그대로 싣는다(`b'123456789'` → `0x29B1` 이면 CCITT-FALSE 가 맞다는 표준 확인값).

- [ ] **Step 3: 완전한 프레임 예제 하나를 계산해 싣기**

`CMD_PING` 요청을 LEN/CRC/COBS 까지 실제 바이트로 계산해 문서에 표로 싣는다. 아래를 그대로 돌려 나온 값을 쓴다 — 스크립트는 repo 에 남기지 않는다(일회성).

```bash
./venv/Scripts/python.exe - <<'PY'
def crc16(d):
    c = 0xFFFF
    for b in d:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return c

def cobs(d):
    out, code, buf = bytearray(), 1, bytearray()
    for b in d:
        if b:
            buf.append(b); code += 1
            if code < 0xFF: continue
        out.append(code); out += buf; code, buf = 1, bytearray()
    out.append(code); out += buf
    return bytes(out)

CMD_PING, seq, payload = 0x01, 0x07, b""
length = 1 + 1 + len(payload) + 2                 # CMD + SEQ + payload + CRC
body = bytes([length & 0xFF, length >> 8, CMD_PING, seq]) + payload
frame = body + crc16(body).to_bytes(2, "little")  # CRC over everything before it
print("raw  ", frame.hex(" ").upper())
print("cobs ", cobs(frame).hex(" ").upper(), "00   <- delimiter")
PY
```

문서에는 `raw` 와 `cobs` 두 줄을 바이트 표로 옮기고, 각 바이트가 어느 필드인지 주석을 붙인다. **CRC 가 무엇을 덮는지**(LEN 포함, CRC 자신 제외)를 이 예제로 못박는다 — 구현자가 가장 자주 틀리는 지점이다.

- [ ] **Step 4: 금지 숫자 회피 확인**

`300`, `350`, `600`, `1000`, `2000`, `3400`, `8000`, `10000`, `180000` 을 본문에 쓰지 않는다.
baud 는 `1 Mbaud`, 그 외는 심볼 이름으로. **이 아홉 개를 외우지 말고** 아래로 확인할 것 —
목록은 소스에서 자란다:

```bash
./venv/Scripts/python.exe -c "from tools import build; print(sorted(build.forbidden_public_values()))"
```

- [ ] **Step 5: 빌드와 누출 검사**

Run: `./venv/Scripts/python.exe -m pytest tests/ -v && ./venv/Scripts/python.exe -m tools.build`
Expected: 전부 PASS, `out/public/Celfras Standard Protocol V2.11.0 (EN).pdf` 생성

- [ ] **Step 6: 커밋**

```bash
git add spec/en.md
git commit -m "Part I: the core standard, in English"
```

---

### Task 12: Part II 부록 (영문)

**Files:**
- Modify: `CFS-SUITE-PROTOCOL/spec/en.md` (Part II 추가)

- [ ] **Step 1: 부록 A — ECIG var/par**

자리표: `{{table:var:var8}}` `{{table:var:var16}}` `{{table:var:var32}}` `{{table:par:par8}}` `{{table:par:par16}}` `{{table:par:par32}}`

산문으로 덧붙일 것:
- `par_id` 번호는 **제품마다 독립**이다. 다른 보드에 그대로 쓰면 다른 `g_param` 필드에 SET 이 꽂히고 펌웨어는 OK 로 답한다 — 프로토콜 차원에서 잡을 방법이 없다. (출처: `conf/par_map.json` `_readme`)
- 쓰기 가능한 par 슬롯은 `TUNING_PHASE` 빌드에서만 열린다. 릴리스 빌드에서는 `g_param` 이 `const` 가 되고 전부 `ERR_BAD_ARGS`. (출처: 같은 `_readme`)
- `EXT_CTRL_STATUS`/`EXT_HEATING_PWM_DUTY`/`EXT_HEATING_POWER` 는 **"외부 제어 인터페이스. 상세는 제품 문서 참조."** 한 줄로만 둔다 — 구동 절차를 적지 않는다.

- [ ] **Step 2: 부록 B — CVS-BP2601 차이**

`FW/Doc/PROTOCOL.md` §9 의 한 건만 옮긴다: BP2601 의 `CMD_SET_MODE` 는 `log_enable` 을 건드리지 않고, ECIG 는 NORMAL/DEBUG 에서 `log_enable` 을 0/1 로 강제한다. **BP2601 소스를 새로 열지 않는다.**

- [ ] **Step 3: 부록 C — 브릿지 대역**

`{{table:bridge}}` + "브릿지는 0xC0 이상을 자기가 답하고 그 아래는 손대지 않고 전달한다. 제품은 0xC0 이상을 쓰면 안 된다."

- [ ] **Step 4: 부록 D — DUT 테스트 FW**

세 칩(`cwm2032`/`cwm1016`/`cwm0508`)에 각각 작은 빌드가 있고 같은 CMD_SET 을 선언한다는 사실만. 핀맵·벤치 세부는 넣지 않는다.

- [ ] **Step 5: 부록 E — 변경 이력**

CMD_SET 버전별 한 줄씩. 확인된 것: `2.10.0` = `CMD_FLASH_READ_EX` 추가, `2.11.0` = 현재. 그 이전은 `CFS-SUITE-BRIDGE` 의 커밋 로그에서 확인해 채운다:

```bash
git -C "D:/BaiduSyncdisk/Company/LianZhi/Project/CFS-SUITE-BRIDGE" log --oneline --all -S"CMD_SET_VERSION" -- pc_app/cfsbridge/commands.py | head -20
```

- [ ] **Step 6: 빌드와 누출 검사**

Run: `./venv/Scripts/python.exe -m pytest tests/ -v && ./venv/Scripts/python.exe -m tools.build`
Expected: 전부 PASS. **특히 `test_no_product_threshold_leaks_into_public_pdfs` 가 통과해야 한다** — 부록 A 가 들어온 뒤의 첫 진짜 시험이다.

- [ ] **Step 7: 사내판도 한 번 돌려 볼 것**

Run: `./venv/Scripts/python.exe -m tools.build --internal`
Expected: `out/internal/` 에 3벌, 표지에 `INTERNAL — NOT FOR DISTRIBUTION`, par16 표에 `Default` 열.

```bash
git status --short   # out/internal/ 이 나타나면 안 된다
```

- [ ] **Step 8: 커밋**

```bash
git add spec/en.md
git commit -m "Part II: per-product appendices, structure without product values"
```

---

### Task 13: 한국어판

**Files:**
- Modify: `CFS-SUITE-PROTOCOL/spec/ko.md`

- [ ] **Step 1: `en.md` 의 절 구조와 자리표를 그대로 두고 산문만 번역**

자리표는 **한 글자도 바꾸지 않는다** — 표는 생성물이라 3개 언어가 같은 것을 공유한다.
심볼 이름(`CMD_PING`, `ERR_BAD_ARGS`, `OPMODE_NORMAL`)은 번역하지 않는다.

- [ ] **Step 2: 절 개수와 자리표 개수가 en 과 일치하는지 확인**

```bash
./venv/Scripts/python.exe -c "
import re
for l in ('en','ko'):
    t=open(f'spec/{l}.md',encoding='utf-8').read()
    print(l, 'headings', len(re.findall(r'^#{1,3} ',t,re.M)),
          'tables', sorted(re.findall(r'\{\{table:[^}]+\}\}',t)))
"
```

Expected: 두 줄의 `headings` 수와 `tables` 목록이 동일.

- [ ] **Step 3: 빌드 + 조판 확인**

```bash
./venv/Scripts/python.exe -m tools.build
```

생성된 `out/public/Celfras Standard Protocol V2.11.0 (KO).pdf` 를 열어 한글이 깨지지 않는지, 표가 페이지 밖으로 넘치지 않는지 눈으로 확인한다.

- [ ] **Step 4: 커밋**

```bash
git add spec/ko.md
git commit -m "Korean edition"
```

---

### Task 14: 중국어판

**Files:**
- Modify: `CFS-SUITE-PROTOCOL/spec/zh.md`

- [ ] **Step 1: 간체 중문으로 번역** — Task 13 의 규칙 동일(자리표·심볼 불변)

- [ ] **Step 2: 절/자리표 일치 확인** (Task 13 Step 2 의 스크립트에 `'zh'` 추가)

- [ ] **Step 3: 한자 글리프 확인**

```bash
./venv/Scripts/python.exe -m tools.build
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -c "
import pypdf,unicodedata
r=pypdf.PdfReader('out/public/Celfras Standard Protocol V2.11.0 (ZH).pdf')
t=''.join(p.extract_text() or '' for p in r.pages)
bad=[c for c in set(t) if 0x2F00<=ord(c)<=0x2FDF]
print('Kangxi radicals found:', bad)
assert not bad, 'font fallback picked radical glyphs -- check the zh font stack'
print('OK')
"
```

Expected: `Kangxi radicals found: []` / `OK`.
실패하면 `render.LANG_FONTS['zh']` 에서 `"Microsoft YaHei"` 가 맨 앞인지 확인한다.

- [ ] **Step 4: 커밋**

```bash
git add spec/zh.md
git commit -m "Chinese edition"
```

---

### Task 15: README, CLAUDE.md, 그리고 갱신 규칙 심기

**Files:**
- Create: `CFS-SUITE-PROTOCOL/README.md`
- Create: `CFS-SUITE-PROTOCOL/CLAUDE.md`
- Create: `CFS-SUITE-PROTOCOL/docs/superpowers/specs/2026-09-10-celfras-standard-protocol-doc-design.md` (루트에서 복사)
- Create: `CFS-SUITE-PROTOCOL/docs/superpowers/plans/2026-09-10-celfras-standard-protocol-doc.md` (이 파일 복사)
- Modify: `CFS-ECIG-SUITE/CLAUDE.md`
- Modify: `CFS-ECIG-SUITE/FW/App/Inc/app_proto.h` (주석만)

- [ ] **Step 1: `README.md`**

무엇인지 / 어떻게 빌드하는지 / 공개판과 사내판이 왜 갈리는지 / 예제 코드는 나중.
`CMD_SET_VERSION` 을 **여기에 적지 않는다** — `VERSION` 파일과 빌드가 답한다.

- [ ] **Step 2: `CFS-SUITE-PROTOCOL/CLAUDE.md`**

담을 규칙:
- 표는 절대 손으로 쓰지 않는다. `spec/_generated` 에서 온다.
- 소스는 워킹 트리가 아니라 `HEAD` 에서 읽는다(이유 포함).
- 공개판 금지 값 목록과 `out/internal/` 이 gitignore 인 이유.
- 산문은 3개 언어가 절 구조와 자리표를 공유한다.
- 이 repo 는 CMD_SET 버전을 선언하지 않는다.

- [ ] **Step 3: 루트 `CLAUDE.md` 에 갱신 규칙 추가**

`CFS-ECIG-SUITE/CLAUDE.md` 의 Protocol 절 바로 뒤에 삽입:

```markdown
## 표준 프로토콜 문서 (MANDATORY — 2026-09-10 확정)

**CMD_SET 버전을 올리면 `CFS-SUITE-PROTOCOL` 의 문서를 함께 재생성한다.**

    cd ../CFS-SUITE-PROTOCOL && ./venv/Scripts/python.exe -m tools.build

산출물은 `Celfras Standard Protocol V<cmd_set>.pdf` 3벌(EN/KO/ZH)과 `site/`.

그 repo 는 **번호를 따로 들고 있지 않다** — 빌드가 이 repo 의 `app_proto.h`
에서 읽는다. 그래서 위의 사본 목록에 **넣지 않는다**. 대조 대상이 아니라 하위
산출물이고, 그 목록은 개수를 세는 용도라 오염시키면 안 된다.

재생성을 잊으면 사본은 전부 일치하는데 문서만 옛 opcode 표를 싣는다. 그것이
2.10.0 과 2.11.0 에서 실제로 일어난 일이고, 그래서 이 규칙이 있다. 문서 빌드는
세 repo 의 번호를 한꺼번에 대조하는 유일한 지점이라 어긋나면 빌드가 선다.

제품 실측값(보호 임계값, 드라이퍼프 임계값)은 공개판에 넣지 않는다 —
`--internal` 빌드에만 들어가고 그 산출물은 gitignore 된다.
```

- [ ] **Step 4: `app_proto.h` 주석 한 줄 — 목록 *밖*에**

`FW/App/Inc/app_proto.h` 의 사본 목록(`// pc_app's tests compare every one of them...` 줄) **뒤**에, 목록 항목이 아닌 별도 문단으로:

```c
// Not a copy of the number, and deliberately not on the list above: the
// standard protocol document (CFS-SUITE-PROTOCOL) reads this header at build
// time rather than declaring a version of its own. It still has to be
// regenerated when this number moves, or every copy agrees while the document
// ships an old opcode table -- which is what happened at 2.10.0 and 2.11.0.
// See the root CLAUDE.md.
```

> ECIG FW 는 frozen 이지만 cmd-set 부기는 허용된 편집이다. **주석만 바꾼다.**
> 편집은 worktree 규칙을 따른다:
> `git -C FW worktree add .claude/worktrees/2026-09-10-protocol-doc-note -b 2026-09-10-protocol-doc-note HEAD`

- [ ] **Step 5: 스펙·계획 문서 복사**

```bash
mkdir -p docs/superpowers/{specs,plans}
cp "../CFS-ECIG-SUITE/docs/superpowers/specs/2026-09-10-celfras-standard-protocol-doc-design.md" docs/superpowers/specs/
cp "../CFS-ECIG-SUITE/docs/superpowers/plans/2026-09-10-celfras-standard-protocol-doc.md" docs/superpowers/plans/
```

- [ ] **Step 6: 전체 테스트 + 빌드**

Run: `./venv/Scripts/python.exe -m pytest tests/ -v && ./venv/Scripts/python.exe -m tools.build`
Expected: 전부 PASS

- [ ] **Step 7: 커밋 (두 repo)**

```bash
# 문서 repo
git add README.md CLAUDE.md docs
git commit -m "Document the build, the editions, and why tables are generated"

# FW repo (worktree 에서)
git -C FW/.claude/worktrees/2026-09-10-protocol-doc-note commit -am \
  "Note the standard protocol document as a downstream artifact"
```

루트 `CLAUDE.md` 는 버전 관리 밖이므로 커밋 대상이 아니다(제자리 편집).

---

### Task 16: GitHub public repo 생성과 push

**Files:** 없음 (repo 작업)

- [ ] **Step 1: `gh` 설치 확인**

```bash
gh --version
```

없으면: `winget install --id GitHub.cli --accept-source-agreements --accept-package-agreements`
설치 후 새 셸이 필요할 수 있다(`PATH`).

- [ ] **Step 2: 로그인 — 사용자가 직접 실행**

대화형이라 에이전트가 할 수 없다. 사용자에게 요청:

```
! gh auth login
```

확인: `gh auth status`

- [ ] **Step 3: push 전에 무엇이 올라가는지 보여줄 것**

```bash
git ls-files | sort
echo "--- 금지 값 최종 확인 ---"
./venv/Scripts/python.exe -c "
from tools import build
import re, pathlib, subprocess
vals = build.forbidden_public_values()
pat = '|'.join(str(v) for v in sorted(vals))
print('checking for:', sorted(vals))
r = subprocess.run(['git','grep','-nE',f'(^|[^0-9.])({pat})([^0-9.]|\$)','--','spec','site','out'],
                   capture_output=True, text=True)
print(r.stdout or 'clean')
"
```

**사용자 확인을 받은 뒤에만 다음 단계로 간다.** public repo 이므로 되돌리기 어렵다.

- [ ] **Step 4: repo 생성과 push**

```bash
gh repo create CFS-SUITE-PROTOCOL --public --source=. --remote=origin \
  --description "Celfras Standard Protocol — UART command-set specification for the CFS-SUITE platform" \
  --push
```

- [ ] **Step 5: 확인**

```bash
gh repo view --web
git remote -v
git log --oneline -1
```

- [ ] **Step 6: `site/` 처분 결정**

`site/` 는 지금 `.gitignore` 에 있다. GitHub Pages 를 쓸 거면 빼야 하고, 사내 서버만 쓸 거면 그대로 둔다. **사용자에게 묻고 결정한다** — 스펙은 "호스팅은 나중에 사내 서버, 이번엔 계획만" 이므로 기본값은 **그대로 두기**다.

---

## 이번 범위에서 제외 (스펙 §10)

- ECIG `FW`/`pc_app` repo 통합 — frozen 해제 후 별건
- 예제 코드 실물 — `fw_dut` 기준 최적화·검증 후 ECIG-SUITE 구조로 이식
- 사내 서버 호스팅 구축
- `FW/Doc/PROTOCOL.md` 의 처분 — 새 문서가 자리를 잡은 뒤 결정
- 워킹 트리의 `conf/*.json` BP2601 덮어쓰기 — 벤치 작업 중이므로 건드리지 않는다
