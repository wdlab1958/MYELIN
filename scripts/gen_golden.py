"""Regenerate the golden snapshot for `myelin init` (P2-T10).

tests/fixtures/golden/init-basic/ is produced by running the CLI non-interactively with a fixed
MYELIN_NOW against the repo packs. The test replays the same command into a temp dir and
compares tree + contents byte for byte. Run this after an intentional scaffold change and
review the diff before committing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests/fixtures/golden/init-basic"
NOW = "2026-10-18T09:00"
ARGS = [
    "init",
    "--non-interactive",
    "--name",
    "Brian",
    "--team",
    "Example Org AI WG",
    "--email",
    "brian@example.org",
    "--primary",
    "D1",
    "--research",
    "D3",
    "--growth",
    "D4",
    "--level",
    "2",
    "--packs-dir",
    str(ROOT / "packs"),
]


def run_init(target: Path) -> None:
    env = {**os.environ, "MYELIN_NOW": NOW, "MYELIN_PACKS": ""}
    cmd = [sys.executable, "-m", "myelin_cli", *ARGS, "--vault", str(target)]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=ROOT)
    if proc.returncode != 0:
        raise SystemExit(f"init failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}")


def main() -> int:
    if GOLDEN.exists():
        shutil.rmtree(GOLDEN)
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    run_init(GOLDEN)
    n = sum(1 for p in GOLDEN.rglob("*") if p.is_file())
    print(f"golden written: {GOLDEN.relative_to(ROOT)} ({n} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
