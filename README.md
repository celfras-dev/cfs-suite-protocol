# CFS-SUITE-PROTOCOL

The Celfras Standard Protocol — the wire protocol shared by every Celfras
product (CFS-ECIG-SUITE, CFS-SUITE-BRIDGE, and whatever LIB-MCU-based product
comes next), documented once instead of once per product.

This repository does not implement the protocol. It builds the document that
describes it: a PDF (English, Korean, Chinese) and a matching static site,
generated from the product repos' own source rather than hand-maintained.
The predecessor of this document (`CFS-ECIG-SUITE/FW/Doc/PROTOCOL.md`) went
stale twice on exactly the part that can be generated — its opcode table —
so this repo generates that part instead of writing it down twice.

## Layout

- `spec/{en,ko,zh}.md` — hand-written prose, one file per language. Prose
  carries `{{table:...}}` placeholders where a table belongs; it never
  contains a table itself.
- `spec/_generated/*.json` — tables extracted from the product repos,
  committed so a standalone clone builds without them checked out alongside.
- `tools/` — the extraction and build pipeline (see below).
- `out/public/` — the built public PDFs. Committed.
- `out/internal/` — the internal edition. Gitignored; see "Two editions".
- `site/` — the built static site. Generated, not committed.
- `examples/` — reference example code. Not here yet (see below).

## Building

```
./venv/Scripts/python.exe -m tools.build            # public edition
./venv/Scripts/python.exe -m tools.build --internal  # + product values
```

This reads the sibling product trees checked out in the same cfs-suite org
folder (`../evapor/fw/framework`, `../evapor/pc_app`, `../bridge` -- see
`tools/extract/sources.py`, which also finds the nested repos inside the
bridge tree), derives the command-set version they all agree on, and renders `out/{public,internal}/Celfras Standard
Protocol V<version>*.pdf` plus `site/`.

Run the tests with `./venv/Scripts/python.exe -m pytest tests/ -v`.

This repository does not declare a command-set version of its own — see
`CLAUDE.md` for why, and don't look for one here. Run the build, or read
`VERSION`, to find out what version the document you're holding covers.

## Two editions

Part I of the standard is the wire protocol itself: frame format, opcodes,
error codes, modes — the same across every conforming product. Part II is
per-product: which identifiers a given product assigns, in what units, with
what access. Part II documents structure — that an id *exists* and what it
*means* — never the value a product actually ships in it (a protection
threshold, a tuning default). Those numbers are real product data, and nothing
about the standard needs them.

The **public** edition is Part I plus that structural Part II, and is what
gets committed and published. The **internal** edition adds the real values,
for engineers who need them; its output lives under `out/internal/`, which
`.gitignore` holds so it cannot reach the public repository by habit. A build
also fails outright if a public-edition page ever contains one of those
product values — see `CLAUDE.md` for the mechanics of that gate.

## What's not here yet

`examples/` is a placeholder. The reference implementation (COBS framing,
CRC16, frame dispatch) is still being optimized and bench-verified against
`fw_dut` before it gets ported to this platform's code layout; until then the
site shows a "coming soon" badge instead of a download link.
