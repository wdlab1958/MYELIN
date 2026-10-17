"""Export JSON Schemas to docs/spec/schema/ (committed; a test checks they are in sync).

usage: python scripts/export_schemas.py [--check]
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from myelin_core.schema.export import export_json_schemas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/spec/schema"


def main(argv: list[str]) -> int:
    if "--check" in argv:
        with tempfile.TemporaryDirectory() as tmp:
            fresh = {
                p.name: json.loads(p.read_text(encoding="utf-8"))
                for p in export_json_schemas(Path(tmp))
            }
        stale = [
            name
            for name, data in fresh.items()
            if not (OUT / name).exists()
            or json.loads((OUT / name).read_text(encoding="utf-8")) != data
        ]
        if stale:
            print(f"STALE schemas: {stale} — run `make schemas`", file=sys.stderr)
            return 1
        print(f"{len(fresh)} schemas in sync")
        return 0
    for p in export_json_schemas(OUT):
        print(f"wrote {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
