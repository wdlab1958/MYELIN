"""`myelin-mcp` entry point: `myelin-mcp --vault <path>` (or $MYELIN_VAULT), stdio transport."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from myelin_core.config import ConfigError
from myelin_mcp import __version__


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="myelin-mcp", description="MYELIN MCP server (stdio, read-only by default)"
    )
    ap.add_argument(
        "--vault", type=Path, default=None, help="Vault path (default: $MYELIN_VAULT or cwd)"
    )
    ap.add_argument("--version", action="version", version=f"myelin-mcp {__version__}")
    ns = ap.parse_args(argv)
    root = ns.vault or Path(os.environ.get("MYELIN_VAULT") or Path.cwd())
    if not (root / "myelin.yaml").is_file():
        print(f"myelin-mcp: {root} is not a MYELIN Vault (myelin.yaml missing)", file=sys.stderr)
        return 2
    from myelin_mcp.server import serve

    try:
        serve(root.resolve())
    except ConfigError as exc:
        print(f"myelin-mcp: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
