"""install.sh 선택 설정 — 플래그를 줄 때만 테마·플러그인·MCP를 건드린다 (P9-T6)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(shutil.which("uv") is None, reason="uv 필요")


def _run(tmp: Path, *args: str) -> subprocess.CompletedProcess[str]:
    stub = tmp / "stubbin"
    stub.mkdir(exist_ok=True)
    log = tmp / "claude.log"
    (stub / "claude").write_text(f'#!/bin/sh\necho "$@" >> "{log}"\n', encoding="utf-8")
    (stub / "claude").chmod(0o755)
    ref = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    env = {
        **os.environ,
        "PATH": f"{stub}:{os.environ['PATH']}",
        "MYELIN_HOME": str(tmp / "install"),
        "MYELIN_BIN": str(tmp / "bin"),
    }
    env.pop("VIRTUAL_ENV", None)
    cmd = ["bash", str(ROOT / "scripts/install.sh"), "--source", str(ROOT), "--ref", ref]
    return subprocess.run(
        [*cmd, "--no-web", *args], env=env, capture_output=True, text=True, timeout=600
    )


def _vault(tmp: Path) -> Path:
    v = tmp / "MyVault"
    v.mkdir()
    (v / "myelin.yaml").write_text("myelin: 1\n", encoding="utf-8")
    return v


def test_defaults_touch_nothing_optional(tmp_path: Path) -> None:
    res = _run(tmp_path)
    assert res.returncode == 0, res.stderr[-800:]
    assert not (tmp_path / "claude.log").exists()  # --claude 없으면 claude 호출 없음
    assert (tmp_path / "bin/myelin").is_file()


def test_vault_theme_and_claude(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    theme = vault / ".obsidian/themes/MYELIN Emboss"
    theme.mkdir(parents=True)
    (theme / "theme.css").write_text("/* 사용자 수정 */", encoding="utf-8")
    res = _run(tmp_path, "--vault", str(vault), "--claude")
    assert res.returncode == 0, res.stderr[-800:]
    assert (theme / "manifest.json").is_file()
    assert (theme / "theme.css").read_text(encoding="utf-8") == "/* 사용자 수정 */"  # 덮어쓰지 않음
    assert "덮어쓰지 않습니다" in res.stdout
    calls = (tmp_path / "claude.log").read_text(encoding="utf-8").splitlines()
    assert (
        calls[0].startswith("plugin marketplace add ")
        and calls[1] == "plugin install myelin@myelin"
    )
    assert calls[2].startswith("mcp add myelin -- ") and calls[2].endswith(f"--vault {vault}")
    assert sorted(p.name for p in vault.iterdir()) == [".obsidian", "myelin.yaml"]  # 노트 불변


def test_vault_must_be_myelin(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    res = _run(tmp_path, "--vault", str(plain))
    assert res.returncode == 1 and "MYELIN Vault가 아닙니다" in res.stderr
