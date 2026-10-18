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
    skip_e2e = pytest.mark.skip(reason="e2e tests run only with MYELIN_E2E=1")
    skip_perf = pytest.mark.skip(reason="perf tests run only with MYELIN_PERF=1 (make gate P=4)")
    for item in items:
        if "e2e" in item.keywords and os.environ.get("MYELIN_E2E") != "1":
            item.add_marker(skip_e2e)
        if "perf" in item.keywords and os.environ.get("MYELIN_PERF") != "1":
            item.add_marker(skip_perf)
