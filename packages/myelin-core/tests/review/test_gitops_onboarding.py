"""로컬 git commit 범위와 공유 온보딩 로직."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

import pytest

from myelin_core import gitops
from myelin_core.errors import MyelinError
from myelin_core.gitops import Author, GitError
from myelin_core.onboarding import (
    InitRequest,
    OnboardingError,
    find_packs_dir,
    load_packs,
    prepare_add_domain,
    prepare_init,
)
from myelin_core.scaffold import apply_plan

ME = Author("Tester", "tester@localhost")
TODAY = date(2026, 10, 18)
PHYS = ("brian.physical-ai",)
REQ = InitRequest(owner="Tester", packs=PHYS, primary="AI-ML-AX", research="ROBOTICS-LEARNING")


def _git(vault: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(vault), *args], capture_output=True, text=True, check=True
    ).stdout


def test_init_repo_and_scoped_commit(vault: Path) -> None:
    assert not gitops.is_repo(vault) and gitops.head(vault) is None
    assert gitops.recent_commits(vault) == []
    first = gitops.init_repo(vault, ME)
    assert gitops.is_repo(vault) and gitops.head(vault) == first
    assert _git(vault, "log", "-1", "--format=%an <%ae>").strip() == "Tester <tester@localhost>"
    assert ".myelin" not in _git(vault, "ls-files")  # .gitignore 적용

    # 사용자가 따로 고치던 파일은 commit에 섞이지 않는다
    (vault / "20_Projects/user-wip.md").write_text("작업 중\n", encoding="utf-8")
    (vault / "20_Projects/hub.md").write_text("hub\n", encoding="utf-8")
    sha = gitops.commit_paths(vault, ["20_Projects/hub.md", "20_Projects/gone.md"], "m", ME)
    assert gitops.files_in_commit(vault, sha) == ["20_Projects/hub.md"]
    assert "?? 20_Projects/user-wip.md" in _git(vault, "status", "--porcelain")

    # 이동(삭제 + 추가)도 한 commit
    (vault / "20_Projects/hub.md").rename(vault / "30_Resources/hub.md")
    sha2 = gitops.commit_paths(vault, ["20_Projects/hub.md", "30_Resources/hub.md"], "mv", ME)
    assert sorted(gitops.files_in_commit(vault, sha2)) == [
        "20_Projects/hub.md",
        "30_Resources/hub.md",
    ]
    log = gitops.recent_commits(vault, 5)
    assert [c.subject for c in log] == ["mv", "m", "myelin: start vault history"]


def test_git_refusals(vault: Path, tmp_path: Path) -> None:
    with pytest.raises(GitError) as exc:
        gitops.commit_paths(vault, ["x.md"], "m", ME)
    assert exc.value.issues[0].code == "no_repo"
    gitops.init_repo(vault, ME)
    with pytest.raises(GitError):
        gitops.init_repo(vault, ME)
    with pytest.raises(GitError) as exc:
        gitops.commit_paths(vault, ["nope.md"], "m", ME)
    assert exc.value.issues[0].code == "nothing"
    inner = vault / "20_Projects" / "nested"
    inner.mkdir()
    with pytest.raises(GitError) as exc:
        gitops.init_repo(inner, ME)
    assert exc.value.issues[0].code == "vault_in_git"


def test_failed_commit_leaves_index_clean(vault: Path) -> None:
    gitops.init_repo(vault, ME)
    hook = vault / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    (vault / "20_Projects/a.md").write_text("a\n", encoding="utf-8")
    with pytest.raises(GitError) as exc:
        gitops.commit_paths(vault, ["20_Projects/a.md"], "m", ME)
    assert exc.value.message == "git commit 실패"
    assert _git(vault, "diff", "--cached", "--name-only") == ""


def test_glob_names_are_literal(vault: Path) -> None:
    gitops.init_repo(vault, ME)
    (vault / "00_Inbox/wip.md").write_text("사용자 작업 중\n", encoding="utf-8")
    (vault / "00_Inbox/*.md").write_text("hub\n", encoding="utf-8")
    sha = gitops.commit_paths(vault, ["00_Inbox/*.md"], "m", ME)
    assert gitops.files_in_commit(vault, sha) == ["00_Inbox/*.md"]
    assert _git(vault, "diff", "--cached", "--name-only") == ""
    assert "?? 00_Inbox/wip.md" in _git(vault, "status", "--porcelain")


def test_recent_commits_odd_subject(vault: Path) -> None:
    gitops.init_repo(vault, ME)
    (vault / "20_Projects/a.md").write_text("a\n", encoding="utf-8")
    gitops.commit_paths(vault, ["20_Projects/a.md"], "제목\x1f이상한 문자", ME)
    assert gitops.recent_commits(vault, 1)[0].subject == "제목\x1f이상한 문자"


def test_git_missing(vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gitops.shutil, "which", lambda _: None)
    assert not gitops.git_available()
    with pytest.raises(GitError) as exc:
        gitops.init_repo(vault, ME)
    assert exc.value.issues[0].code == "no_git"


def test_existing_identity_is_respected(vault: Path) -> None:
    gitops.init_repo(vault, ME)
    _git(vault, "config", "user.name", "Real Name")
    _git(vault, "config", "user.email", "real@example.org")
    (vault / "20_Projects/a.md").write_text("a\n", encoding="utf-8")
    gitops.commit_paths(vault, ["20_Projects/a.md"], "m", ME)
    assert _git(vault, "log", "-1", "--format=%an").strip() == "Real Name"


# ── onboarding ───────────────────────────────────────────────────────────
def test_prepare_init_does_not_write(tmp_path: Path) -> None:
    target = tmp_path / "v"
    prepared = prepare_init(target, REQ, load_packs(find_packs_dir()), TODAY)
    assert not target.exists()
    assert prepared.config.domains.all() == ["AI-ML-AX", "ROBOTICS-LEARNING"]
    assert "10_Domains/AI-ML-AX/_MOC.md" in prepared.plan.files


@pytest.mark.parametrize(
    "req",
    [
        InitRequest(owner=" ", primary="AI-ML-AX", packs=PHYS),
        InitRequest(owner="A", primary="", packs=PHYS),
        InitRequest(owner="A", primary="NOPE", packs=PHYS),
        InitRequest(owner="A", primary="AI-ML-AX", packs=("no.such-pack",)),
        InitRequest(owner="A", primary="AI-ML-AX", research="AI-ML-AX", packs=PHYS),
    ],
)
def test_prepare_init_refuses(tmp_path: Path, req: InitRequest) -> None:
    with pytest.raises(MyelinError):
        prepare_init(tmp_path / "v", req, load_packs(find_packs_dir()), TODAY)


def test_prepare_init_refuses_non_empty(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    with pytest.raises(OnboardingError):
        prepare_init(tmp_path, REQ, load_packs(find_packs_dir()), TODAY)


def test_prepare_add_domain(vault: Path) -> None:
    packs = load_packs(find_packs_dir())
    before = (vault / "myelin.yaml").read_text(encoding="utf-8")
    prepared = prepare_add_domain(
        vault, "SEC-CONSULT", "extra", "org.security-consulting", packs, TODAY
    )
    assert (vault / "myelin.yaml").read_text(encoding="utf-8") == before  # 계획만
    apply_plan(vault, prepared.plan)
    assert "SEC-CONSULT" in (vault / "myelin.yaml").read_text(encoding="utf-8")
    for domain, role, code in [
        ("SEC-CONSULT", "growth", "이미 있는"),
        ("EMBEDDED-SW", "research", "3+1"),
        ("EMBEDDED-SW", "primary", "role"),
        ("NOPE", "growth", "찾을 수 없습니다"),
    ]:
        with pytest.raises(OnboardingError) as exc:
            prepare_add_domain(vault, domain, role, None, packs, TODAY)
        assert code in exc.value.message


def test_find_packs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert find_packs_dir(tmp_path) == tmp_path
    monkeypatch.setenv("MYELIN_PACKS", str(tmp_path / "env"))
    assert find_packs_dir() == tmp_path / "env"
