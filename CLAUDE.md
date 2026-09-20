# CFS-SUITE-PROTOCOL

This repo builds the Celfras Standard Protocol document from the sibling
product repos' own source. The rules below exist because every one of them
was learned by getting it wrong once first; don't relearn any of them.

## Tables are never hand-written

Every table in the built document comes from `spec/_generated/*.json`,
produced by `tools/extract/*.py` reading the product repos. Prose in
`spec/{en,ko,zh}.md` never contains a table — it places a `{{table:...}}`
placeholder (`tools/render.py` expands it at build time) and writes around
it.

This is not a style preference. The document this repo replaces
(`CFS-ECIG-SUITE/FW/Doc/PROTOCOL.md`) went stale on exactly its opcode table,
twice, across two command-set bumps (2.10.0, 2.11.0) — a hand-written table
simply stopped being touched once nobody remembered to. A generated table
cannot go stale the same way: it is wrong only if the extraction is wrong,
and the extraction is covered by `tests/test_extract_*.py`. If a table needs
new content, add it to the source the extractor reads (or extend the
extractor), never edit `spec/_generated/*.json` or a rendered table by hand.

The `:no_notes` suffix (`{{table:opcodes:core:no_notes}}`,
`{{table:op_modes:no_notes}}`) drops a table's Notes/Meaning column. A note
column carries firmware-comment prose — FSM state names, driver function
names, argument names — which is a convenience for firmware developers, not
normative standard text. Guessing which notes are "too internal" to show
would be judgment calls made once and then stale forever; dropping the whole
column at an explicit call site is a decision made in the prose, visible in
the diff, and it costs nothing to get wrong in the safe direction. Use it
wherever a table's notes would be product-internal detail rather than
standard text — see `tools/render.py`'s comment on `_PLACEHOLDER` for the
finding that motivated it (`OPMODE_ISP`'s and `CMD_RESET`'s notes were
leaking FSM/driver internals into Part I).

## Sources are read from HEAD, never the working tree

