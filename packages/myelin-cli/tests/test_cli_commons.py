"""P7 — CLI: commons init/add-pack/registry, publish (check/confirm/block), propose, metrics."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import myelin_cli.app as app_module
from myelin_cli.app import run


@pytest.fixture
def vault(fixtures_dir: Path, tmp_path: Path) -> Path:
    dst = tmp_path / "vault"
    shutil.copytree(fixtures_dir / "vaults/basic", dst)
    return dst


def test_commons_init_registry(
    tmp_path: Path, packs_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    c = tmp_path / "commons"
    assert run(["commons", "init", str(c)]) == 0
    assert (c / "registry/index.yaml").exists()
    assert (
        run(["commons", "add-pack", str(packs_dir / "a3.security-consulting"), "--commons", str(c)])
        == 0
    )
    assert "초안" in capsys.readouterr().out
    assert (
        run(
            [
                "commons",
                "add-pack",
                str(packs_dir / "a3.incident-response"),
                "--commons",
                str(c),
                "--champion",
                "홍챔피언",
            ]
        )
        == 0
    )
    assert "확정" in capsys.readouterr().out
    assert run(["commons", "registry", str(c)]) == 0
    out = capsys.readouterr().out
    assert "a3.incident-response" in out and "홍챔피언" in out and "(초안)" in out
    assert run(["commons", "registry", str(c), "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 2
    assert run(["commons", "add-pack", str(tmp_path / "nope"), "--commons", str(c)]) == 2


def test_publish_check_and_blocks(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    c = tmp_path / "commons"
    run(["commons", "init", str(c)])
    good = "10_Domains/D2/WCET 예산은 측정값의 1.5배로 잡는다.md"
    assert run(["publish", good, "--vault", str(vault), "--commons", str(c), "--check"]) == 0
    assert "검사 통과" in capsys.readouterr().out
    assert (
        run(
            [
                "publish",
                "40_IP/candidates/Agentic CAD 검증 루프.md",
                "--vault",
                str(vault),
                "--commons",
                str(c),
                "--check",
            ]
        )
        == 1
    )
    err = capsys.readouterr().err
    assert "confidential" in err and "차단" in err
    assert (
        run(
            [
                "publish",
                "10_Domains/D4/구멍 간 최소 간격 규칙.md",
                "--vault",
                str(vault),
                "--commons",
                str(c),
                "-y",
            ]
        )
        == 1
    )
    assert "share: false" in capsys.readouterr().err
    # non-interactive without --yes → refuses (confirmation required)
    assert run(["publish", good, "--vault", str(vault), "--commons", str(c)]) == 2
    assert "--yes" in capsys.readouterr().err
    assert not list((c / "notes").rglob("*.md"))


def test_publish_confirmed_and_commons_local(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    c = tmp_path / "commons"
    run(["commons", "init", str(c)])
    good = "10_Domains/D2/WCET 예산은 측정값의 1.5배로 잡는다.md"
    assert run(["publish", good, "--vault", str(vault), "--commons", str(c), "-y"]) == 0
    out = capsys.readouterr().out
    assert "publish/20260907-0800-wcet-budget" in out and "git push -u origin" in out
    branches = subprocess.run(["git", "branch"], cwd=c, capture_output=True, text=True).stdout
    assert "publish/20260907-0800-wcet-budget" in branches
    ev = (vault / ".myelin/metrics.jsonl").read_text(encoding="utf-8")
    assert '"event": "publish"' in ev
    # commons.local from myelin.yaml + no --commons
    (vault / "myelin.yaml").write_text(
        (vault / "myelin.yaml")
        .read_text(encoding="utf-8")
        .replace("commons: { enabled: false }", f"commons: {{ enabled: false, local: '{c}' }}"),
        encoding="utf-8",
    )
    assert (
        run(
            [
                "publish",
                "10_Domains/D1/AX 저항은 통제감 상실에서 온다.md",
                "--vault",
                str(vault),
                "-y",
            ]
        )
        == 0
    )
    assert run(["publish", good, "--vault", str(vault), "-y"]) == 1  # already exists
    (vault / "myelin.yaml").write_text(
        (vault / "myelin.yaml").read_text(encoding="utf-8").replace(f", local: '{c}'", ""),
        encoding="utf-8",
    )
    assert run(["publish", good, "--vault", str(vault), "-y"]) == 2
    assert "Commons 경로" in capsys.readouterr().err


def test_publish_interactive_confirm(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = tmp_path / "commons"
    run(["commons", "init", str(c)])
    monkeypatch.setattr(app_module, "_is_tty", lambda: True)
    monkeypatch.setattr(app_module.typer, "confirm", lambda *_a, **_k: False)
    good = "10_Domains/D2/WCET 예산은 측정값의 1.5배로 잡는다.md"
    assert run(["publish", good, "--vault", str(vault), "--commons", str(c)]) == 0  # cancelled
    assert not list((c / "notes").rglob("*.md"))
    monkeypatch.setattr(app_module.typer, "confirm", lambda *_a, **_k: True)
    assert run(["publish", good, "--vault", str(vault), "--commons", str(c)]) == 0
    assert (
        "publish/"
        in subprocess.run(["git", "branch"], cwd=c, capture_output=True, text=True).stdout
    )


def test_pack_propose_and_metrics(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    c = tmp_path / "commons"
    run(["commons", "init", str(c)])
    pdir = vault / "packs" / "me.side"
    pdir.mkdir(parents=True)
    (pdir / "pack.yaml").write_text(
        "pack: me.side\nkind: personal\nmaintainer: me\nrequires: [myelin.core>=1.0]\n"
        "domains:\n  - {id: SIDE, name: Side}\n",
        encoding="utf-8",
    )
    assert (
        run(["pack-propose", str(pdir), "--vault", str(vault), "--commons", str(c)]) == 2
    )  # needs --yes
    assert run(["pack-propose", str(pdir), "--vault", str(vault), "--commons", str(c), "-y"]) == 0
    assert "propose/me.side" in capsys.readouterr().out
    assert run(["metrics", "show", "--vault", str(vault)]) == 0
    out = capsys.readouterr().out
    assert "anonymous: yes" in out and "proposals" in out and "brian@example.org" not in out
    assert run(["metrics", "show", "--vault", str(vault), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["anonymous"] is True
    assert (
        run(["metrics", "send", "--vault", str(vault), "--commons", str(c), "-y"]) == 1
    )  # opt-in off
    assert "opt-in" in capsys.readouterr().err
    (vault / "myelin.yaml").write_text(
        (vault / "myelin.yaml")
        .read_text(encoding="utf-8")
        .replace(
            "commons: { enabled: false }", "commons: { enabled: false, metrics_opt_in: true }"
        ),
        encoding="utf-8",
    )
    assert run(["metrics", "send", "--vault", str(vault), "--commons", str(c), "-y"]) == 0
    files = list((c / "metrics").rglob("*.json"))
    assert len(files) == 1 and "brian" not in files[0].read_text(encoding="utf-8")
    assert run(["metrics", "aggregate", str(c)]) == 0
    out = capsys.readouterr().out
    assert "users" in out and "reuse" in out and "reuse total" in out
    assert run(["metrics", "aggregate", str(c), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) >= {"weeks", "reuse", "reuse_total", "top_contributors"}
    assert all("reuse" in row for row in data["weeks"].values())


def test_init_records_onboard_start(tmp_path: Path, packs_dir: Path, fixed_now: str) -> None:
    v = tmp_path / "v"
    assert (
        run(
            [
                "init",
                "-y",
                "--vault",
                str(v),
                "--packs-dir",
                str(packs_dir),
                "--name",
                "x",
                "--primary",
                "D1",
            ]
        )
        == 0
    )
    assert '"event": "onboard_start"' in (v / ".myelin/metrics.jsonl").read_text(encoding="utf-8")
