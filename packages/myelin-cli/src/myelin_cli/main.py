"""Entry point placeholder. Real commands arrive in P2 (Typer)."""

import sys

from myelin_cli import __version__


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args in (["--version"], ["-V"]):
        print(f"myelin {__version__}")
        return 0
    print("myelin: commands are not implemented yet (planned for P2).", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
