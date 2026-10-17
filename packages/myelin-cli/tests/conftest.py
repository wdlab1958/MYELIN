from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def packs_dir() -> Path:
    return REPO_ROOT / "packs"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return REPO_ROOT / "tests" / "fixtures"


@pytest.fixture
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setenv("MYELIN_NOW", "2026-10-18T09:00")
    monkeypatch.setenv("MYELIN_PACKS", "")
    yield "2026-10-18T09:00"
    os.environ.pop("MYELIN_NOW", None)
