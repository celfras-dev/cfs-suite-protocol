# Celfras Standard Protocol 문서 — 설계

작성 2026-09-10. 대상 CMD_SET **2.11.0**.

## 1. 배경과 문제

표준 프로토콜 문서는 이미 있다 — `CFS-ECIG-SUITE/FW/Doc/PROTOCOL.md` (828줄, v1.5,
2026-08-05 기준). 프레임 포맷부터 튜닝까지 10개 절로 충실하지만 네 가지가 걸린다.

1. **갱신이 멈췄다.** 그 뒤 CMD_SET이 2.10.0(`CMD_FLASH_READ_EX`) → 2.11.0 으로 두 번
   올랐는데 문서에 없다. 놓친 지점이 정확히 opcode 표 — 기계적으로 도출 가능한 부분이다.
2. **버전 축이 다르다.** 문서 스스로 "문서 버전(v1.5)은 CMD_SET 번호와 별개 축"이라고
   서두에 못박고 있다. 이번 요구(문서명 = CMD_SET 버전)와 정면으로 충돌한다.
3. **§1 Transport 가 stale.** IT 백엔드로 서술돼 있으나 shipping 은 DMA다.
4. **ECIG 전용 문서다.** §9가 "CVS-BP2601 과의 차이"인 형태 — 표준이 아니라 한 제품의
   문서이고, 브릿지·LIB-MCU 는 시야에 없다.

## 2. 산출물

- `Celfras Standard Protocol V2.11.0 (EN|KO|ZH).pdf` — 공개판 3벌
- 같은 내용의 정적 웹사이트 (언어 스위처 + 다운로드 섹션)
- 사내판 3벌 — 공개판 + 제품 실측값 (§5 참조)
- 예제 코드 자리 — 지금은 "준비 중" 배지. 코드는 나중에 `fw_dut` 기준으로 최적화·검증
  후 ECIG-SUITE 코드 구조에 맞춰 이식되면 떨어진다.
- 루트 `CLAUDE.md` 갱신 규칙 + `app_proto.h` 사본 목록 주석 한 줄

## 3. Repo 구조 결정

### 3.1 현황 (조사 결과)

| | 실제 구조 | remote |
|---|---|---|
| `CFS-SUITE-BRIDGE` | **단일 repo** — `fw/brd01`, `fw/brd02`, `fw_dut/*`, `pc_app/`, `hw/`, `ota_release/` | 없음 |
| `CFS-ECIG-SUITE` | **repo 2개** — `FW/`, `pc_app/` 각각 독립. 루트는 repo 아님 | 없음 |
| `LIB-MCU` | 단독 repo | 없음 |

브릿지 FW 와 pc_app 은 독립 repo가 아니다. 2026-09-01 에 `CFS-NANAODAP` +
`CFS-BRIDGE-CWM30C8` 을 하나로 합친 결과가 지금 형태다. **통합 실험은 이미 했고 결과가
좋았다.** 쪼개져 있는 쪽은 ECIG이며, 그 분리가 실제 비용을 내고 있다:

- 루트가 repo가 아니라서 `CLAUDE.md`·`PLATFORM_HANDOFF.md`·`docs/`·코딩 가이드라인이
  전부 버전 관리 밖이다. worktree 규칙의 "저장소 밖 파일은 제자리에서 편집한다" 예외
  조항이 이것 때문에 존재한다.
- CMD_SET 번호가 3개 repo 8곳에 있고, `app_proto.h` 주석이 직접 "두 테스트가 각각
  절반씩만 잡는다"고 적고 있다.

그리고 **어느 repo에도 remote 가 없다.** 이번이 이 프로젝트의 첫 원격이다.

### 3.2 결정

**① 지금 — 문서용 repo 1개 신설: `CFS-SUITE-PROTOCOL` (public)**

표준 문서는 ECIG·브릿지·LIB-MCU 어디에 넣어도 틀린다. 셋에 걸치는 계약이라 주인이 없다.
별도 repo는 "쪼개기"가 아니라 주인 없던 것에 집을 주는 일이다.

**② 다음 (별건) — ECIG 를 단일 repo 로 통합**

브릿지에서 검증된 형태 그대로. 루트 문서가 버전 관리에 들어오고 CMD_SET 대조가 한
테스트로 닫힌다. **이번 작업에 포함하지 않는다** — ECIG FW 가 frozen(BP2601 검증 대기)
이고 worktree 규칙이 repo 단위로 짜여 있다.

**③ 하지 않을 것 — 전부 하나의 대형 모노레포**

브릿지와 ECIG 는 다른 제품이고 릴리스 주기·`product_id` 가 다르다. brd02/brd03 을 분리
유지한 것과 같은 논리. 합쳐서 얻는 건 CMD_SET 대조 하나뿐인데 그건 ②가 해결한다.

### 3.3 버전 사본을 9개로 늘리지 않는다

