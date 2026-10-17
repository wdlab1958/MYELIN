"""P0: the repository matches spec §10.1 and the session-protocol files exist."""

from __future__ import annotations

import re
from pathlib import Path

REQUIRED = [
    "CLAUDE.md",
    "PHASE_STATE.md",
    "Makefile",
    "docs/spec/MYELIN_Rev2.0.md",
    "docs/adr/0001-tech-stack.md",
    "docs/adr/0002-plugin-spec.md",
    "packs/myelin.core",
    "packs/brian.physical-ai",
    "packs/a3.security-consulting",
    "packages/myelin-core/pyproject.toml",
    "packages/myelin-cli/pyproject.toml",
    "packages/myelin-mcp/pyproject.toml",
    "packages/myelin-hub/api/pyproject.toml",
    "packages/myelin-hub/web",
    "plugin/.claude-plugin/plugin.json",
    "plugin/hooks/hooks.json",
    "design/tokens.json",
    "theme/obsidian-myelin-emboss",
    "tests/fixtures/vaults",
    "tests/e2e",
    ".github/workflows/ci.yml",
]


def test_required_paths_exist(repo_root: Path) -> None:
    missing = [p for p in REQUIRED if not (repo_root / p).exists()]
    assert not missing, f"missing from §10.1 layout: {missing}"


def test_phase_docs_exist(repo_root: Path) -> None:
    for n in range(9):
        p = repo_root / f"docs/phases/P{n}.md"
        assert p.exists(), p
        assert "## Task 목록" in p.read_text(encoding="utf-8")


def test_phase_state_has_header(repo_root: Path) -> None:
    text = (repo_root / "PHASE_STATE.md").read_text(encoding="utf-8")
    assert re.search(r"^current_phase: P\d$", text, re.M)
    assert re.search(r"^status: (in_progress|gate_pending|awaiting_approval)\b", text, re.M)
    for section in ("## Done", "## Next", "## Blockers", "## Decisions", "## Backlog"):
        assert section in text, section
