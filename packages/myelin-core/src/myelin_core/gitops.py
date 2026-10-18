"""Vault 로컬 git — Hub의 사람 행위(승격·반려·설정)를 되돌릴 수 있는 commit으로 남긴다 (ADR-0008).

- push·fetch·remote 조작은 하지 않는다. 원격은 사용자가 직접 정한다.
- commit 은 Hub가 바꾼 경로만 담는다 (`git commit -- <paths>`).
  사용자가 따로 고치던 파일은 섞이지 않는다.
- git 이 없거나 실패하면 MyelinError — 호출자가 파일 변경을 되돌린다.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from myelin_core.errors import Issue, MyelinError
from myelin_core.safety import find_git_root

TIMEOUT_S = 30


class GitError(MyelinError):
    """git 작업 실패."""


@dataclass(frozen=True)
class Author:
    name: str
    email: str


@dataclass(frozen=True)
class CommitInfo:
    sha: str
    subject: str
    when: str


def git_available() -> bool:
    return shutil.which("git") is not None


def is_repo(vault: Path) -> bool:
    """Vault 폴더 자체가 git 저장소의 루트인가 (상위 저장소는 해당 없음)."""
    return (vault / ".git").exists()


def _env() -> dict[str, str]:
    return {**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}


def _git(vault: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    if not git_available():
        raise GitError("git 을 찾을 수 없습니다", [Issue("git", "git 을 설치하세요", "no_git")])
    res = subprocess.run(
        ["git", "-C", str(vault), *args],
        capture_output=True,
        text=True,
        env=_env(),
        timeout=TIMEOUT_S,
        check=False,
    )
    if check and res.returncode != 0:
        detail = (res.stderr or res.stdout).strip().splitlines()[-1:] or ["(출력 없음)"]
        raise GitError(f"git {args[0]} 실패", [Issue("git", detail[0], "git_failed")])
    return res


def _identity(vault: Path, author: Author) -> list[str]:
    """저장소·전역 설정에 이름/이메일이 없을 때만 Vault 주인으로 채운다."""
    has_name = _git(vault, "config", "user.name", check=False).stdout.strip()
    has_email = _git(vault, "config", "user.email", check=False).stdout.strip()
    out: list[str] = []
    if not has_name:
        out += ["-c", f"user.name={author.name}"]
    if not has_email:
        out += ["-c", f"user.email={author.email}"]
    return out


def init_repo(vault: Path, author: Author) -> str:
    """Vault에 로컬 git을 시작하고 첫 commit. 이미 저장소이거나 다른 저장소 안이면 거부."""
    if is_repo(vault):
        raise GitError("이미 git 저장소입니다", [Issue(".git", "이미 존재", "exists")])
    outer = find_git_root(vault)
    if outer is not None:
        raise GitError(
            "다른 git 저장소 안입니다",
            [Issue(".", f"{outer} — Vault는 독립된 폴더여야 합니다", "vault_in_git")],
        )
    _git(vault, "init", "-q")
    _git(vault, "add", "-A")
    ident = _identity(vault, author)
    _git(vault, *ident, "commit", "-q", "--allow-empty", "-m", "myelin: start vault history")
    return head(vault) or ""


def head(vault: Path) -> str | None:
    if not is_repo(vault):
        return None
    res = _git(vault, "rev-parse", "--verify", "-q", "HEAD", check=False)
    return res.stdout.strip() or None


def _tracked(vault: Path, rel: str) -> bool:
    return _git(vault, "ls-files", "--error-unmatch", "--", rel, check=False).returncode == 0


def commit_paths(vault: Path, paths: Sequence[str], message: str, author: Author) -> str:
    """`paths` 의 변경(추가·수정·삭제)만 commit 하고 새 HEAD sha를 돌려준다."""
    if not is_repo(vault):
        raise GitError(
            "Vault가 git 저장소가 아닙니다",
            [Issue(".git", "Settings에서 '로컬 git 시작'을 먼저 하세요", "no_repo")],
        )
    specs = sorted({p for p in paths if (vault / p).exists() or _tracked(vault, p)})
    if not specs:
        raise GitError("commit할 변경이 없습니다", [Issue("git", "경로 없음", "nothing")])
    _git(vault, "add", "-A", "--", *specs)
    _git(vault, *_identity(vault, author), "commit", "-q", "-m", message, "--", *specs)
    return head(vault) or ""


def recent_commits(vault: Path, limit: int = 10) -> list[CommitInfo]:
    if head(vault) is None:
        return []
    res = _git(vault, "log", f"-{limit}", "--format=%H%x1f%s%x1f%cI")
    out: list[CommitInfo] = []
    for line in res.stdout.splitlines():
        sha, subject, when = line.split("\x1f")
        out.append(CommitInfo(sha, subject, when))
    return out


def files_in_commit(vault: Path, sha: str) -> list[str]:
    res = _git(vault, "show", "--no-renames", "--name-only", "-z", "--format=", sha)
    return [p for p in res.stdout.split("\0") if p.strip()]
