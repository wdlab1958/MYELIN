"""T4/T5 — settings.json template and level helpers."""

from __future__ import annotations

import json

import pytest

from myelin_core.levels import LEVEL_ALLOW, allowed_dirs, available_skills
from myelin_core.settings_template import (
    BASH_DENY,
    HUMAN_ONLY_PATHS,
    claude_settings,
    render_claude_settings,
)


def test_settings_template_uses_edit_rules_only() -> None:
    s = claude_settings()
    deny = s["permissions"]["deny"]  # type: ignore[index]
    assert all(
        not d.startswith("Write(") for d in deny
    )  # Write(...) rules are never consulted (ADR-0002 D5)
    assert "Edit(./10_Domains/**)" in deny and "Edit(./myelin.yaml)" in deny
    assert set(d for d in deny if d.startswith("Bash(")) == set(BASH_DENY)
    assert len([d for d in deny if d.startswith("Edit(")]) == len(HUMAN_ONLY_PATHS)
    assert "Bash(git commit *)" in s["permissions"]["ask"]  # type: ignore[index]
    assert json.loads(render_claude_settings()) == s


def test_allowed_dirs_cumulative() -> None:
    for lvl in range(1, 4):
        assert set(allowed_dirs(lvl - 1)) <= set(allowed_dirs(lvl))
    assert allowed_dirs(0) == ()
    assert "40_IP/candidates" in allowed_dirs(3) and "40_IP/candidates" not in allowed_dirs(2)
    with pytest.raises(ValueError, match="level"):
        allowed_dirs(4)
    assert set(LEVEL_ALLOW) == {0, 1, 2, 3}
    assert [s.name for s in available_skills(1)] == ["ingest", "distill", "interview", "review"]


def test_settings_ask_for_script_interpreters() -> None:
    """Threat model T02 — script execution is not analysed by the Bash guard, so it asks."""
    ask = claude_settings()["permissions"]["ask"]  # type: ignore[index]
    assert {"Bash(python *)", "Bash(python3 *)", "Bash(uv run python *)", "Bash(node *)"} <= set(
        ask
    )
