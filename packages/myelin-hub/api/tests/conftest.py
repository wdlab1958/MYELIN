from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from myelin_hub_api.app import INTENT_HEADER, create_app

REPO_ROOT = Path(__file__).resolve().parents[4]
CLICK = {INTENT_HEADER: "user-click"}


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(autouse=True)
def _packs_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MYELIN_PACKS", str(REPO_ROOT / "packs"))
    monkeypatch.setenv("GIT_AUTHOR_NAME", "t")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "t@example.org")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "t")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "t@example.org")


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    dst = tmp_path / "basic"
    # Runtime/editor state (Hub index, Obsidian workspace) may exist in the checked-out fixture
    # when a developer opens it directly; never copy it into the test Vault (it would be
    # committed by `git add -A` and show up as dirty after the index rebuilds).
    shutil.copytree(
        REPO_ROOT / "tests/fixtures/vaults/basic",
        dst,
        ignore=shutil.ignore_patterns(".myelin", ".obsidian"),
    )
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=dst, check=True)
    subprocess.run(["git", "add", "-A"], cwd=dst, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture"], cwd=dst, check=True, env={**os.environ}
    )
    return dst


@pytest.fixture
def client(vault_root: Path) -> Iterator[TestClient]:
    app = create_app(vault_root, serve_web=False)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def empty_client(tmp_path: Path) -> Iterator[TestClient]:
    root = tmp_path / "fresh"
    root.mkdir()
    app = create_app(root, serve_web=False)
    with TestClient(app) as c:
        c.app.state.root = root  # type: ignore[attr-defined]
        yield c


def tree_hash(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git" not in p.parts and ".myelin" not in p.parts
    }
