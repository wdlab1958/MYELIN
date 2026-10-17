from pathlib import Path

from myelin_core.safety import (
    find_git_root,
    find_source_root,
    git_remotes,
    init_target_issues,
    location_issues,
)

ROOT = Path(__file__).resolve().parents[3]


def make_repo(path: Path, remote: str | None = None) -> Path:
    (path / ".git").mkdir(parents=True)
    if remote:
        (path / ".git" / "config").write_text(
            f'[core]\n\tbare = false\n[remote "origin"]\n\turl = {remote}\n', encoding="utf-8"
        )
    return path


def codes(issues: list) -> set[str]:  # type: ignore[type-arg]
    return {i.code for i in issues}


def test_init_target_ok_for_new_and_empty_dirs(tmp_path: Path) -> None:
    assert init_target_issues(tmp_path / "new") == []
    (tmp_path / "empty").mkdir()
    assert init_target_issues(tmp_path / "empty") == []


def test_init_target_refusals(tmp_path: Path) -> None:
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "x.md").write_text("x", encoding="utf-8")
    assert codes(init_target_issues(occupied)) == {"not_empty"}
    a_file = tmp_path / "file"
    a_file.write_text("x", encoding="utf-8")
    assert codes(init_target_issues(a_file)) == {"not_a_directory"}
    repo = make_repo(tmp_path / "repo")
    assert codes(init_target_issues(repo / "vault")) == {"vault_in_git"}
    assert codes(init_target_issues(ROOT / "anything")) == {"vault_in_source"}


def test_finders(tmp_path: Path) -> None:
    assert find_source_root(ROOT / "packs" / "x") == ROOT
    assert find_source_root(tmp_path) is None
    repo = make_repo(tmp_path / "r")
    assert find_git_root(repo / "a" / "b") == repo


def test_git_remotes(tmp_path: Path) -> None:
    assert git_remotes(tmp_path) == []
    repo = make_repo(tmp_path / "r", "git@github.com:me/vault.git")
    assert git_remotes(repo) == ["git@github.com:me/vault.git"]
    (repo / ".git" / "config").write_text("[broken\n", encoding="utf-8")
    assert git_remotes(repo) == []


def test_location_issues(tmp_path: Path) -> None:
    assert location_issues(tmp_path / "plain") == []
    src = location_issues(ROOT / "tests")
    assert [(s, i.code) for s, i in src] == [("error", "vault_in_source")]

    outer = make_repo(tmp_path / "outer")
    (outer / "vault").mkdir()
    assert [(s, i.code) for s, i in location_issues(outer / "vault")] == [
        ("warning", "vault_in_git")
    ]

    own = make_repo(tmp_path / "own", "https://github.com/me/notes.git")
    assert [(s, i.code) for s, i in location_issues(own)] == [("warning", "public_remote")]

    private = make_repo(tmp_path / "private", "ssh://git@nas.local/notes.git")
    assert location_issues(private) == []
