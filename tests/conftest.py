"""Repo-level pytest config: fixtures root + e2e opt-in."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_VAULTS = REPO_ROOT / "tests" / "fixtures" / "vaults"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def fixture_vaults() -> Path:
    return FIXTURE_VAULTS


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("MYELIN_E2E") == "1":
        return
    skip = pytest.mark.skip(reason="e2e tests run only with MYELIN_E2E=1")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip)
