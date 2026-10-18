"""MYELIN Fail-closed Guard — PreToolUse for Write | Edit | MultiEdit | NotebookEdit.

Standard library only. Exit 0 = allow, exit 2 = block (reason on stderr → shown to Claude).
Spec: docs/spec/MYELIN_Rev2.0.md §7.2 · ADR-0002 · ADR-0005.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard_common import (
    ALLOW,
    BlockedError,
    block,
    check_allowed,
    find_vault,
    read_event,
    resolve_inside,
    vault_level,
)

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def decide(ev: dict) -> int:
    tool = ev.get("tool_name")
    if tool not in WRITE_TOOLS:
        raise BlockedError(f"알 수 없는 쓰기 도구 {tool!r} — 차단 (fail-closed)")
    ti = ev.get("tool_input")
    if not isinstance(ti, dict):
        raise BlockedError("tool_input 이 없습니다 — 차단")
    raw = ti.get("file_path") or ti.get("notebook_path")
    if not isinstance(raw, str):
        raise BlockedError("file_path/notebook_path 가 없습니다 — 차단")
    vault = find_vault(ev)
    level = vault_level(vault)
    rel = resolve_inside(vault, raw)
    check_allowed(rel, level, raw)
    return ALLOW


def main() -> int:
    try:
        return decide(read_event())
    except BlockedError as exc:
        return block(str(exc))
    except Exception as exc:
        return block(f"내부 오류 ({type(exc).__name__}: {exc}) — 차단")


if __name__ == "__main__":
    sys.exit(main())
