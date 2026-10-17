"""`myelin` console entry point (Typer app in `myelin_cli.app`)."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from myelin_cli.app import run

    return run(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    raise SystemExit(main())
