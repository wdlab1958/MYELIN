"""P3 테스트 공용: 임시 Vault 생성과 Guard 실행."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from myelin_core.config import parse_config
from myelin_core.loader import discover_packs, resolve
from myelin_core.scaffold import GUARD_FILE, apply_plan, plan_init

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_GUARD = ROOT / "plugin" / "scripts" / "myelin_guard.py"


def make_vault(path: Path, level: int = 1) -> Path:
    packs = resolve(["brian.physical-ai"], discover_packs(ROOT / "packs"))
    cfg = parse_config(
        {
            "owner": {"name": "t"},
            "packs": ["myelin.core", "brian.physical-ai"],
            "domains": {"primary": "AI-ML-AX", "research": "EMBEDDED-SW"},
            "level": level,
        }
    )
    apply_plan(path, plan_init(cfg, packs, date(2026, 10, 18)))
    return path


def set_config(vault: Path, old: str, new: str) -> None:
    cfg = vault / "myelin.yaml"
    text = cfg.read_text(encoding="utf-8")
    assert old in text
    cfg.write_text(text.replace(old, new), encoding="utf-8")


Runner = Callable[..., "tuple[int, str]"]


def run_guard(script: Path, payload: object, raw: str | None = None) -> tuple[int, str]:
    data = raw if raw is not None else json.dumps(payload)
    res = subprocess.run(
        [sys.executable, str(script)], input=data, capture_output=True, text=True, timeout=30
    )
    return res.returncode, res.stderr


def event(tool: str, path: str, cwd: Path, key: str = "file_path") -> dict[str, object]:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {key: path},
        "cwd": str(cwd),
    }


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    return make_vault(tmp_path / "vault")


@pytest.fixture
def vault_guard(vault: Path) -> Path:
    return vault / GUARD_FILE
