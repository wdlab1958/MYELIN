"""`myelin skills` and `myelin interview-bank`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from myelin_cli.app import run


def test_skills_table(fixtures_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    basic = str(fixtures_dir / "vaults/basic")  # level 2
    assert run(["skills", "--vault", basic]) == 0
    out = capsys.readouterr().out
    assert "Level 2 — link-patch" in out and "/ip-scan" in out
    assert run(["skills", "--vault", basic, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    enabled = {r["skill"] for r in data["skills"] if r["enabled"]}
    assert enabled == {"/ingest", "/distill", "/interview", "/review", "/link", "/compose"}
    assert data["level"] == 2


def test_skills_level_0_all_disabled(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "myelin.yaml").write_text(
        "owner: {name: x}\npacks: [myelin.core]\ndomains: {primary: D1}\nlevel: 0\n",
        encoding="utf-8",
    )
    assert run(["skills", "--vault", str(tmp_path), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert not any(r["enabled"] for r in data["skills"])  # T10: Level 0 → 쓰기 Skill 전부 비활성


def test_interview_bank(
    fixtures_dir: Path, packs_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    basic = str(fixtures_dir / "vaults/basic")
    assert run(["interview-bank", "--vault", basic, "--packs-dir", str(packs_dir), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    qs = data["questions"]
    assert len(qs) == 16 and {q["domain"] for q in qs} == {"D1", "D2", "D3", "D4"}
    assert run(["interview-bank", "--vault", basic, "--packs-dir", str(packs_dir), "-d", "D3"]) == 0
    out = capsys.readouterr().out
    assert "[D3] d3-sim2real-gap" in out and "[D1]" not in out and "↳" not in out
    assert run(["interview-bank", "--vault", basic, "--packs-dir", str(packs_dir), "-d", "D2"]) == 0
    assert "↳" in capsys.readouterr().out  # follow-ups rendered
    assert run(["interview-bank", "--vault", basic, "--packs-dir", str(packs_dir), "-d", "D9"]) == 2
    assert "설정되지 않았습니다" in capsys.readouterr().err


def test_interview_bank_empty(
    tmp_path: Path, packs_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "myelin.yaml").write_text(
        "owner: {name: x}\npacks: [myelin.core, a3.security-consulting]\n"
        "domains: {primary: SEC-CONSULT}\nlevel: 1\n",
        encoding="utf-8",
    )
    assert run(["interview-bank", "--vault", str(tmp_path), "--packs-dir", str(packs_dir)]) == 0
    assert "[SEC-CONSULT] sec-method-skip" in capsys.readouterr().out
    (tmp_path / "myelin.yaml").write_text(
        "owner: {name: x}\npacks: [myelin.core]\ndomains: {primary: D1}\nlevel: 1\n",
        encoding="utf-8",
    )
    assert run(["interview-bank", "--vault", str(tmp_path), "--packs-dir", str(packs_dir)]) == 0
    assert "질문 은행이 없습니다" in capsys.readouterr().out
    assert (
        run(["interview-bank", "--vault", str(tmp_path), "--packs-dir", str(tmp_path / "none")])
        == 2
    )
