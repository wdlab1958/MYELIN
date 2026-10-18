"""CLI 통합 테스트 — 실제 명령을 CliRunner로 실행한다."""

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from myelin_cli import main as cli
from myelin_cli.main import app, default_packs_dir
from myelin_core import onboarding

ROOT = Path(__file__).resolve().parents[3]
PACKS = ["--packs", str(ROOT / "packs")]
TODAY = ["--today", "2026-10-18"]
GOLDEN = ROOT / "tests" / "fixtures" / "vaults" / "golden" / "brian"
GOLDEN_ARGS = [
    "--name", "Brian", "--pack", "brian.physical-ai",
    "--primary", "AI-ML-AX", "--research", "ROBOTICS-LEARNING",
    "--growth", "AUTO-DESIGN", "--extra", "EMBEDDED-SW",
    "--level", "1", *TODAY, "--yes", *PACKS,
]  # fmt: skip

runner = CliRunner()


def tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0 and "myelin 1.0.0" in result.output


def test_packs_lists_domains() -> None:
    result = runner.invoke(app, ["packs", *PACKS])
    assert result.exit_code == 0
    assert "brian.physical-ai" in result.output and "EMBEDDED-SW" in result.output


def test_init_matches_golden(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", str(tmp_path / "v"), *GOLDEN_ARGS])
    assert result.exit_code == 0, result.output
    assert tree(tmp_path / "v") == tree(GOLDEN)


def test_init_refuses_occupied_and_source(tmp_path: Path) -> None:
    (tmp_path / "x.md").write_text("mine", encoding="utf-8")
    result = runner.invoke(app, ["init", str(tmp_path), *GOLDEN_ARGS])
    assert result.exit_code == 1 and "not_empty" not in result.output
    assert (tmp_path / "x.md").read_text(encoding="utf-8") == "mine"
    result = runner.invoke(app, ["init", str(ROOT / "my-vault"), *GOLDEN_ARGS])
    assert result.exit_code == 1 and "MYELIN 소스" in result.output
    assert not (ROOT / "my-vault").exists()


def test_init_noninteractive_requires_values(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["init", str(tmp_path / "v"), "--pack", "brian.physical-ai", *PACKS]
    )
    assert result.exit_code == 1 and "--name" in result.output


def test_init_validation_errors(tmp_path: Path) -> None:
    bad_domain = ["--name", "a", "--pack", "brian.physical-ai", "--primary", "NOPE", "--yes"]
    result = runner.invoke(app, ["init", str(tmp_path / "v"), *bad_domain, *PACKS])
    assert result.exit_code == 1 and "NOPE" in result.output
    result = runner.invoke(
        app,
        [
            "init",
            str(tmp_path / "v2"),
            "--name",
            "a",
            "--primary",
            "X",
            "--pack",
            "no.such",
            *PACKS,
        ],
    )
    assert result.exit_code == 1 and "no.such" in result.output
    result = runner.invoke(app, ["init", str(tmp_path / "v3"), *GOLDEN_ARGS[:-3], "--today", "bad"])
    assert result.exit_code == 1


def test_init_interactive(tmp_path: Path) -> None:
    answers = "1\n홍길동\nAI-ML-AX\nROBOTICS-LEARNING\n\ny\n"
    result = runner.invoke(
        app, ["init", str(tmp_path / "v"), "--interactive", *PACKS, *TODAY], input=answers
    )
    assert result.exit_code == 0, result.output
    text = (tmp_path / "v" / "myelin.yaml").read_text(encoding="utf-8")
    assert '"홍길동"' in text and "research: ROBOTICS-LEARNING" in text and "  growth:" not in text


def test_init_interactive_decline(tmp_path: Path) -> None:
    answers = "1\n홍길동\nAI-ML-AX\n\n\nn\n"
    result = runner.invoke(
        app, ["init", str(tmp_path / "v"), "--interactive", *PACKS], input=answers
    )
    assert result.exit_code == 1 and not (tmp_path / "v").exists()


@pytest.fixture
def sec_vault(tmp_path: Path) -> Path:
    v = tmp_path / "v"
    args = ["--name", "a", "--pack", "org.security-consulting", "--primary", "SEC-CONSULT", "--yes"]
    assert runner.invoke(app, ["init", str(v), *args, *PACKS, *TODAY]).exit_code == 0
    return v


def test_add_domain_flow(sec_vault: Path) -> None:
    add = ["add-domain", str(sec_vault), *PACKS, *TODAY]
    ok = runner.invoke(
        app, [*add, "--domain", "AI-ML-AX", "--role", "research", "--pack", "brian.physical-ai"]
    )
    assert ok.exit_code == 0, ok.output
    assert (sec_vault / "10_Domains" / "AI-ML-AX" / "_MOC.md").is_file()
    assert "| research | AI-ML-AX |" in (sec_vault / "CLAUDE.md").read_text(encoding="utf-8")
    assert "AI-ML-AX" in (sec_vault / "90_System" / "myelin.lock.yaml").read_text(encoding="utf-8")
    assert runner.invoke(app, ["doctor", str(sec_vault), "--no-location", *TODAY]).exit_code == 0

    cases = [
        (["--domain", "EMBEDDED-SW", "--role", "research"], "3+1"),
        (["--domain", "AI-ML-AX", "--role", "growth"], "이미 있는"),
        (["--domain", "NOPE", "--role", "growth"], "찾을 수 없습니다"),
        (["--domain", "EMBEDDED-SW", "--role", "boss"], "role"),
    ]
    for extra, needle in cases:
        result = runner.invoke(app, [*add, *extra])
        assert result.exit_code == 1 and needle in result.output, (extra, result.output)


def test_add_domain_refuses_non_vault_and_existing_moc(tmp_path: Path, sec_vault: Path) -> None:
    result = runner.invoke(app, ["add-domain", str(tmp_path / "nothing"), "--domain", "X", *PACKS])
    assert result.exit_code == 1 and "myelin.yaml" in result.output
    moc = sec_vault / "10_Domains" / "EMBEDDED-SW" / "_MOC.md"
    moc.parent.mkdir(parents=True)
    moc.write_text("내 노트", encoding="utf-8")
    before = (sec_vault / "myelin.yaml").read_text(encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "add-domain",
            str(sec_vault),
            "--domain",
            "EMBEDDED-SW",
            "--pack",
            "brian.physical-ai",
            *PACKS,
        ],
    )
    assert result.exit_code == 1 and "덮어쓰지" in result.output
    assert moc.read_text(encoding="utf-8") == "내 노트"
    assert (sec_vault / "myelin.yaml").read_text(encoding="utf-8") == before


