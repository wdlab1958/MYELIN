"""Validate every pack under packs/ and resolve them together (P1 Gate: Pack 3종 검증 통과).

usage: python scripts/validate_packs.py [packs_dir]
"""

from __future__ import annotations

import sys
from pathlib import Path

from myelin_core import PackError, discover_packs, resolve_packs

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    packs_dir = Path(argv[1]) if len(argv) > 1 else ROOT / "packs"
    try:
        registry = discover_packs([packs_dir])
        order = resolve_packs(sorted(registry), registry)
    except PackError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    for lp in order:
        doms = ", ".join(lp.pack.domain_ids) or "-"
        print(f"OK   {lp.name:<28} v{lp.pack.version:<8} {lp.pack.kind.value:<10} domains: {doms}")
    print(f"{len(order)} packs valid, install order: {' -> '.join(lp.name for lp in order)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
