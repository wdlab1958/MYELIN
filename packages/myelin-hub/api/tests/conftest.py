"""Hub API 테스트 공용."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from myelin_core.onboarding import find_packs_dir
from myelin_hub_api.app import create_app
from myelin_hub_api.service import HubService

BASE = "http://127.0.0.1:8765"
ACT = {"X-Myelin-Intent": "user", "Origin": BASE}
TODAY = date(2026, 10, 18)
ONBOARD = {
    "owner": "Tester",
    "packs": ["brian.physical-ai"],
    "primary": "AI-ML-AX",
    "research": "ROBOTICS-LEARNING",
    "level": 1,
    "git": True,
}


def tree(root: Path) -> dict[str, str]:
    """폴더 전체(숨김·.git 포함)의 경로 → 내용 해시. 폴더 자체도 기록한다."""
    if not root.exists():
        return {}
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        out[rel] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "<dir>"
    return out


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "no-global-gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def target(tmp_path: Path) -> Path:
    return tmp_path / "vault"


@pytest.fixture
def service(target: Path) -> HubService:
    return HubService(target, find_packs_dir(), today=lambda: TODAY)


@pytest.fixture
def client(service: HubService) -> TestClient:
    return TestClient(create_app(service), base_url=BASE)


@pytest.fixture
def onboarded(client: TestClient, target: Path) -> Path:
    res = client.post("/api/onboarding/apply", json=ONBOARD, headers=ACT)
    assert res.status_code == 200, res.text
    return target


@pytest.fixture
def put(target: Path) -> Callable[[str, str], str]:
    def _put(rel: str, text: str) -> str:
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return rel

    return _put


def draft(note_id: str = "20261018-0900-wcet", body: str = "# WCET 예산\n\n본문.\n") -> str:
    return (
        "---\n"
        f"id: {note_id}\n"
        "type: evergreen\n"
        "domain: [AI-ML-AX]\n"
        "status: draft\n"
        "origin: claude\n"
        "created: 2026-10-17\n"
        "---\n"
        f"{body}"
    )


# importlib 모드에서는 conftest를 import 할 수 없으므로 fixture로 내보낸다.
@pytest.fixture
def act() -> dict[str, str]:
    return dict(ACT)


@pytest.fixture
def onboard_body() -> dict[str, object]:
    return dict(ONBOARD)


@pytest.fixture
def make_draft() -> Callable[..., str]:
    return draft


@pytest.fixture
def snapshot() -> Callable[[Path], dict[str, str]]:
    return tree
