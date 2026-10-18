"""ADR-0005: Guard LEVEL_ALLOW copy equals myelin_core.levels.LEVEL_ALLOW; hooks are stdlib-only."""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

from myelin_core.levels import LEVEL_ALLOW, SKILLS, allowed_dirs

HOOKS = Path(__file__).resolve().parents[2] / "plugin" / "hooks"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.path.insert(0, str(HOOKS))
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    finally:
        sys.path.pop(0)
    return mod


def test_level_allow_in_sync() -> None:
    common = _load("guard_common")
    assert common.LEVEL_ALLOW == LEVEL_ALLOW
    for lvl in range(4):
        assert tuple(common.LEVEL_ALLOW[lvl]) == allowed_dirs(lvl)


def test_every_skill_scope_is_allowed_at_its_level() -> None:
    for s in SKILLS:
        assert s.write_scope in allowed_dirs(s.min_level), s
        if s.min_level > 0:
            assert s.write_scope not in allowed_dirs(s.min_level - 1), s


def test_hooks_are_stdlib_only() -> None:
    stdlib = set(sys.stdlib_module_names)
    for script in HOOKS.glob("*.py"):
        tree = ast.parse(script.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for n in names:
                assert n in stdlib or n == "guard_common", f"{script.name} imports non-stdlib {n!r}"


def test_hooks_json_wires_both_guards() -> None:
    cfg = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))
    pre = cfg["hooks"]["PreToolUse"]
    matchers = {h["matcher"]: h["hooks"][0] for h in pre}
    assert set(matchers) == {"Write|Edit|MultiEdit|NotebookEdit", "Bash"}
    for m, h in matchers.items():
        assert h["type"] == "command" and h["command"] == "python3"
        assert h["args"][0].startswith("${CLAUDE_PLUGIN_ROOT}/hooks/guard_")
        assert h["onFailure"] == "block" and h["timeout"] <= 10, m
    assert matchers["Bash"]["args"][0].endswith("guard_bash.py")
