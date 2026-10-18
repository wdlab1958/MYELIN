"""T10/T11 — golden snapshot of `myelin init` and the < 10 s budget."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

GOLDEN_REL = "tests/fixtures/golden/init-basic"


def _tree(root: Path) -> dict[str, bytes]:
    # .myelin/ is runtime state (metrics events carry timestamps) — not part of the snapshot
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not {".myelin", ".git"} & set(p.relative_to(root).parts)
    }


def _run_golden_init(repo_root: Path, target: Path) -> subprocess.CompletedProcess[str]:
    sys.path.insert(0, str(repo_root / "scripts"))
    try:
        import gen_golden  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    env = {**os.environ, "MYELIN_NOW": gen_golden.NOW, "MYELIN_PACKS": ""}
    cmd = [sys.executable, "-m", "myelin_cli", *gen_golden.ARGS, "--vault", str(target)]
    return subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=repo_root)


def test_init_matches_golden(repo_root: Path, tmp_path: Path) -> None:
    golden = repo_root / GOLDEN_REL
    assert golden.is_dir(), "run `make golden` first"
    target = tmp_path / "init-basic"
    proc = _run_golden_init(repo_root, target)
    assert proc.returncode == 0, proc.stderr
    actual, expected = _tree(target), _tree(golden)
    assert sorted(actual) == sorted(expected)
    diffs = [p for p in expected if actual[p] != expected[p]]
    if diffs and os.environ.get("UPDATE_GOLDEN") == "1":
        shutil.rmtree(golden)
        shutil.copytree(target, golden)
        pytest.fail(f"golden updated for {diffs}; re-run")
    assert diffs == [], f"content differs from golden: {diffs} (set UPDATE_GOLDEN=1 to accept)"


def test_init_under_10_seconds(repo_root: Path, tmp_path: Path) -> None:
    t0 = time.perf_counter()
    proc = _run_golden_init(repo_root, tmp_path / "bench")
    elapsed = time.perf_counter() - t0
    assert proc.returncode == 0, proc.stderr
    assert elapsed < 10.0, f"init took {elapsed:.2f}s (budget 10s incl. interpreter start-up)"
