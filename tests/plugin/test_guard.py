"""MYELIN Guard — 실제 Hook처럼 별도 프로세스로 실행해 종료 코드를 검사한다 (exit 2 = 차단)."""

from __future__ import annotations

from pathlib import Path

import pytest

from .conftest import PLUGIN_GUARD, event, make_vault, run_guard, set_config

ALLOW, BLOCK = 0, 2


# ── Vault 안 Hook: 쓰기 Level 게이트 ─────────────────────────────────────────
@pytest.mark.parametrize(
    ("level", "rel", "expected"),
    [
        (1, "00_Inbox/ai-drafts/a.md", ALLOW),
        (1, "00_Inbox/ai-drafts/sub/a.md", ALLOW),
        (1, "50_Journal/reviews/2026-W42.md", ALLOW),
        (1, "_patches/20261018-link.md", BLOCK),
        (2, "_patches/20261018-link.md", ALLOW),
        (2, "80_Outputs/drafts/proposal.md", ALLOW),
        (2, "40_IP/candidates/c.md", BLOCK),
        (3, "40_IP/candidates/c.md", ALLOW),
        (0, "00_Inbox/ai-drafts/a.md", BLOCK),
        (3, "10_Domains/AI-ML-AX/새 노트.md", BLOCK),
        (3, "10_Domains/AI-ML-AX/_MOC.md", BLOCK),
        (3, "00_Inbox/clips/a.md", BLOCK),
        (3, "50_Journal/2026-10-18.md", BLOCK),
        (3, "40_IP/idea.md", BLOCK),
        (3, "myelin.yaml", BLOCK),
        (3, "CLAUDE.md", BLOCK),
        (3, ".claude/settings.json", BLOCK),
        (3, ".claude/hooks/myelin_guard.py", BLOCK),
        (3, "90_System/myelin.lock.yaml", BLOCK),
        (1, "00_Inbox/ai-drafts/a.txt", BLOCK),
    ],
)
def test_write_level_gate(tmp_path: Path, level: int, rel: str, expected: int) -> None:
    v = make_vault(tmp_path / "v", level=level)
    code, err = run_guard(v / ".claude/hooks/myelin_guard.py", event("Write", str(v / rel), v))
    assert code == expected, err
    if expected == BLOCK:
        assert err.startswith("MYELIN guard:")


@pytest.mark.parametrize("tool", ["Edit", "MultiEdit"])
def test_other_write_tools(vault: Path, vault_guard: Path, tool: str) -> None:
    assert run_guard(vault_guard, event(tool, "00_Inbox/ai-drafts/a.md", vault))[0] == ALLOW
    assert run_guard(vault_guard, event(tool, "30_Resources/a.md", vault))[0] == BLOCK


def test_notebook_edit_uses_notebook_path(vault: Path, vault_guard: Path) -> None:
    ev = event(
        "NotebookEdit", str(vault / "00_Inbox/ai-drafts/n.ipynb"), vault, key="notebook_path"
    )
    assert run_guard(vault_guard, ev)[0] == BLOCK  # .md 만 허용


def test_blocked_message_suggests_patches(vault: Path, vault_guard: Path) -> None:
    code, err = run_guard(vault_guard, event("Write", "10_Domains/AI-ML-AX/x.md", vault))
    assert code == BLOCK and "_patches/" in err and "Level 1" in err


# ── 경계 ────────────────────────────────────────────────────────────────
def test_relative_paths_resolve_against_cwd(vault: Path, vault_guard: Path) -> None:
    assert run_guard(vault_guard, event("Write", "00_Inbox/ai-drafts/a.md", vault))[0] == ALLOW
    sub = vault / "00_Inbox"
    assert run_guard(vault_guard, event("Write", "ai-drafts/b.md", sub))[0] == ALLOW
    escaped = "00_Inbox/ai-drafts/../../10_Domains/AI-ML-AX/x.md"
    assert run_guard(vault_guard, event("Write", escaped, vault))[0] == BLOCK


def test_in_vault_hook_blocks_writes_outside_vault(
    tmp_path: Path, vault: Path, vault_guard: Path
) -> None:
    code, err = run_guard(vault_guard, event("Write", str(tmp_path / "elsewhere.md"), vault))
    assert code == BLOCK and "Vault 밖" in err
    assert run_guard(vault_guard, event("Write", "../outside.md", vault))[0] == BLOCK


