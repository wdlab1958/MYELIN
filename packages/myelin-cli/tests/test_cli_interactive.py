"""T3 — interactive wizard path (prompts) driven through typer's CliRunner."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import myelin_cli.app as app_module
from myelin_cli.app import app


@pytest.fixture
def tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module, "_is_tty", lambda: True)


def test_wizard_prompts_and_creates_vault(
    tmp_path: Path, packs_dir: Path, fixed_now: str, tty: None
) -> None:
    vault = tmp_path / "v"
    runner = CliRunner()
    # name, team, email, primary, research, growth
    answers = "\n".join(["Brian", "A3", "", "D1", "D3", ""]) + "\n"
    result = runner.invoke(
        app, ["init", "--vault", str(vault), "--packs-dir", str(packs_dir)], input=answers
    )
    assert result.exit_code == 0, result.output
    assert "3+1 규칙" in result.output and "AI/ML/AX Platform  [brian.physical-ai]" in result.output
    cfg = (vault / "myelin.yaml").read_text(encoding="utf-8")
    assert (
        "primary: D1" in cfg
        and "research: D3" in cfg
        and "growth" not in cfg.split("domains:")[1].split("extra")[0]
    )


def test_wizard_requires_name(tmp_path: Path, packs_dir: Path, tty: None) -> None:
    result = CliRunner().invoke(
        app, ["init", "--vault", str(tmp_path / "v"), "--packs-dir", str(packs_dir)], input="\n"
    )
    assert result.exit_code == 2
    assert "비워둘 수 없습니다" in result.output
    assert not (tmp_path / "v").exists()


def test_wizard_uses_flag_defaults(
    tmp_path: Path, packs_dir: Path, fixed_now: str, tty: None
) -> None:
    vault = tmp_path / "v"
    # all values given as flags → prompts show them as defaults, empty input accepts them
    result = CliRunner().invoke(
        app,
        [
            "init",
            "--vault",
            str(vault),
            "--packs-dir",
            str(packs_dir),
            "--name",
            "B",
            "--primary",
            "D4",
        ],
        input="\n" * 6,
    )
    assert result.exit_code == 0, result.output
    assert "primary: D4" in (vault / "myelin.yaml").read_text(encoding="utf-8")
