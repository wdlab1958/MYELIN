from __future__ import annotations

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


GOOD_FM = """---
id: 20261018-0712-wcet-budget
type: evergreen
domain: [D2, D3]
status: verified
origin: mixed
confidence: high
classification: internal
share: false
source: ["[[Lit - ROS2 Executor]]"]
created: 2026-10-18
reviewed: 2026-10-18
tags: [rtos, control-loop]
---
# WCET budget

Body with a link to [[Lit - ROS2 Executor]] and [[Control Loop|alias]].
"""


@pytest.fixture
def good_note_text() -> str:
    return GOOD_FM
