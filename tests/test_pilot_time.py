"""scripts/pilot_time.py — 온보딩 시간 계산."""

from __future__ import annotations

import importlib.util
import os
import subprocess
from datetime import datetime
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("pilot_time", ROOT / "scripts/pilot_time.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pt = _load()


def _commit(repo: Path, msg: str, when: str) -> None:
    env = {
        **os.environ,
        "GIT_COMMITTER_DATE": when,
        "GIT_AUTHOR_DATE": when,
        "GIT_CONFIG_GLOBAL": str(repo / ".." / "nogit"),
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
         "--allow-empty", "-m", msg],
        check=True, env=env,
    )  # fmt: skip


def test_onboarding_minutes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = tmp_path / "v"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    assert pt.main([str(repo)]) == 1  # 기록 없음
    _commit(repo, "myelin: start vault history", "2026-10-20T10:00:00+09:00")
    with pytest.raises(ValueError):
        pt.onboarding_minutes(repo)
    _commit(repo, "myelin: promote 20261020-1003-x (x)", "2026-10-20T10:12:30+09:00")
    assert pt.onboarding_minutes(repo) == 12.5
    start = datetime.fromisoformat("2026-10-20T09:55:00")
    assert pt.onboarding_minutes(repo, start) == 17.5
    assert pt.main([str(repo)]) == 0 and capsys.readouterr().out.strip() == "12.5"
