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
