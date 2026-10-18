"""Review·git·onboarding 테스트 공용 — 임시 폴더에 실제 Vault를 만든다."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from myelin_core.onboarding import InitRequest, find_packs_dir, load_packs, prepare_init
from myelin_core.scaffold import apply_plan

TODAY = date(2026, 10, 18)
REQ = InitRequest(
    owner="Tester",
    packs=("brian.physical-ai",),
    primary="AI-ML-AX",
    research="ROBOTICS-LEARNING",
    level=1,
)


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    target = tmp_path / "vault"
    prepared = prepare_init(target, REQ, load_packs(find_packs_dir()), TODAY)
    apply_plan(target, prepared.plan)
    return target


@pytest.fixture
def put(vault: Path) -> Callable[[str, str], str]:
    def _put(rel: str, text: str) -> str:
        path = vault / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return rel

    return _put


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """사용자·러너의 전역 git 설정(서명, 훅, 이름)에 영향받지 않게."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "no-global-gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
