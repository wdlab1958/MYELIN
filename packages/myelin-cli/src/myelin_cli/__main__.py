"""`myelin` console entry point. Commands (init/add-domain/doctor/stats) arrive in P2."""

from __future__ import annotations

import sys

from myelin_cli import __version__


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args in (["--version"], ["-V"]):
        print(f"myelin {__version__}")
        return 0
    print(
        "myelin: CLI commands are implemented in Phase P2. See docs/phases/P2.md", file=sys.stderr
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