문서 repo 는 CMD_SET 버전을 **선언하지 않는다.** 빌드가 옆 디렉터리
`CFS-ECIG-SUITE/FW/App/Inc/app_proto.h` 에서 읽어 파일명·표지에 찍는다. 단독 클론에서도
빌드되도록 도출값을 `VERSION` 파일로 커밋하고, 헤더에 닿을 수 있을 때는 대조해 어긋나면
빌드를 세운다. → `app_proto.h` 의 사본 목록에 **들어가지 않는다.** 사본이 아니라 하위
산출물이다.

## 4. 문서 구조

```
Part I — 코어 (모든 Celfras 제품이 지키는 것)
  1. 개요 / 적용 범위 / 준수 수준
  2. 전송 계층 (UART 8N1, 1 Mbaud, 백엔드 무관)
  3. 프레임 포맷 — COBS, [LEN16_LE][CMD8][SEQ8][PAYLOAD][CRC16_LE]
     CRC16-CCITT-FALSE 정의 + 시험 벡터, SEQ 규칙, 비요청 프레임 seq=0 관례
  4. 응답 규약 — [OK] / [ERR][err_code], 오류 코드 표
  5. 동작 모드 (NORMAL/DEBUG/TEST/PROG) 와 모드별 허용 명령
  6. 코어 명령 (0x01-0x05, 0x10)
  7. 로그 스트리밍 (0x30-0x32) / 바이너리 버스트 (0x40-0x42)
  8. VAR / PAR 접근 모델 (0x50-0x5B) — id 맵은 제품이 정의
  9. 확장 규칙 — 미할당 opcode, 0xC0+ 브릿지 예약 대역, 버전 규칙
 10. 적합성 체크리스트

Part II — 부록 (제품별 구현)
  A. CFS-ECIG-SUITE — var/par 맵, 튜닝 (0x70-0x74)
  B. CVS-BP2601 — 차이점
  C. CFS-SUITE-BRIDGE — 0xC0+ 대역
  D. DUT 테스트 FW
  E. 변경 이력 (CMD_SET 버전별)
```

Part I 이 표준이고 Part II 는 "이 표준을 이렇게 구현했다"다. 부록이 늘어도 Part I 은
흔들리지 않는다.

## 5. 공개 경계 — 값이 아니라 의미만

repo 는 public 이다. Part II 는 **구조는 싣고 실측값은 뺀다.**

```
공개  : par16 id 14 = DRY_PUFF_ABS_TEMP_TH, 단위 degC, 쓰기는 TUNING_PHASE 빌드에서만
비공개: default = 350
```

표준으로서 잃는 게 없다. 표준이 정의할 것은 "id 14 는 이 의미다"이지 "우리 제품은 350 을
쓴다"가 아니다. 값이 들어가면 표준이 아니라 제품 문서가 되고, 다른 제품이 이 표준을 따를
때 방해가 된다.

**제외 대상 (근거: `pc_app/conf/par_map.json` 실측):**

| 항목 | 값 | 성격 |
|---|---|---|
| `DRY_PUFF_ABS_TEMP_TH` / `REL_SLOPE_TH` | 350 degC / 350 degC·s⁻¹ | 제품 노하우에 가장 근접 |
| 보호 임계값 | UVLO 3400/2000 mV, CHG_OVP 8000 mV, OPEN/SHORT_COIL 300/2000 mV, HEATING_TIMEOUT 180 s | IP 가 아니라 안전 마진 노출 |
| `EXT_CTRL_STATUS`/`EXT_HEATING_PWM_DUTY`/`EXT_HEATING_POWER` | — | 호스트가 UART 로 코일을 구동하는 경로 |

셋 다 가치가 낮은 비밀이다(실물 계측으로 나온다). 그러나 표준 문서에 필요한 내용도
아니다. `EXT_*` 는 목록에 남기되 "외부 제어 인터페이스, 상세는 제품 문서 참조" 한 줄로 둔다.

**구조로 강제한다** — 습관이 아니라 파일 배치로:

- `out/public/` — 커밋된다
- `out/internal/` — `.gitignore` 에 등재. 사내판이 public repo 에 실수로 들어갈 수 없다

## 6. 빌드 파이프라인

설치 없이 되는 경로만 쓴다. 이 머신 확인 결과: pandoc·LaTeX·weasyprint **없음**,
Chrome·Edge **있음**, CJK 폰트(Noto Sans KR/SC, 맑은고딕, YaHei) **있음**.
Chrome 헤드리스 스모크 테스트로 CJK 포함 A4 PDF 생성 및 폰트 서브셋 임베드 확인 완료.

```
spec/{en,ko,zh}.md           손으로 쓰는 산문
spec/_generated/*.json       FW 소스에서 추출 (표)
tools/extract.py             FW/pc_app/bridge 소스 → _generated/
tools/build.py               md + json → site/ (웹) + out/{public,internal}/*.pdf
```

**Markdown 3벌 → 단일 HTML → 웹 + PDF.** 소스 하나가 두 출력을 낸다.

### 6.1 표는 손으로 쓰지 않는다

`PROTOCOL.md` 가 stale 해진 지점이 opcode 표이고, 그건 도출 가능하다. **산문은 손으로,
표는 생성.** 3개 언어가 같은 표를 공유하니 번역 드리프트도 여기서 막힌다.

추출원:

