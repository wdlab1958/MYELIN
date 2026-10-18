"""MYELIN Confidential-routing Guard — PreToolUse for Read | Grep | Glob (ADR-0011).

Standard library only. Exit 0 = allow, exit 2 = block (Korean reason on stderr → shown to Claude).

A session is LOCAL iff the environment has `MYELIN_LLM=local`; LOCAL sessions are not restricted
here. In an EXTERNAL session (anything else) this hook blocks:

- Read of a file that resolves (symlinks followed) inside `<Vault>/40_IP/`, or of a `.md` whose
  frontmatter says `classification: confidential` (anywhere in the Vault; unparseable = block);
- Grep/Glob whose `path` lies inside 40_IP/, or covers the whole Vault (root, an ancestor, or
  absent → cwd) while 40_IP/ holds any file — the reason asks for a `path` outside 40_IP;
- Grep whose `path` (a directory) contains a confidential note anywhere beneath.

Everything else — paths outside the Vault, notes without a confidential classification — is allowed.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard_common import (
    ALLOW,
    BlockedError,
    block,
    check_read_target,
    check_search_root,
    find_vault,
    is_local_session,
    read_event,
    resolve_any,
)

READ_TOOLS = {"Read", "Grep", "Glob"}


def decide(ev: dict) -> int:
    tool = ev.get("tool_name")
    if tool not in READ_TOOLS:
        raise BlockedError(f"알 수 없는 읽기 도구 {tool!r} — 차단 (fail-closed)")
    ti = ev.get("tool_input")
    if not isinstance(ti, dict):
        raise BlockedError("tool_input 이 없습니다 — 차단")
    if is_local_session():
        return ALLOW  # MYELIN_LLM=local: confidential routing satisfied (ADR-0011)
    vault = find_vault(ev)
    cwd = ev.get("cwd")
    base = Path(cwd) if isinstance(cwd, str) and cwd and Path(cwd).is_absolute() else vault
    if tool == "Read":
        raw = ti.get("file_path")
        if not isinstance(raw, str) or not raw.strip():
            raise BlockedError("file_path 가 없습니다 — 차단")
        check_read_target(resolve_any(raw, base), vault, raw)
        return ALLOW
    raw = ti.get("path")
    if raw is None:
        if not isinstance(cwd, str) or not cwd:
            raise BlockedError(f"{tool} 에 path 가 없고 cwd 도 알 수 없습니다 — 차단 (fail-closed)")
        raw = cwd
    if not isinstance(raw, str) or not raw.strip():
        raise BlockedError(f"{tool} 의 path 가 비어 있습니다 — 차단")
    check_search_root(resolve_any(raw, base), vault, raw, contents=(tool == "Grep"))
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
