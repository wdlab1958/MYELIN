"""Vault 위치 안전 검사 — 개인 지식이 공개 저장소로 새지 않도록 (P2-T10, ADR-0005).

원칙: Vault는 각자의 기기에, MYELIN 소스와 분리해서 둔다.
- MYELIN 소스 폴더 안의 Vault → 금지 (fork에 push될 위험)
- 다른 git 저장소 안의 Vault → init 거부, doctor 경고
- Vault 자체 git의 원격이 공개 코드 호스팅이면 → doctor 경고 (비공개인지 확인 요청)
"""

from __future__ import annotations

import configparser
from pathlib import Path

from myelin_core.errors import Issue

PUBLIC_HOSTS = ("github.com", "gitlab.com", "bitbucket.org", "codeberg.org")


def _ancestors(path: Path) -> list[Path]:
    p = path.absolute()
    return [p, *p.parents]


def find_git_root(path: Path) -> Path | None:
    for p in _ancestors(path):
        if (p / ".git").exists():
            return p
    return None


def is_myelin_source(path: Path) -> bool:
    return (path / "packs" / "myelin.core" / "pack.yaml").is_file() and (
        path / "scripts" / "gate.py"
    ).is_file()


def find_source_root(path: Path) -> Path | None:
    for p in _ancestors(path):
        if is_myelin_source(p):
            return p
    return None


def git_remotes(repo: Path) -> list[str]:
    config = repo / ".git" / "config"
    if not config.is_file():
        return []
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    try:
        parser.read(config, encoding="utf-8")
    except configparser.Error:
        return []
    return [
        parser[s]["url"]
        for s in parser.sections()
        if s.startswith('remote "') and "url" in parser[s]
    ]


def init_target_issues(target: Path) -> list[Issue]:
    """`myelin init` 대상 경로 검사. 하나라도 있으면 생성하지 않는다 (fail-closed)."""
    loc = str(target)
    issues: list[Issue] = []
    source = find_source_root(target)
    if source is not None:
        issues.append(
            Issue(
                loc,
                f"MYELIN 소스 폴더({source}) 안에는 Vault를 만들 수 없습니다 — "
                "개인 노트가 공개 저장소에 올라갈 수 있습니다. 소스와 분리된 경로를 쓰세요.",
                "vault_in_source",
            )
        )
    else:
        repo = find_git_root(target)
        if repo is not None:
            issues.append(
                Issue(
                    loc,
                    f"git 저장소({repo}) 안에는 Vault를 만들지 않습니다 — "
                    "Vault는 독립된 폴더에 만들고, 필요하면 그 폴더에서 비공개 git을 시작하세요.",
                    "vault_in_git",
                )
            )
    if target.exists() and not target.is_dir():
        issues.append(Issue(loc, "파일이 이미 있습니다 (디렉터리가 아님)", "not_a_directory"))
    elif target.is_dir() and any(target.iterdir()):
        issues.append(Issue(loc, "비어 있지 않은 디렉터리입니다 — 덮어쓰지 않습니다", "not_empty"))
    return issues


def location_issues(vault: Path) -> list[tuple[str, Issue]]:
    """doctor용: (severity, Issue) 목록."""
    out: list[tuple[str, Issue]] = []
    source = find_source_root(vault)
    if source is not None:
        out.append(
            (
                "error",
                Issue(".", f"Vault가 MYELIN 소스 폴더({source}) 안에 있습니다", "vault_in_source"),
            )
        )
        return out
    repo = find_git_root(vault)
    if repo is None:
        return out
    if repo.resolve() != vault.resolve():
        out.append(
            (
                "warning",
                Issue(".", f"Vault가 다른 git 저장소({repo}) 안에 있습니다", "vault_in_git"),
            )
        )
    for url in git_remotes(repo):
        if any(host in url for host in PUBLIC_HOSTS):
            out.append(
                (
                    "warning",
                    Issue(
                        ".",
                        f"git 원격 {url} — 공개 호스팅입니다. 비공개 저장소인지 확인하세요",
                        "public_remote",
                    ),
                )
            )
    return out