def test_doctor_and_stats_outputs(tmp_path: Path) -> None:
    v = tmp_path / "violations"
    shutil.copytree(ROOT / "tests" / "fixtures" / "vaults" / "violations", v)
    result = runner.invoke(app, ["doctor", str(v), *TODAY])
    assert result.exit_code == 1 and "오류 6" in result.output
    as_json = runner.invoke(app, ["doctor", str(v), "--json", *TODAY])
    assert len(json.loads(as_json.output)) == 9

    golden = tmp_path / "golden"
    shutil.copytree(GOLDEN, golden)
    (golden / "00_Inbox" / "old.md").write_text(
        "---\nid: 20261001-0000-old\ntype: fleeting\nstatus: draft\norigin: human\n"
        "created: 2026-09-01\n---\n",
        encoding="utf-8",
    )
    assert runner.invoke(app, ["doctor", str(golden), *TODAY]).exit_code == 0
    assert runner.invoke(app, ["doctor", str(golden), "--strict", *TODAY]).exit_code == 1

    stats = runner.invoke(app, ["stats", str(v), "--json", *TODAY])
    assert json.loads(stats.output)["parse_errors"] == 1
    plain = runner.invoke(app, ["stats", str(v), *TODAY])
    assert "orphan_ratio" in plain.output


def test_default_packs_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MYELIN_PACKS", str(tmp_path))
    assert default_packs_dir() == tmp_path
    monkeypatch.delenv("MYELIN_PACKS")
    assert default_packs_dir() == ROOT / "packs"
    monkeypatch.setattr(cli, "__file__", str(tmp_path / "a" / "b" / "c" / "d" / "main.py"))
    monkeypatch.setattr(onboarding, "__file__", str(tmp_path / "a" / "b" / "c" / "d" / "x.py"))
    result = runner.invoke(app, ["packs"])
    assert result.exit_code == 1 and "MYELIN_PACKS" in result.output


def test_broken_packs_dir(tmp_path: Path) -> None:
    (tmp_path / "me.bad").mkdir()
    (tmp_path / "me.bad" / "pack.yaml").write_text("pack: me.bad\n", encoding="utf-8")
    result = runner.invoke(app, ["packs", "--packs", str(tmp_path)])
    assert result.exit_code == 1
