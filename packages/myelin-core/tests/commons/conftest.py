"""Commons·비식별·지표 테스트 공용 — 임시 Vault + Commons 저장소 + bare 원격."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from myelin_core.commons import init_commons
from myelin_core.config import update_config
from myelin_core.gitops import Author
from myelin_core.onboarding import InitRequest, find_packs_dir, load_packs, prepare_init
from myelin_core.scaffold import apply_plan

TODAY = date(2026, 10, 18)


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "no-global-gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    target = tmp_path / "vault"
    req = InitRequest(owner="Tester", packs=("brian.physical-ai",), primary="AI-ML-AX")
    apply_plan(target, prepare_init(target, req, load_packs(find_packs_dir()), TODAY).plan)
    return target


@pytest.fixture
def commons(tmp_path: Path) -> Path:
    repo = tmp_path / "commons"
    init_commons(repo, "Example Org", Author("Admin", "admin@localhost"))
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(remote)], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "-q", "origin", "HEAD"], check=True)
    return repo


@pytest.fixture
def link() -> Callable[[Path, Path | None, bool], None]:
    def _link(vault: Path, commons: Path | None, enabled: bool = True) -> None:
        def mutate(data: Any) -> None:
            data["commons"]["enabled"] = enabled
            data["commons"]["path"] = str(commons) if commons else None

        _, text = update_config(vault, mutate)
        (vault / "myelin.yaml").write_text(text, encoding="utf-8")

    return _link


@pytest.fixture
def put(vault: Path) -> Callable[[str, str], str]:
    def _put(rel: str, text: str) -> str:
        path = vault / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return rel

    return _put