`tools/extract/sources.py`'s `read_committed()` runs `git -C <repo> show
HEAD:<path>` — it never opens a file in the product repos' working trees.

This was found, not assumed: at the time this repo was built,
`CFS-ECIG-SUITE/pc_app/conf/cmd_set.json` was sitting uncommitted, swapped
for a different board's copy, because a bench session was mid-test.
CFS-ECIG-SUITE's own root `CLAUDE.md` documents this as routine bench
practice, not an accident to guard against once. Reading the working tree
would have put that other board's tables into the standard document, silently,
with no error — the file would parse fine, it would just be the wrong
product's data. Reading `HEAD` means a bench session's uncommitted swap
never reaches this build, no matter what state the checkout is in.

## The public/internal split, and why `out/internal/` is gitignored

Part I of the standard (the wire protocol) is the same for every product.
Part II documents what each product does with the parts the standard leaves
open — id maps, optional command groups — but only the *structure*: that an
id exists, what it means, its unit, its access. Never the *value* a product
actually ships in it (a protection threshold, a tuning default, an external-
control setpoint). Those are real product data with no standard purpose.

- The **public** edition (`out/public/`, committed) is Part I plus
  structural-only Part II.
- The **internal** edition (`out/internal/`, built with `--internal`) adds
  real product values, for engineers who need them.

`out/internal/` is in `.gitignore` on purpose — see the comment directly
above the line in `.gitignore` itself. This is a second, independent line of
defense: even if someone forgets which edition they built, `git add`/`git
status` cannot surface it by habit.

The stronger defense is mechanical, not procedural: `tools/build.py`'s
`forbidden_public_values()` derives the exact set of real product defaults
from `par_map.json` at HEAD (never a hand-maintained list — that list was
already wrong once, missing `CHG_TIMEOUT_TH` and `LONG_PUFF_TH`), and
`tests/test_public_leak.py` scans every public artifact — PDFs, the site,
`site_extra`, and the literal `print_html` the PDFs are printed from — for
any of those numbers appearing anywhere. A small, explicitly-verified
exemption list (`PROTOCOL_VALUE_EXEMPTIONS` in `tools/build.py`) covers the
rare case where a real standard constant's value collides with a product
default by coincidence (`BURST_PERIOD_MS_MAX == LED_BREATH_PERIOD_MS == 1000`);
extend that list only when `tests/test_build_exemptions.py`'s mechanical
re-derivation would actually justify it, not by comment alone.

`tests/test_public_leak.py::test_shipped_prose_actually_places_a_par_or_var_table`
exists because the whole-document leak scans above are only meaningful while
some public page actually renders a `{{table:par:...}}` or
`{{table:var:...}}` table — if a future prose edit removed every such
placeholder from all three editions, those scans would keep passing with
nothing left to check. That test makes the precondition explicit instead of
letting the gate go quietly vacuous.

**The leak gate has two halves, and both matter.** `tests/test_public_leak.py`
covers *built output* — the rendered site, print HTML, and PDFs. It never
looks at this repository's own tracked source. On 2026-09-10, two internal
working documents (a plan and a design spec, carrying real product values
and a developer's local file paths) were committed straight into
`docs/superpowers/` and would have been pushed with everything in them,
because nothing scanned tracked files at all — only what `tools.build`
produces. `tests/test_tracked_source_leak.py` is the second half: it scans
every file `git ls-files` returns for the same `leak_gate_values()` and for
a developer-machine path marker. A future session that adds a new kind of
published artifact (another generated file, a new site page, an export
format) needs to know the built-output gate does not, by itself, protect a
document someone drops into the tree by hand — that is what the tracked-
file half is for.

## The three editions must stay structurally identical

`spec/en.md`, `ko.md`, and `zh.md` are independent hand-written prose files,
but they are required to share the same heading structure and the same
`{{table:...}}` placeholders, in the same order, byte for byte. Nothing about
the build enforces this by construction — each file is rendered
independently, and `render.py` will happily expand whichever placeholders a
given file happens to contain without comparing it to the others.
`tests/test_spec_parity.py` is the check: it compares heading levels and
placeholder sequences across all three files and fails if any of them
diverge. Run it (it's part of the normal suite) after any edit that touches
more than one language file, and before adding a placeholder or heading to
only one of them on purpose.

This does not check translation quality — only structure. Translated prose
is reviewed by people; six of the seven findings the translators raised
while reviewing this document's first draft were exactly the kind of
divergence this test would have caught immediately (a section reordered in
one language, a definition split in one file and not the others).

## Normative verbs, §1.4 — do not introduce a sixth rendering

Each language's §1.4 fixes the words that carry normative force, and only
those words carry it. Record here so a later edit doesn't invent a new
phrasing for a level that already has one:

| Level | English | Korean (`spec/ko.md`) | Chinese (`spec/zh.md`) |
|---|---|---|---|
| MUST | `MUST` | ~하여야 한다 | 应 |
| MUST NOT | `MUST NOT` | ~하여서는 안 된다 | 不应 |
| SHOULD / SHOULD NOT | `SHOULD` / `SHOULD NOT` | ~하는 것을 권장한다 / ~하지 않을 것을 권장한다 | 宜 (covers both directions) |
| MAY | `MAY` | ~하여도 된다 | 可 |

Two traps specific to each language, both stated explicitly in that
language's §1.4:

- Korean: normative permission is expressed **only** as "~하여도 된다". "~할
  수 있다" reads as ability/possibility, not permission, and must not be used
  where MAY is meant.
- Chinese: 应/不应/宜/可 are the only four verbs carrying normative force in
  the whole document; every other verb is descriptive prose and must not be
  read as a requirement.

If a translation ever needs a fifth level or a different shade of MUST/SHOULD,
that is a change to all three §1.4 sections at once, not a new phrase
introduced quietly somewhere in Part II.

## This repo declares no command-set version

There is no `CMD_SET_VERSION`-shaped constant anywhere in this repository.
`tools/extract/version.py` derives the version this build documents by
reading every real copy in the product repos (`_collect()`'s list) at `HEAD`
and refusing to build if they disagree — see that module's own docstring for
why it is deliberately not allowed to say how many copies there are (the
count has been wrong before, more than once, in more than one repo). `VERSION`
at this repo's root is that derived value, committed so a standalone clone
can build without every product repo checked out — but it is a cached
answer, not a second source of truth: a real build always re-derives it and
fails if `VERSION` and the derivation disagree with each other, never picks
one.

Do not add a version constant here, and do not add this repo's `VERSION` file
or `app_proto.h` reference to any product repo's own copy-count comment or
test — this repo is a downstream artifact of the command-set version, not
another place the number lives. `CFS-ECIG-SUITE/CLAUDE.md`'s "표준 프로토콜
문서" section and the comment in `FW/App/Inc/app_proto.h` (outside its copy
list, deliberately) both say the same thing from the other side.

## Action item — `examples/`: port `fw_dut` as the reference implementation

Registered 2026-09-20, not started. `examples/` is still the "coming soon"
placeholder; `README.md` promises a portable DUT-side core (COBS framing,
CRC16-CCITT-FALSE, frame dispatch, needing only a byte put/get from the
UART) plus one buildable example, in the platform's `drv_*`/`svc_*`/`app_*`
layout. Facts to design around, checked 2026-09-20:

- **`bridge/fw_dut/<chip>/App` is the living, bench-verified code** (fw_dut
  2.0.0, cmd_set 4.1.0; five trees whose `App/` is identical but for the
  CHIP define and product name). `lib-mcu/template/dut-test/` claims to be
  its source but is stale (0.1.0, half the files). Pick ONE source of
  truth — the natural answer is the core living here and the fw_dut trees
  and the LIB-MCU template being generated/snapshotted from it — and
  retire the other copies in the same change.
- **Two readers depend on the fw_dut paths**: `tools/extract/version.py`
  `_C_HEADERS` (five `fw_dut/cwm*/App/Inc/app_proto.h` entries) and
  `bridge/pc_app/tests/fw_tree.py` `DUT_SLUGS`. Whatever moves, both are
  updated in the same commit, and `test_no_undeclared_copy_appeared`
  re-baselined by hand.
- **Public boundary.** This repo mirrors to GitHub; the public-edition leak
  gate applies to `examples/` too. Strip product names, pin maps and
  hwtest values; keep chip names (CWM* are public).
- **Bench path stays in bridge.** hwtest.py, MDK/GCC builds and the LIB-MCU
  chip-pack snapshots (`Libraries/`) are wired to `bridge/fw_dut/<chip>/`.
  The example here is one buildable project, not five trees.

Start with brainstorming → a spec in `docs/superpowers/specs/` (source of
truth, core boundary, which chip the example targets, extractor changes,
leak gate), then a plan. Do not copy files across before that is written.
