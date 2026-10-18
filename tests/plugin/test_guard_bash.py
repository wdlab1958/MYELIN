"""T3 (ADR-0002 D6 / ADR-0005) — guard_bash.py: shell write bypasses are blocked."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.plugin.conftest import make_vault, run_hook

B = "guard_bash.py"


def bash(cmd: str) -> dict[str, object]:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


ALLOWED_L1 = [
    "ls -la",
    "cat 10_Domains/D1/note.md",
    "grep -rn WCET 10_Domains",
    "find . -name '*.md' | head",
    "uv run myelin doctor",
    "myelin stats --json",
    "git status",
    "git add 00_Inbox/ai-drafts/x.md",
    "git commit -m '[myelin:ingest] add'",
    "git log --oneline -5",
    "git diff",
    "echo hi > 00_Inbox/ai-drafts/x.md",
    "echo hi >> 50_Journal/w.md",
    "tee 00_Inbox/ai-drafts/t.md < /dev/null",
    "python3 scripts/thing.py",
    "ls > /dev/null 2>&1",
    "cat a.md 2>&1 | wc -l",
    "echo a; echo b",
    "mkdir -p 00_Inbox/ai-drafts/sub",
    "touch 50_Journal/today.md",
]
BLOCKED_L1 = [
    "echo hi > 10_Domains/D1/note.md",
    "echo hi >> myelin.yaml",
    "cat x > CLAUDE.md",
    "echo x > /tmp/out.md",
    "echo x 2> 10_Domains/D1/err.log",
    "echo x &> 10_Domains/D1/a.md",
    "echo x >| 10_Domains/D1/a.md",
    "tee 10_Domains/D1/note.md",
    "tee -a myelin.yaml",
    "sed -i 's/a/b/' 10_Domains/D1/note.md",
    "sed -i.bak 's/a/b/' 10_Domains/D1/note.md",
    "perl -pi -e 's/a/b/' 10_Domains/D1/note.md",
    "mv 10_Domains/D1/note.md 99_Archive/",
    "mv 00_Inbox/ai-drafts/x.md 10_Domains/D1/",
    "cp a.md 10_Domains/D1/b.md",
    "rm -rf 10_Domains",
    "rm 00_Inbox/ai-drafts/../../myelin.yaml",
    "/bin/rm -f CLAUDE.md",
    "rmdir 90_System",
    "touch 10_Domains/D1/new.md",
    "truncate -s 0 myelin.yaml",
    "chmod 777 myelin.yaml",
    "ln -s /etc 00_Inbox/ai-drafts/e",
    "python3 -c \"open('10_Domains/D1/x.md','w').write('x')\"",
    "python -c 'print(1)'",
    "node -e 'require(\"fs\")'",
    "bash -c 'echo x > 10_Domains/D1/x.md'",
    "sh -c ls",
    "eval echo x",
    "perl -e 'print 1'",
    "echo $(cat myelin.yaml) > 00_Inbox/ai-drafts/x.md",
    "echo `whoami` > 00_Inbox/ai-drafts/x.md",
    "echo x > $HOME/x.md",
    "echo x > ${VAULT}/x.md",
    "cd /tmp && echo x > y.md",
    "cd 10_Domains; touch x.md",
    "git push origin main",
    "git reset --hard",
    "git checkout -- .",
    "git restore myelin.yaml",
    "git clean -fd",
    "git stash",
    "git rm 10_Domains/D1/note.md",
    "git mv a b",
    "git rebase main",
    "git pull",
    "git switch main",
    "sudo rm -rf /",
    "env X=1 rm a",
    "echo 'unterminated > 10_Domains/D1/a.md",
    "ls > ",
    "echo x > 00_Inbox/ai-drafts/.hidden",
    "tee _patches/p.patch.md",
    "echo x > 80_Outputs/drafts/d.md",
    "echo x > 40_IP/candidates/i.md",
    "tee",
    "rsync -a src/ 10_Domains/",
    "tar -xf a.tar -C 10_Domains",
    "install -m 644 a 10_Domains/D1/a",
    "dd if=/dev/zero of=myelin.yaml",
    "shred CLAUDE.md",
]


@pytest.mark.parametrize("cmd", ALLOWED_L1)
def test_allowed_level_1(vault: Path, cmd: str) -> None:
    r = run_hook(B, bash(cmd), {"MYELIN_VAULT": str(vault)}, cwd=vault)
    assert r.allowed, f"{cmd!r} should be allowed: {r.stderr}"


@pytest.mark.parametrize("cmd", BLOCKED_L1)
def test_blocked_level_1(vault: Path, cmd: str) -> None:
    r = run_hook(B, bash(cmd), {"MYELIN_VAULT": str(vault)}, cwd=vault)
    assert r.blocked, f"{cmd!r} should be blocked (exit 2), got {r.code}: {r.stderr}"
    assert "MYELIN guard" in r.stderr


def test_level_matrix_bash(tmp_path: Path) -> None:
    v0 = make_vault(tmp_path / "v0", level=0)
    assert run_hook(B, bash("echo x > 00_Inbox/ai-drafts/x.md"), {"MYELIN_VAULT": str(v0)}).blocked
    assert run_hook(B, bash("ls"), {"MYELIN_VAULT": str(v0)}).allowed  # reads are fine at level 0
    v2 = make_vault(tmp_path / "v2", level=2)
    assert run_hook(B, bash("tee _patches/p.patch.md"), {"MYELIN_VAULT": str(v2)}).allowed
    assert run_hook(B, bash("echo x > 80_Outputs/drafts/d.md"), {"MYELIN_VAULT": str(v2)}).allowed
    assert run_hook(B, bash("echo x > 40_IP/candidates/i.md"), {"MYELIN_VAULT": str(v2)}).blocked
    v3 = make_vault(tmp_path / "v3", level=3)
    assert run_hook(B, bash("echo x > 40_IP/candidates/i.md"), {"MYELIN_VAULT": str(v3)}).allowed
    assert run_hook(B, bash("echo x > 40_IP/final.md"), {"MYELIN_VAULT": str(v3)}).blocked


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "{}",
        '{"tool_name": "Bash"}',
        '{"tool_name": "Bash", "tool_input": {}}',
        '{"tool_name": "Bash", "tool_input": {"command": ""}}',
        '{"tool_name": "Bash", "tool_input": {"command": 5}}',
        '{"tool_name": "Write", "tool_input": {"file_path": "x"}}',
    ],
)
def test_undecidable_bash_input_blocked(vault: Path, payload: str) -> None:
    assert run_hook(B, payload, {"MYELIN_VAULT": str(vault)}).blocked


def test_bash_no_vault_blocked(tmp_path: Path) -> None:
    r = run_hook(B, bash("ls"), {"MYELIN_VAULT": str(tmp_path)}, cwd=tmp_path)
    assert r.blocked and "myelin.yaml" in r.stderr
