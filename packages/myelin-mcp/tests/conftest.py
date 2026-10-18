from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from myelin_mcp.service import VaultService

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(autouse=True)
def _external_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-0011: tests run as an EXTERNAL process unless they opt in with `local_session`."""
    monkeypatch.delenv("MYELIN_LLM", raising=False)


@pytest.fixture
def local_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MYELIN_LLM", "local")


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    dst = tmp_path / "basic"
    shutil.copytree(REPO_ROOT / "tests/fixtures/vaults/basic", dst)
    return dst


def set_mcp(
    root: Path,
    *,
    write_draft: bool | None = None,
    expose: bool | None = None,
    level: int | None = None,
) -> None:
    text = (root / "myelin.yaml").read_text(encoding="utf-8")
    if level is not None:
        text = text.replace("level: 2", f"level: {level}")
    extra = []
    if write_draft is not None:
        extra.append(f"  write_draft: {str(write_draft).lower()}")
    if expose is not None:
        extra.append(f"  expose_confidential: {str(expose).lower()}")
    if extra:
        text += "mcp:\n" + "\n".join(extra) + "\n"
    (root / "myelin.yaml").write_text(text, encoding="utf-8")


@pytest.fixture
def service(vault_root: Path) -> VaultService:
    return VaultService.open(vault_root)
