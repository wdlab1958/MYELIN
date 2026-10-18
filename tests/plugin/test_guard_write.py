"""T2/T3 — guard_write.py: 허용 외 경로·Vault 밖·symlink·`..`·빈 경로·비JSON 차단 100%."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.plugin.conftest import make_vault, run_hook

W = "guard_write.py"


def ev(tool: str, path: str, **extra: object) -> dict[str, object]:
    return {
        "tool_name": tool,
        "tool_input": {"file_path": path, "content": "x"},
        "hook_event_name": "PreToolUse",
        **extra,
    }


def test_allowed_write_in_ai_drafts(vault: Path) -> None:
    r = run_hook(
        W, ev("Write", str(vault / "00_Inbox/ai-drafts/new.md")), {"MYELIN_VAULT": str(vault)}
    )
    assert r.allowed, r.stderr
    r = run_hook(W, ev("Edit", "50_Journal/w.md"), {"MYELIN_VAULT": str(vault)})  # relative path
    assert r.allowed, r.stderr


@pytest.mark.parametrize(
    "rel",
    [
        "10_Domains/D1/note.md",
        "10_Domains/D1/new.md",
        "myelin.yaml",
        "CLAUDE.md",
        "90_System/templates/x.md",
        "40_IP/candidates/x.md",
        "_patches/p.patch.md",
        "80_Outputs/drafts/x.md",
        "00_Inbox/x.md",
        "00_Inbox/clips/x.md",
        ".myelin/index.db",
        ".claude/settings.json",
        "00_Inbox/ai-drafts/.hidden.md",
        "00_Inbox/ai-drafts",
        "00_Inbox/ai-drafts-evil/x.md",
    ],
)
def test_blocked_paths_at_level_1(vault: Path, rel: str) -> None:
    r = run_hook(W, ev("Write", str(vault / rel)), {"MYELIN_VAULT": str(vault)})
    assert r.blocked, f"{rel} should be blocked: {r.stderr}"
    assert "MYELIN guard" in r.stderr


def test_outside_vault_and_dotdot(vault: Path, tmp_path: Path) -> None:
    r = run_hook(W, ev("Write", str(tmp_path / "elsewhere.md")), {"MYELIN_VAULT": str(vault)})
    assert r.blocked and "Vault 밖" in r.stderr
    r = run_hook(
        W,
        ev("Write", str(vault / "00_Inbox/ai-drafts/../../myelin.yaml")),
        {"MYELIN_VAULT": str(vault)},
    )
    assert r.blocked
    # `..` that still resolves inside an allowed dir is refused too
    r = run_hook(
        W, ev("Write", "00_Inbox/ai-drafts/../ai-drafts/x.md"), {"MYELIN_VAULT": str(vault)}
    )
    assert r.blocked and "'..'" in r.stderr
    r = run_hook(W, ev("Write", "/etc/passwd"), {"MYELIN_VAULT": str(vault)})
    assert r.blocked
    r = run_hook(W, ev("Write", "~/x.md"), {"MYELIN_VAULT": str(vault)})
    assert r.blocked


def test_symlink_escape(vault: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (vault / "00_Inbox/ai-drafts/link").symlink_to(outside, target_is_directory=True)
    r = run_hook(
        W, ev("Write", str(vault / "00_Inbox/ai-drafts/link/x.md")), {"MYELIN_VAULT": str(vault)}
    )
    assert r.blocked and "Vault 밖" in r.stderr
    # symlink inside the vault that points at a human-only area
    (vault / "00_Inbox/ai-drafts/moc").symlink_to(vault / "10_Domains/D1", target_is_directory=True)
    r = run_hook(
        W, ev("Write", str(vault / "00_Inbox/ai-drafts/moc/_MOC.md")), {"MYELIN_VAULT": str(vault)}
    )
    assert r.blocked and "사람 승인 영역" in r.stderr
    # file symlink
    (vault / "00_Inbox/ai-drafts/cfg.md").symlink_to(vault / "myelin.yaml")
    r = run_hook(
        W, ev("Edit", str(vault / "00_Inbox/ai-drafts/cfg.md")), {"MYELIN_VAULT": str(vault)}
    )
    assert r.blocked


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "",
        "[]",
        "42",
        '{"tool_name": "Write"}',
        '{"tool_name": "Write", "tool_input": {}}',
        '{"tool_name": "Write", "tool_input": {"file_path": ""}}',
        '{"tool_name": "Write", "tool_input": {"file_path": "   "}}',
        '{"tool_name": "Write", "tool_input": {"file_path": 3}}',
        '{"tool_name": "Bash", "tool_input": {"command": "ls"}}',  # wrong tool for this hook
        '{"tool_name": "Foo", "tool_input": {"file_path": "00_Inbox/ai-drafts/x.md"}}',
        '{"tool_input": {"file_path": "00_Inbox/ai-drafts/x.md"}}',
    ],
)
def test_undecidable_input_is_blocked(vault: Path, payload: str) -> None:
    r = run_hook(W, payload, {"MYELIN_VAULT": str(vault)})
    assert r.blocked, f"{payload!r} must be blocked; stderr={r.stderr}"


def test_no_vault_is_blocked(tmp_path: Path) -> None:
    r = run_hook(
        W,
        ev("Write", str(tmp_path / "00_Inbox/ai-drafts/x.md")),
        {"MYELIN_VAULT": str(tmp_path)},
        cwd=tmp_path,
    )
    assert r.blocked and "myelin.yaml 없음" in r.stderr
    r = run_hook(W, ev("Write", "00_Inbox/ai-drafts/x.md", cwd=str(tmp_path)), cwd=tmp_path)
    assert r.blocked


def test_vault_discovery_order(vault: Path, tmp_path: Path) -> None:
    other = make_vault(tmp_path / "other", level=0)
    # MYELIN_VAULT wins over CLAUDE_PROJECT_DIR
    r = run_hook(
        W,
        ev("Write", "00_Inbox/ai-drafts/x.md"),
        {"MYELIN_VAULT": str(vault), "CLAUDE_PROJECT_DIR": str(other)},
    )
    assert r.allowed
    # CLAUDE_PROJECT_DIR used when MYELIN_VAULT missing
    r = run_hook(W, ev("Write", "00_Inbox/ai-drafts/x.md"), {"CLAUDE_PROJECT_DIR": str(other)})
    assert r.blocked and "Level 0" in r.stderr
    # event cwd used as fallback
    r = run_hook(W, ev("Write", "00_Inbox/ai-drafts/x.md", cwd=str(vault)))
    assert r.allowed
    # process cwd as last resort
    r = run_hook(W, ev("Write", "00_Inbox/ai-drafts/x.md"), cwd=vault)
    assert r.allowed


@pytest.mark.parametrize(
    "level,rel,ok",
    [
        (0, "00_Inbox/ai-drafts/x.md", False),
        (0, "50_Journal/x.md", False),
        (1, "00_Inbox/ai-drafts/x.md", True),
        (1, "50_Journal/x.md", True),
        (1, "_patches/x.patch.md", False),
        (1, "80_Outputs/drafts/x.md", False),
        (2, "_patches/x.patch.md", True),
        (2, "80_Outputs/drafts/x.md", True),
        (2, "40_IP/candidates/x.md", False),
        (2, "80_Outputs/final.md", False),
        (3, "40_IP/candidates/x.md", True),  # LOCAL session only (ADR-0011)
        (3, "40_IP/x.md", False),
        (3, "10_Domains/D1/x.md", False),
    ],
)
def test_level_matrix(tmp_path: Path, level: int, rel: str, ok: bool) -> None:
    v = make_vault(tmp_path / f"v{level}", level=level)
    env = {"MYELIN_VAULT": str(v), "MYELIN_LLM": "local"}
    r = run_hook(W, ev("Write", str(v / rel)), env)
    assert r.allowed is ok, f"level={level} rel={rel}: {r.stderr}"
    # EXTERNAL session (MYELIN_LLM unset): identical except that 40_IP/** is always blocked
    r = run_hook(W, ev("Write", str(v / rel)), {"MYELIN_VAULT": str(v)})
    assert r.allowed is (ok and not rel.startswith("40_IP/")), f"external {rel}: {r.stderr}"


def test_bad_or_missing_level_blocks(vault: Path) -> None:
    (vault / "myelin.yaml").write_text(
        "owner: {name: t}\npacks: [myelin.core]\ndomains: {primary: D1}\n", encoding="utf-8"
    )
    r = run_hook(W, ev("Write", "00_Inbox/ai-drafts/x.md"), {"MYELIN_VAULT": str(vault)})
    assert r.blocked and "level" in r.stderr
    (vault / "myelin.yaml").write_text("level: 7\n", encoding="utf-8")
    assert run_hook(W, ev("Write", "00_Inbox/ai-drafts/x.md"), {"MYELIN_VAULT": str(vault)}).blocked


def test_notebook_edit_uses_notebook_path(vault: Path) -> None:
    # notebook_path is inspected like file_path; .ipynb is not a note, so it is blocked everywhere
    not_md = {
        "tool_name": "NotebookEdit",
        "tool_input": {"notebook_path": str(vault / "00_Inbox/ai-drafts/n.ipynb")},
    }
    bad = {
        "tool_name": "NotebookEdit",
        "tool_input": {"notebook_path": str(vault / "10_Domains/D1/n.ipynb")},
    }
    r = run_hook(W, not_md, {"MYELIN_VAULT": str(vault)})
    assert r.blocked and ".md" in r.stderr
    r = run_hook(W, bad, {"MYELIN_VAULT": str(vault)})
    assert r.blocked and "사람 승인 영역" in r.stderr
    assert run_hook(
        W,
        {"tool_name": "MultiEdit", "tool_input": {"file_path": "50_Journal/x.md"}},
        {"MYELIN_VAULT": str(vault)},
    ).allowed