| 대상 | 출처 |
|---|---|
| opcode 표 + CMD_SET 버전 | `CFS-ECIG-SUITE/FW/App/Inc/app_proto.h` |
| 부록 A (var/par) | `CFS-ECIG-SUITE/pc_app/conf/{var_map,par_map}.json` |
| 부록 C (0xC0+) | `CFS-SUITE-BRIDGE/pc_app/cfsbridge/commands.py` |

**부록 B(CVS-BP2601)는 추출하지 않는다.** 출처는 기존 `FW/Doc/PROTOCOL.md` §9 가 이미
기록한 "알려진 차이" 한 건뿐이고, 손으로 옮긴다. BP2601 소스를 새로 분석하지 않는다 —
이 저장소의 작업 범위 규칙(BP2601 프로젝트 파일 불가침)과 충돌하고, 표준 문서에 필요한
정보도 아니다.

**워킹 트리가 아니라 커밋된 내용을 읽는다** (`git -C <repo> show HEAD:<path>`). 근거:
조사 시점에 `CFS-ECIG-SUITE/pc_app/conf/cmd_set.json` 이 `BP2601_org` 사본으로 덮여 있었다
(uncommitted `M`, 벤치 작업 중). 워킹 트리를 읽었으면 **다른 보드의 표가 표준 문서에
실렸을 것이다.**

### 6.2 빌드가 겸하는 교차 검증

추출 시 세 곳의 CMD_SET 번호를 대조하고 어긋나면 빌드를 세운다. 이것은 기존 두 테스트가
할 수 없는 일이다 — 각 테스트는 자기 repo 안만 본다. 문서 빌드는 세 repo 를 동시에 보는
유일한 지점이다.

### 6.3 PDF 조판

- A4, 여백 18/16 mm, 표지 + 머리말 + 쪽번호
- **언어별 폰트 스택을 따로 준다.** 스모크 테스트에서 한 스택을 공유했더니 중국어 `文` 이
  강희부수 글리프(U+2F00)로 떨어졌다 — 전형적인 한자 통합 문제.
  - ko: `"Noto Sans KR", "Malgun Gothic", sans-serif`
  - zh: `"Microsoft YaHei", "Noto Sans SC", sans-serif`
  - en: `"Segoe UI", Arial, sans-serif`
  - 코드: `Consolas, "Cascadia Mono", monospace` (공통)

## 7. 웹 게시

정적 사이트. 호스팅은 **나중에 사내 서버** — 이번엔 계획만 잡고 산출물은 어디에 올려도
동작하는 형태로 만든다(상대 경로, 외부 의존 없음). public repo 이므로 GitHub Pages 도
그대로 가능하다.

구성: 언어 스위처 / 본문 / 다운로드 섹션(PDF 3벌 + 예제 코드 자리).
예제 코드는 "준비 중" 배지로 두고, 코드가 들어오면 배지가 링크로 바뀐다.

## 8. Repo 레이아웃

```
CFS-SUITE-PROTOCOL/
  README.md
  CLAUDE.md              이 repo 규칙
  VERSION                도출된 CMD_SET 버전 (커밋)
  .gitignore             out/internal/ 등재
  spec/
    en.md ko.md zh.md
    _generated/*.json
    assets/style.css
  tools/
    extract.py
    build.py
  out/
    public/*.pdf         커밋
    internal/            gitignore
  site/                  생성물
  examples/
    README.md            "준비 중" 안내
```

## 9. CLAUDE.md 갱신 규칙

루트 `CLAUDE.md` 의 CMD_SET 관련 절에 추가한다. 요지:

> CMD_SET 버전을 올릴 때 `CFS-SUITE-PROTOCOL` 의 문서도 함께 재생성한다.
> 문서는 번호를 따로 들고 있지 않고 `app_proto.h` 에서 읽으므로 **사본 목록에 넣지 않는다**
> — 대조 대상이 아니라 하위 산출물이다. 재생성하지 않으면 사본은 전부 일치하는데
> 문서만 옛 opcode 표를 싣는다. 그것이 2.10.0 과 2.11.0 에서 실제로 일어난 일이다.

`FW/App/Inc/app_proto.h` 의 사본 목록 주석에도 한 줄을 붙이되 **목록 밖에** 둔다 —
목록 안에 넣으면 "번호를 들고 있는 곳"으로 오해되고, 그 목록은 개수를 세는 용도라
오염시키면 안 된다. (ECIG FW 는 frozen 이나 cmd-set 부기(bookkeeping)는 허용된 편집이다.)

## 10. 이번 범위에서 제외

- ECIG `FW`/`pc_app` repo 통합 (§3.2 ②) — frozen 해제 후 별건
- 예제 코드 실물 — `fw_dut` 기준 최적화·검증 후 ECIG-SUITE 구조로 이식하여 별도 투입
- 사내 서버 호스팅 구축 — 계획만
- `FW/Doc/PROTOCOL.md` 의 처분 — 새 문서가 자리를 잡은 뒤 결정 (당장은 남겨 둔다)
- 워킹 트리의 `conf/*.json` BP2601 덮어쓰기 — 벤치 작업 중이므로 건드리지 않는다
