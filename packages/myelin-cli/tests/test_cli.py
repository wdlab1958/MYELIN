"""T1/T3 — CLI behaviour via `run()` (exit codes, flags, non-interactive wizard, fail-closed)."""

from __future__ import annotations

import json
import os
import sys
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


def _git_out(vault: Path, *args: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", *args], cwd=vault, capture_output=True, text=True, check=True
    ).stdout


def test_add_domain_commits_only_its_own_paths(
    tmp_path: Path, packs_dir: Path, fixed_now: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """formal F3 (ADR-0009 §4): unrelated user files — untracked, modified or already staged —
    must not land in the `[myelin:add-domain]` commit (was `git add -A`)."""
    vault = tmp_path / "v"
    assert run(_init_args(vault, packs_dir, research="D3", growth="D4")) == 0
    scratch = vault / "30_Resources" / "wip-notes.txt"
    scratch.parent.mkdir(exist_ok=True)
    scratch.write_text("private scratch\n", encoding="utf-8")  # untracked
    staged = vault / "30_Resources" / "staged-by-user.txt"
    staged.write_text("the user staged this for their own commit\n", encoding="utf-8")
    _git_out(vault, "add", "--", "30_Resources/staged-by-user.txt")
    moc = vault / "10_Domains/D1/_MOC.md"
    moc.write_text(moc.read_text(encoding="utf-8") + "\nunfinished edit\n", encoding="utf-8")
    capsys.readouterr()

    assert run(["add-domain", "D2", "--vault", str(vault), "--packs-dir", str(packs_dir)]) == 0
    out = capsys.readouterr().out
    touched = set(out.split("변경: ", 1)[1].splitlines()[0].split(", "))
    assert _git_out(vault, "log", "-1", "--format=%s").strip() == "[myelin:add-domain] D2"
    committed = set(_git_out(vault, "show", "--pretty=format:", "--name-only", "HEAD").split())
    assert "10_Domains/D2/_MOC.md" in committed and "myelin.yaml" in committed
    assert committed <= touched, f"unrelated paths in the commit: {sorted(committed - touched)}"
    status = _git_out(vault, "status", "--porcelain")
    assert "?? 30_Resources/wip-notes.txt" in status  # still untracked
    assert "A  30_Resources/staged-by-user.txt" in status  # still staged, not committed
    assert " M 10_Domains/D1/_MOC.md" in status  # still an uncommitted edit


def test_obsidian_setup_commits_only_obsidian_paths(
    tmp_path: Path, packs_dir: Path, fixed_now: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Sibling of F3: `myelin obsidian setup` used the same whole-tree commit."""
    import json as _json

    vault = tmp_path / "v"
    assert run(_init_args(vault, packs_dir)) == 0
    graph = vault / ".obsidian/graph.json"
    data = _json.loads(graph.read_text(encoding="utf-8"))
    data["colorGroups"] = []  # so that setup has something to restore
    graph.write_text(_json.dumps(data), encoding="utf-8")
    _git_out(vault, "add", "--", ".obsidian/graph.json")
    _git_out(vault, "commit", "-q", "-m", "user: reset graph", "--no-verify")
    (vault / "30_Resources").mkdir(exist_ok=True)
    (vault / "30_Resources/wip.txt").write_text("scratch\n", encoding="utf-8")
    capsys.readouterr()
    assert run(["obsidian", "setup", "--vault", str(vault), "--packs-dir", str(packs_dir)]) == 0
    assert _git_out(vault, "log", "-1", "--format=%s").strip().startswith("[myelin:settings]")
    committed = set(_git_out(vault, "show", "--pretty=format:", "--name-only", "HEAD").split())
    assert committed and all(p.startswith(".obsidian/") for p in committed), committed
    assert "?? 30_Resources/" in _git_out(vault, "status", "--porcelain")


# ------------------------------------------------------------------ 고객정보 가드 · One Cycle
def _fixture_vault(tmp_path: Path, fixtures_dir: Path) -> Path:
    import shutil

    dst = tmp_path / "basic"
    shutil.copytree(
        fixtures_dir / "vaults/basic", dst, ignore=shutil.ignore_patterns(".myelin", ".obsidian")
    )
    return dst


def test_guard_scan_blocks_flags_and_masks(
    tmp_path: Path, fixtures_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = _fixture_vault(tmp_path, fixtures_dir)
    assert run(["guard", "scan", "--vault", str(vault)]) == 0
    assert "0 blocked" in capsys.readouterr().out
    bad = vault / "10_Domains/D2/leak.md"
    bad.write_text("# x\n\npassword = Sup3rS3cret!!\n", encoding="utf-8")
    code = vault / "10_Domains/D2/code.md"
    code.write_text("# x\n```\n" + "a\n" * 40 + "```\n", encoding="utf-8")
    assert run(["guard", "scan", "--vault", str(vault)]) == 1
    out = capsys.readouterr().out
    assert "BLOCK" in out and "credential-assignment" in out and "Sup3rS3cret" not in out
    assert "FLAG" in out and "large-code-block" in out and "1 blocked · 1 flagged" in out
    assert run(["guard", "scan", "--vault", str(vault), str(code), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["blocked"] == 0 and data["flagged"] == 1 and data["scanned"] == 1
    assert run(["guard", "scan", "--vault", str(vault), str(code), "--strict"]) == 1
    capsys.readouterr()
    assert run(["guard", "scan", str(bad)]) == 1  # without a Vault: built-in rules
    capsys.readouterr()
    assert run(["guard", "scan"]) == 2
    (vault / "90_System/infoguard.yaml").write_text("bogus: 1\n", encoding="utf-8")
    assert run(["guard", "scan", "--vault", str(vault)]) == 2  # fail-closed
    assert "fail-closed" in capsys.readouterr().err


def test_pre_commit_guard_refuses_a_secret_outside_the_inbox(
    tmp_path: Path, packs_dir: Path, fixed_now: str, capsys: pytest.CaptureFixture[str]
) -> None:
    import subprocess

    vault = tmp_path / "v"
    assert run(_init_args(vault, packs_dir)) == 0
    note = (
        "---\nid: 20261018-0900-leak\ntype: evergreen\ndomain: [D1]\ncreated: 2026-10-18\n---\n"
        "# 누출\n\n{body}\n"
    )
    leak = vault / "10_Domains/D1/leak.md"
    leak.write_text(note.format(body="api_key: abcd1234efgh5678"), encoding="utf-8")
    inbox = vault / "00_Inbox/leak-inbox.md"
    inbox.write_text(note.format(body="api_key: abcd1234efgh5678"), encoding="utf-8")
    _git_out(vault, "add", "--", "00_Inbox/leak-inbox.md")
    capsys.readouterr()
    assert run(["doctor", "--staged", "--vault", str(vault), "--packs-dir", str(packs_dir)]) == 0
    _git_out(vault, "add", "--", "10_Domains/D1/leak.md")
    assert run(["doctor", "--staged", "--vault", str(vault), "--packs-dir", str(packs_dir)]) == 1
    err = capsys.readouterr().err
    assert "credential-assignment" in err and "abcd1234efgh5678" not in err
    # the real hook: git commit is refused
    env = {**os.environ, "MYELIN_BIN": f"{sys.executable} -m myelin_cli"}
    proc = subprocess.run(
        ["git", "commit", "-q", "-m", "leak"], cwd=vault, capture_output=True, text=True, env=env
    )
    assert proc.returncode != 0 and "고객정보 가드" in proc.stderr
    leak.write_text(note.format(body="api_key 는 금고에 둔다"), encoding="utf-8")
    _git_out(vault, "add", "--", "10_Domains/D1/leak.md")
    assert run(["doctor", "--staged", "--vault", str(vault), "--packs-dir", str(packs_dir)]) == 0


def test_onecycle_import_findings_cli(
    tmp_path: Path,
    fixtures_dir: Path,
    repo_root: Path,
    fixed_now: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = _fixture_vault(tmp_path, fixtures_dir)
    samples = repo_root / "docs/onecycle/samples"
    src = str(samples / "findings.llmops.sample.json")
    before = sorted(p.name for p in (vault / "00_Inbox/ai-drafts").iterdir())
    assert run(["onecycle", "import-findings", src, "--vault", str(vault), "--dry-run"]) == 0
    assert "만들 예정" in capsys.readouterr().out
    assert sorted(p.name for p in (vault / "00_Inbox/ai-drafts").iterdir()) == before
    assert run(["onecycle", "import-findings", src, "--vault", str(vault), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] and len(data["created"]) == 2 and "LLMOPS" in data["hint"]
    assert all((vault / c["path"]).is_file() for c in data["created"])
    assert not (vault / ".git").exists()  # the importer never runs git
    assert run(["onecycle", "import-findings", src, "--vault", str(vault)]) == 0
    assert "2 건너뜀" in capsys.readouterr().out
    assert run(["doctor", "--vault", str(vault), "--packs-dir", str(repo_root / "packs")]) == 0
    capsys.readouterr()
    # bad input: exit 2, nothing written
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema": "onecycle.findings/v1", "findings": []}', encoding="utf-8")
    n = len(list((vault / "00_Inbox/ai-drafts").iterdir()))
    assert run(["onecycle", "import-findings", str(bad), "--vault", str(vault)]) == 2
    assert "not a valid onecycle.findings/v1" in capsys.readouterr().err
    assert (
        run(["onecycle", "import-findings", str(tmp_path / "none.json"), "--vault", str(vault)])
        == 2
    )
    capsys.readouterr()
    # a finding the guard blocks: exit 1, the clean ones are still imported
    doc = json.loads((samples / "findings.ssc.sample.json").read_text(encoding="utf-8"))
    doc["findings"].append(
        dict(doc["findings"][0], id="ssc:x/leak", description="token=abcdef0123456789")
    )
    mixed = tmp_path / "mixed.json"
    mixed.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    assert run(["onecycle", "import-findings", str(mixed), "--vault", str(vault)]) == 1
    cap = capsys.readouterr()
    assert "가드가 막음: ssc:x/leak" in cap.err and "abcdef0123456789" not in cap.err
    assert len(list((vault / "00_Inbox/ai-drafts").iterdir())) == n + 1
