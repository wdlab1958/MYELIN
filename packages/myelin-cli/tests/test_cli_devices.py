"""ADR-0011 §4/§5 — settings.json Read deny, Vault git pre-commit device, `doctor --staged`."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from myelin_cli.app import run
from myelin_core.scaffold import PRE_COMMIT, PRE_COMMIT_MARKER, install_git_hook

from .test_cli import _init_args

NOTE = (
    "---\nid: {id}\ntype: fleeting\ndomain: [D1]\nstatus: {status}\norigin: {origin}\n"
    "classification: {cls}\nshare: {share}\ncreated: 2026-10-01\n{reviewed}---\n# {id}\n"
)


def note(
    id_: str,
    *,
    status: str = "draft",
    origin: str = "claude",
    cls: str = "internal",
    share: str = "false",
    reviewed: str | None = None,
) -> str:
    return NOTE.format(
        id=id_,
        status=status,
        origin=origin,
        cls=cls,
        share=share,
        reviewed=f"reviewed: {reviewed}\n" if reviewed else "",
    )


def git(
    vault: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=vault, capture_output=True, text=True, env={**os.environ, **(env or {})}
    )


def stage(vault: Path, rel: str, text: str) -> None:
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    assert git(vault, "add", "--", rel).returncode == 0


@pytest.fixture
def vault(tmp_path: Path, packs_dir: Path, fixed_now: str) -> Path:
    v = tmp_path / "v"
    assert run(_init_args(v, packs_dir, level="1")) == 0
    return v


def doctor(vault: Path, *flags: str) -> int:
    return run(["doctor", "--vault", str(vault), *flags])


# ------------------------------------------------------------------------------ §4 settings
def test_settings_json_denies_read_of_ip(vault: Path) -> None:
    deny = json.loads((vault / ".claude/settings.json").read_text(encoding="utf-8"))["permissions"][
        "deny"
    ]
    assert "Read(./40_IP/**)" in deny and "Edit(./40_IP/**)" in deny
    assert not any(d.startswith(("Grep(", "Glob(", "Write(")) for d in deny)  # never evaluated


# ------------------------------------------------------------------------------ §5 install
def test_init_installs_pre_commit_hook(vault: Path) -> None:
    src, dest = vault / PRE_COMMIT, vault / ".git/hooks/pre-commit"
    for p in (src, dest):
        assert p.is_file() and p.stat().st_mode & stat.S_IXUSR, p
        text = p.read_text(encoding="utf-8")
        assert text.startswith("#!/bin/sh") and PRE_COMMIT_MARKER in text
        assert "doctor --staged" in text and "--no-verify" in text
    assert src.read_bytes() == dest.read_bytes()
    assert dest.stat().st_mode & 0o777 == 0o755 or dest.stat().st_mode & 0o111 == 0o111
    # the scaffold copy is committed with the Vault, the installed copy is not tracked
    assert PRE_COMMIT in git(vault, "ls-files").stdout.splitlines()


def test_no_git_init_leaves_no_hook_and_install_hook_refuses(
    tmp_path: Path, packs_dir: Path, fixed_now: str, capsys: pytest.CaptureFixture[str]
) -> None:
    v = tmp_path / "nogit"
    assert run([*_init_args(v, packs_dir), "--no-git"]) == 0
    assert (v / PRE_COMMIT).is_file() and not (v / ".git").exists()
    assert doctor(v, "--install-hook") == 2
    assert "git 저장소가 아닙니다" in capsys.readouterr().err


def test_install_hook_reinstalls_and_never_clobbers_foreign_hook(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = vault / ".git/hooks/pre-commit"
    dest.unlink()
    assert doctor(vault, "--install-hook") == 0
    assert dest.is_file() and "pre-commit hook 설치" in capsys.readouterr().out
    # ours → replaced (upgrade path)
    dest.write_text(f"#!/bin/sh\n# {PRE_COMMIT_MARKER} v0 old\nexit 0\n", encoding="utf-8")
    assert doctor(vault, "--install-hook") == 0
    assert "doctor --staged" in dest.read_text(encoding="utf-8")
    # foreign → refused, untouched
    dest.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")
    assert doctor(vault, "--install-hook") == 2
    assert "덮어쓰지 않습니다" in capsys.readouterr().err
    assert dest.read_text(encoding="utf-8") == "#!/bin/sh\necho mine\n"
    # a user-modified scaffold copy without the marker is not silently replaced either
    dest.unlink()
    (vault / PRE_COMMIT).write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    with pytest.raises(Exception, match="MYELIN 이 만든 hook 이 아닙니다"):
        install_git_hook(vault)


def test_install_hook_recreates_missing_scaffold_copy(vault: Path) -> None:
    (vault / PRE_COMMIT).unlink()
    (vault / ".git/hooks/pre-commit").unlink()
    dest = install_git_hook(vault)
    assert dest == (vault / ".git/hooks/pre-commit").resolve()
    assert PRE_COMMIT_MARKER in (vault / PRE_COMMIT).read_text(encoding="utf-8")


# ------------------------------------------------------------------------------ §5 --staged
def test_staged_nothing_is_ok(vault: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert doctor(vault, "--staged") == 0
    assert "doctor (staged): 0 notes" in capsys.readouterr().out


def test_staged_not_a_repo(tmp_path: Path, packs_dir: Path, fixed_now: str) -> None:
    v = tmp_path / "nogit"
    assert run([*_init_args(v, packs_dir), "--no-git"]) == 0
    assert doctor(v, "--staged") == 2


@pytest.mark.parametrize(
    "rel,text,rule",
    [
        ("10_Domains/D1/ai.md", note("20261001-0900-a"), "ai-scope"),  # claude draft outside scope
        ("10_Domains/D1/v.md", note("20261001-0901-b", status="verified"), "temporal"),
        ("30_Resources/vc.md", note("20261001-0902-c"), "ai-scope"),  # draft in 30_Resources
        ("80_Outputs/drafts/o.md", note("20261001-0903-d"), "ai-scope"),  # Level 2 scope, L1 vault
        (
            "00_Inbox/ai-drafts/x.md",
            note("20261001-0904-e", cls="confidential", share="true"),
            "confidential-share",
        ),
        ("00_Inbox/ai-drafts/bad.md", "---\nid: x\n", "schema"),
        ("00_Inbox/ai-drafts/d.md", note("20261001-0905-f").replace("[D1]", "[NOPE]"), "domain"),
        (
            "00_Inbox/ai-drafts/hv.md",
            note("20261001-0906-g", origin="human", status="verified"),
            "temporal",
        ),
    ],
)
def test_staged_errors_exit_1(
    vault: Path, capsys: pytest.CaptureFixture[str], rel: str, text: str, rule: str
) -> None:
    stage(vault, rel, text)
    assert doctor(vault, "--staged", "--json") == 1
    data = json.loads(capsys.readouterr().out)
    assert data["errors"] >= 1 and rule in data["by_rule"], data
    assert all(f["path"] == rel for f in data["findings"])


@pytest.mark.parametrize(
    "rel,text",
    [
        ("00_Inbox/ai-drafts/ok.md", note("20261001-0910-a")),  # AI draft in scope
        ("50_Journal/w.md", note("20261001-0911-b")),
        # Hub Promote shape: moved to 10_Domains, verified, reviewed, origin mixed
        (
            "10_Domains/D1/p.md",
            note("20261001-0912-c", status="verified", origin="mixed", reviewed="2026-10-02"),
        ),
        # Hub Reject shape: archived, deprecated, still origin claude
        ("99_Archive/rejected/r.md", note("20261001-0913-d", status="deprecated")),
        ("10_Domains/D1/h.md", note("20261001-0914-e", origin="human", status="unverified")),
        ("90_System/templates/t.md", "not a note {{id}}"),  # templates are skipped
        ("CLAUDE.md", "# rules\n"),
        ("_patches/p.patch.md", "whatever"),
        ("10_Domains/D1/img.png", "\x89PNG"),
    ],
)
def test_staged_ok_exit_0(vault: Path, rel: str, text: str) -> None:
    stage(vault, rel, text)
    assert doctor(vault, "--staged") == 0


def test_staged_checks_index_not_working_tree(vault: Path) -> None:
    rel = "10_Domains/D1/ai.md"
    stage(vault, rel, note("20261001-0920-a"))  # bad version staged
    (vault / rel).write_text(
        note("20261001-0920-a", origin="human"), encoding="utf-8"
    )  # fixed only on disk
    assert doctor(vault, "--staged") == 1
    assert git(vault, "add", rel).returncode == 0
    assert doctor(vault, "--staged") == 0
    # deletions are not checked (nothing to validate)
    assert git(vault, "rm", "-q", "--cached", rel).returncode == 0
    assert doctor(vault, "--staged") == 0


def test_staged_level_scopes_follow_myelin_yaml(
    tmp_path: Path, packs_dir: Path, fixed_now: str
) -> None:
    v = tmp_path / "l2"
    assert run(_init_args(v, packs_dir, level="2")) == 0
    stage(v, "80_Outputs/drafts/o.md", note("20261001-0930-a"))
    assert doctor(v, "--staged") == 0  # Level 2 unlocks 80_Outputs/drafts
    stage(v, "40_IP/candidates/i.md", note("20261001-0931-b", cls="confidential"))
    assert doctor(v, "--staged") == 1  # 40_IP/candidates is Level 3


def test_staged_nested_vault_in_bigger_repo(
    tmp_path: Path, packs_dir: Path, fixed_now: str
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert git(repo, "init", "-q", "-b", "main").returncode == 0
    v = repo / "sub" / "vault"
    assert run([*_init_args(v, packs_dir, level="1"), "--no-git"]) == 0
    (repo / "README.md").write_text("outside the vault\n", encoding="utf-8")
    assert git(repo, "add", "-A").returncode == 0
    assert doctor(v, "--staged") == 0  # README + scaffold are fine
    stage(repo, "sub/vault/10_Domains/D1/ai.md", note("20261001-0940-a"))
    assert doctor(v, "--staged") == 1


# ------------------------------------------------------------------------------ §5 real hook
def _commit(vault: Path, msg: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return git(
        vault,
        "commit",
        "-q",
        "-m",
        msg,
        *extra,
        env={"MYELIN_BIN": f"{sys.executable} -m myelin_cli"},
    )


def test_real_git_commit_is_rejected_then_accepted(vault: Path) -> None:
    stage(vault, "10_Domains/D1/ai.md", note("20261001-0950-a"))
    bad = _commit(vault, "sneak an AI note into the human area")
    assert bad.returncode != 0
    assert "ai-scope" in bad.stdout + bad.stderr and "--no-verify" in bad.stdout + bad.stderr
    assert git(vault, "log", "--format=%s").stdout.splitlines() == ["[myelin:init] vault created"]
    stage(
        vault,
        "10_Domains/D1/ai.md",
        note("20261001-0950-a", origin="mixed", status="verified", reviewed="2026-10-02"),
    )
    good = _commit(vault, "human promoted it")
    assert good.returncode == 0, good.stderr
    assert git(vault, "log", "--format=%s").stdout.splitlines()[0] == "human promoted it"


def test_real_git_commit_no_verify_is_the_human_bypass(vault: Path) -> None:
    stage(vault, "10_Domains/D1/ai.md", note("20261001-0951-a"))
    assert _commit(vault, "I know what I am doing", "--no-verify").returncode == 0


def test_hook_fails_closed_when_cli_missing(vault: Path) -> None:
    stage(vault, "00_Inbox/ai-drafts/ok.md", note("20261001-0952-a"))
    proc = git(vault, "commit", "-q", "-m", "x", env={"MYELIN_BIN": "myelin-does-not-exist-xyz"})
    assert proc.returncode != 0 and "fail-closed" in proc.stderr


def test_add_domain_commit_passes_the_hook(
    vault: Path, packs_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(["add-domain", "D2", "--vault", str(vault), "--packs-dir", str(packs_dir)]) == 0
    assert "[myelin:add-domain]" in capsys.readouterr().out
    assert git(vault, "log", "--format=%s").stdout.splitlines()[0] == "[myelin:add-domain] D2"