def test_symlink_out_of_vault_blocked(tmp_path: Path, vault: Path, vault_guard: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (vault / "00_Inbox/ai-drafts/link").symlink_to(outside, target_is_directory=True)
    code, _ = run_guard(vault_guard, event("Write", "00_Inbox/ai-drafts/link/x.md", vault))
    assert code == BLOCK


def test_symlink_into_vault_from_outside_blocked_by_plugin_hook(
    tmp_path: Path, vault: Path
) -> None:
    project = tmp_path / "code-repo"
    project.mkdir()
    (project / "notes").symlink_to(vault / "10_Domains", target_is_directory=True)
    code, err = run_guard(PLUGIN_GUARD, event("Write", "notes/AI-ML-AX/x.md", project))
    assert code == BLOCK and "심볼릭" in err


# ── 플러그인 Hook (보조): 다른 프로젝트 세션 ─────────────────────────────────
def test_plugin_hook_ignores_non_vault_projects(tmp_path: Path) -> None:
    project = tmp_path / "code-repo"
    project.mkdir()
    assert run_guard(PLUGIN_GUARD, event("Write", "src/main.py", project))[0] == ALLOW
    assert run_guard(PLUGIN_GUARD, event("Read", "src/main.py", project))[0] == ALLOW


def test_plugin_hook_guards_vault_from_other_projects(tmp_path: Path, vault: Path) -> None:
    project = tmp_path / "code-repo"
    project.mkdir()
    protected = event("Write", str(vault / "10_Domains/AI-ML-AX/x.md"), project)
    assert run_guard(PLUGIN_GUARD, protected)[0] == BLOCK
    drafts = event("Write", str(vault / "00_Inbox/ai-drafts/x.md"), project)
    assert run_guard(PLUGIN_GUARD, drafts)[0] == ALLOW


# ── 읽기 차단 (Privacy) ───────────────────────────────────────────────────
def write_note(vault: Path, rel: str, classification: str) -> None:
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nid: 20261018-0000-x\ntype: evergreen\nstatus: draft\norigin: human\n"
        f"classification: {classification}\ncreated: 2026-10-18\n---\n본문\n",
        encoding="utf-8",
    )


def test_read_blocks_ip_and_confidential(vault: Path, vault_guard: Path) -> None:
    write_note(vault, "40_IP/idea.md", "confidential")
    write_note(vault, "40_IP/candidates/c.md", "internal")
    write_note(vault, "30_Resources/secret.md", "confidential")
    write_note(vault, "30_Resources/open.md", "internal")
    cases = {
        "40_IP/idea.md": BLOCK,
        "40_IP/candidates/c.md": ALLOW,
        "30_Resources/secret.md": BLOCK,
        "30_Resources/open.md": ALLOW,
        "10_Domains/AI-ML-AX/_MOC.md": ALLOW,
    }
    for rel, expected in cases.items():
        code, err = run_guard(vault_guard, event("Read", rel, vault))
        assert code == expected, (rel, err)


def test_read_allowed_when_route_is_claude(vault: Path, vault_guard: Path) -> None:
    write_note(vault, "30_Resources/secret.md", "confidential")
    write_note(vault, "40_IP/idea.md", "confidential")
    set_config(vault, '"confidential": local', '"confidential": claude')
    assert run_guard(vault_guard, event("Read", "30_Resources/secret.md", vault))[0] == ALLOW
    set_config(vault, '"40_IP/**": local', '"40_IP/**": claude')
    assert run_guard(vault_guard, event("Read", "40_IP/idea.md", vault))[0] == ALLOW


def test_read_outside_vault_allowed_for_ingest(
    tmp_path: Path, vault: Path, vault_guard: Path
) -> None:
    doc = tmp_path / "paper.pdf"
    doc.write_bytes(b"%PDF")
    assert run_guard(vault_guard, event("Read", str(doc), vault))[0] == ALLOW


# ── Fail-closed: 판단 불가 → 차단 ──────────────────────────────────────────
@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        '{"tool_input": {"file_path": "a.md"}}',
        '{"tool_name": "Write"}',
        '{"tool_name": "Write", "tool_input": "a.md"}',
        '{"tool_name": "Write", "tool_input": {}}',
        '{"tool_name": "Write", "tool_input": {"file_path": ""}}',
        '{"tool_name": "Write", "tool_input": {"file_path": 3}}',
    ],
)
@pytest.mark.parametrize("which", ["vault", "plugin"])
def test_malformed_input_blocks(vault_guard: Path, raw: str, which: str) -> None:
    script = vault_guard if which == "vault" else PLUGIN_GUARD
    code, err = run_guard(script, None, raw=raw)
    assert code == BLOCK and err.startswith("MYELIN guard:")


def test_unrelated_tools_pass(vault: Path, vault_guard: Path) -> None:
    ev = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(vault)}
    assert run_guard(vault_guard, ev)[0] == ALLOW


def test_unknown_level_means_level_zero(vault: Path, vault_guard: Path) -> None:
    set_config(vault, "level: 1", "level: high")
    assert run_guard(vault_guard, event("Write", "00_Inbox/ai-drafts/a.md", vault))[0] == BLOCK


def test_hook_outside_a_vault_has_no_home(tmp_path: Path) -> None:
    fake = tmp_path / "proj" / ".claude" / "hooks"
    fake.mkdir(parents=True)
    script = fake / "myelin_guard.py"
    script.write_bytes(PLUGIN_GUARD.read_bytes())
    assert run_guard(script, event("Write", "x.md", tmp_path / "proj"))[0] == ALLOW


def test_guard_copies_are_identical() -> None:
    """원천 · 플러그인 · golden Vault 사본이 바이트 단위로 같아야 한다."""
    root = PLUGIN_GUARD.parents[2]
    copies = [
        root / "packages/myelin-core/src/myelin_core/resources/myelin_guard.py",
        PLUGIN_GUARD,
        root / "tests/fixtures/vaults/golden/brian/.claude/hooks/myelin_guard.py",
    ]
    assert len({p.read_bytes() for p in copies}) == 1
