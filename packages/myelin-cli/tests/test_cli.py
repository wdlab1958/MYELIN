"""T1/T3 — CLI behaviour via `run()` (exit codes, flags, non-interactive wizard, fail-closed)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from myelin_cli.__main__ import main
from myelin_cli.app import run


def _init_args(vault: Path, packs_dir: Path, **over: str) -> list[str]:
    opts = {"name": "Brian", "primary": "D1", "research": "D3", "growth": "D4", "level": "2"}
    opts.update(over)
    args = ["init", "--non-interactive", "--vault", str(vault), "--packs-dir", str(packs_dir)]
    for k, v in opts.items():
        args += [f"--{k}", v]
    return args


def test_version_and_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.startswith("myelin ")
    assert run([]) == 0  # no args → help, not an error
    assert "init" in capsys.readouterr().out
    assert run(["bogus"]) == 2


def test_init_non_interactive(
    tmp_path: Path, packs_dir: Path, fixed_now: str, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "v"
    assert run(_init_args(vault, packs_dir)) == 0
    out = capsys.readouterr().out
    assert "Vault 생성" in out and "D1, D3, D4" in out
    assert (vault / "myelin.yaml").is_file()
    assert "level: 2" in (vault / "myelin.yaml").read_text(encoding="utf-8")
    assert "id: 20261018-0900-d1-moc" in (vault / "10_Domains/D1/_MOC.md").read_text(
        encoding="utf-8"
    )


def test_init_requires_name_and_primary(
    tmp_path: Path, packs_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = run(
        [
            "init",
            "-y",
            "--vault",
            str(tmp_path / "v"),
            "--packs-dir",
            str(packs_dir),
            "--primary",
            "D1",
        ]
    )
    assert rc == 2 and "--name" in capsys.readouterr().err
    rc = run(
        ["init", "-y", "--vault", str(tmp_path / "v"), "--packs-dir", str(packs_dir), "--name", "x"]
    )
    assert rc == 2 and "--primary" in capsys.readouterr().err
    assert not (tmp_path / "v").exists()


def test_init_rejects_unknown_domain_pack_and_bad_values(
    tmp_path: Path, packs_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(_init_args(tmp_path / "v", packs_dir, primary="D9")) == 2
    assert "알 수 없는 Domain" in capsys.readouterr().err
    assert run([*_init_args(tmp_path / "v", packs_dir), "--pack", "me.ghost"]) == 2
    assert "me.ghost" in capsys.readouterr().err
    assert run(_init_args(tmp_path / "v", packs_dir, research="D1")) == 2
    assert "distinct" in capsys.readouterr().err
    assert run(_init_args(tmp_path / "v", packs_dir, level="7")) == 2
    assert not (tmp_path / "v").exists()


def test_init_no_packs_found(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    empty = tmp_path / "nopacks"
    empty.mkdir()
    assert run(_init_args(tmp_path / "v", empty)) == 2
    assert "Pack 을 찾을 수 없습니다" in capsys.readouterr().err


def test_init_extra_pack_and_dry_run(
    tmp_path: Path, packs_dir: Path, fixed_now: str, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "v"
    assert (
        run([*_init_args(vault, packs_dir), "--pack", "a3.security-consulting", "--dry-run"]) == 0
    )
    out = capsys.readouterr().out
    assert "CLAUDE.md" in out and "10_Domains/D1/_MOC.md" in out
    assert not vault.exists()  # dry-run writes nothing
    assert run([*_init_args(vault, packs_dir), "--pack", "a3.security-consulting"]) == 0
    assert "a3.security-consulting" in (vault / "myelin.yaml").read_text(encoding="utf-8")


def test_init_fail_closed_on_existing(
    tmp_path: Path, packs_dir: Path, fixed_now: str, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "v"
    assert run(_init_args(vault, packs_dir)) == 0
    capsys.readouterr()
    assert run(_init_args(vault, packs_dir, level="3")) == 2
    err = capsys.readouterr().err
    assert "덮어쓰기 금지" in err and "myelin.yaml" in err
    assert "level: 2" in (vault / "myelin.yaml").read_text(encoding="utf-8")


def test_bad_myelin_now(
    tmp_path: Path,
    packs_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("MYELIN_NOW", "yesterday")
    assert run(_init_args(tmp_path / "v", packs_dir)) == 2
    assert "MYELIN_NOW" in capsys.readouterr().err


def test_add_domain_doctor_stats_flow(
    tmp_path: Path, packs_dir: Path, fixed_now: str, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "v"
    assert run(_init_args(vault, packs_dir, research="D3", growth="D4")) == 0
    capsys.readouterr()
    assert run(["add-domain", "D2", "--vault", str(vault), "--packs-dir", str(packs_dir)]) == 0
    assert "Domain D2 추가" in capsys.readouterr().out
    assert (vault / "10_Domains/D2/_MOC.md").is_file()
    assert run(["add-domain", "D2", "--vault", str(vault), "--packs-dir", str(packs_dir)]) == 2
    assert "already configured" in capsys.readouterr().err

    assert run(["doctor", "--vault", str(vault), "--packs-dir", str(packs_dir)]) == 0
    assert "0 errors" in capsys.readouterr().out
    assert run(["doctor", "--vault", str(vault), "--packs-dir", str(packs_dir), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert (
        data["errors"] == 0 and data["notes_scanned"] == 4
    )  # 4 MOCs + taxonomy? no: taxonomy is in 90_System
    assert run(["stats", "--vault", str(vault), "--today", "2026-10-18"]) == 0
    out = capsys.readouterr().out
    assert "MYELIN stats" in out and "verified_per_week" in out
    assert run(["stats", "--vault", str(vault), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["notes"] == 4
    assert run(["stats", "--vault", str(vault), "--today", "18/10/2026"]) == 2


def test_doctor_exit_codes_on_fixtures(
    fixtures_dir: Path, packs_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    basic = str(fixtures_dir / "vaults/basic")
    seeded = str(fixtures_dir / "vaults/seeded-violations")
    assert run(["doctor", "--vault", basic, "--packs-dir", str(packs_dir)]) == 0
    assert run(["doctor", "--vault", basic, "--packs-dir", str(packs_dir), "--strict"]) == 0
    assert run(["doctor", "--vault", seeded, "--packs-dir", str(packs_dir)]) == 1
    out = capsys.readouterr().out
    assert "11 errors" in out and "2 warnings" in out
    assert run(["doctor", "--vault", str(fixtures_dir / "nope")]) == 2
    assert "myelin.yaml not found" in capsys.readouterr().err
    # stats shows a parse-error warning on the seeded vault
    assert run(["stats", "--vault", seeded, "--today", "2026-10-18"]) == 0
    assert "could not be parsed" in capsys.readouterr().out


def test_init_and_add_domain_commit_to_git(
    tmp_path: Path, packs_dir: Path, fixed_now: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """정본 §3: 모든 변경은 Git commit — CLI init 은 저장소를 만들고 add-domain 은 커밋을 남긴다."""
    import subprocess

    vault = tmp_path / "v"
    assert run(_init_args(vault, packs_dir)) == 0
    assert "[myelin:init]" in capsys.readouterr().out
    assert (vault / ".git").is_dir()
    log = subprocess.run(
        ["git", "log", "--format=%s"], cwd=vault, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    assert log == ["[myelin:init] vault created"]
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=vault, capture_output=True, text=True, check=True
    ).stdout
    assert status == ""  # .myelin/ is ignored, everything else committed
    assert run(["add-domain", "D2", "--vault", str(vault), "--packs-dir", str(packs_dir)]) == 0
    log = subprocess.run(
        ["git", "log", "--format=%s"], cwd=vault, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    assert log[0] == "[myelin:add-domain] D2"
    # --no-git keeps the old behaviour (no repository)
    v2 = tmp_path / "v2"
    assert run([*_init_args(v2, packs_dir), "--no-git"]) == 0
    assert not (v2 / ".git").exists()
