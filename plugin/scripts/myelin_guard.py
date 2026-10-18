#!/usr/bin/env python3
"""MYELIN Guard — Claude Code PreToolUse Hook (fail-closed). ADR-0002 Rev 2.

표준 라이브러리만 사용한다 (Python 3.9+). 이 파일 하나가 세 곳에 똑같이 놓인다:
  - Vault `.claude/hooks/myelin_guard.py`  — 주 장치. 자기 위치로 Vault를 안다.
  - 플러그인 `scripts/myelin_guard.py`      — 보조. 다른 프로젝트 세션에서 Vault로 쓰는 것을 막는다.
  - 원천 `myelin_core/resources/`          — init이 여기서 복사한다.

판정
  쓰기(Write·Edit·MultiEdit·NotebookEdit)
    - Vault 안: myelin.yaml `level` 이 허용하는 폴더의 `.md` 만 통과. 나머지는 차단.
    - Vault 안 Hook인데 Vault 밖으로 쓰기 → 차단.
    - 심볼릭 링크로 Vault 경계를 넘나드는 경로 → 차단.
    - Vault와 무관한 경로 → 통과 (플러그인 Hook이 다른 프로젝트에 간섭하지 않도록).
  읽기(Read)
    - `40_IP/`(candidates 제외)와 `classification: confidential` 노트 → 차단
      (llm.route 가 local일 때 — 기본값). Claude가 읽으면 내용이 Anthropic으로 전송되기 때문.
  판단할 수 없는 입력·내부 오류 → 차단 (exit 2). exit 1은 Claude Code에서 비차단이므로 쓰지 않는다.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import IO, Any

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
READ_TOOLS = {"Read"}
MARKERS = ("myelin.yaml", "90_System/myelin.lock.yaml")
LEVEL_PREFIXES = (
    (),  # 0: 읽기 전용
    ("00_Inbox/ai-drafts/", "50_Journal/reviews/"),  # 1: 초안
    ("_patches/", "80_Outputs/drafts/"),  # 2: 링크·산출물 제안
    ("40_IP/candidates/",),  # 3: 정기 리뷰·특허 후보
)
IP_DIR = "40_IP/"
IP_OPEN = "40_IP/candidates/"
BLOCK = 2


class Block(Exception):
    """차단 사유."""


def allowed_prefixes(level: int) -> tuple[str, ...]:
    out: tuple[str, ...] = ()
    for lv in range(0, max(0, min(level, 3)) + 1):
        out += LEVEL_PREFIXES[lv]
    return out


def is_vault(path: Path) -> bool:
    return all((path / marker).is_file() for marker in MARKERS)


def find_vault(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if is_vault(candidate):
            return candidate
    return None


def home_vault() -> Path | None:
    """이 스크립트가 `<vault>/.claude/hooks/` 에 있으면 그 Vault."""
    here = Path(__file__).resolve()
    if here.parent.name == "hooks" and here.parent.parent.name == ".claude":
        vault = here.parents[2]
        return vault if is_vault(vault) else None
    return None


def _config(vault: Path) -> str:
    return (vault / "myelin.yaml").read_text(encoding="utf-8")


def vault_level(vault: Path) -> int:
    m = re.search(r"^level:\s*([0-3])\s*(#.*)?$", _config(vault), re.MULTILINE)
    return int(m.group(1)) if m else 0  # 알 수 없으면 가장 낮은 Level


def route_is_local(vault: Path, key: str) -> bool:
    pattern = r"^\s+[\"']?" + re.escape(key) + r"[\"']?\s*:\s*([A-Za-z]+)"
    m = re.search(pattern, _config(vault), re.MULTILINE)
    return m is None or m.group(1) != "claude"  # 설정이 없으면 local (fail-closed)


def is_confidential(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8") as fh:
            head = fh.read(8192)
    except (OSError, UnicodeDecodeError):
        return False
    if not head.lstrip("﻿").startswith("---"):
        return False
    end = head.find("\n---", 3)
    block = head[: end if end != -1 else len(head)]
    return re.search(r"^classification:\s*[\"']?confidential\b", block, re.MULTILINE) is not None


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def check(event: Any, home: Path | None) -> str | None:
    """차단 사유를 돌려준다. None이면 통과."""
    if not isinstance(event, dict):
        raise Block("Hook 입력이 JSON 객체가 아닙니다")
    tool = event["tool_name"]
    if tool not in WRITE_TOOLS and tool not in READ_TOOLS:
        return None
    tool_input = event["tool_input"]
    if not isinstance(tool_input, dict):
        raise Block("tool_input 이 객체가 아닙니다")
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
        raise Block("대상 경로를 알 수 없습니다")

    cwd = event.get("cwd") or (str(home) if home else os.getcwd())
    lexical = Path(os.path.abspath(os.path.join(os.path.expanduser(str(cwd)), raw)))
    real = Path(os.path.realpath(lexical))
    writing = tool in WRITE_TOOLS

    if home is not None and writing and not (_inside(lexical, home) and _inside(real, home)):
        return f"Vault 밖 쓰기 차단 — {raw}"

    v_lex, v_real = find_vault(lexical), find_vault(real)
    if writing and v_lex != v_real:
        return f"심볼릭 링크가 Vault 경계를 넘습니다 — {raw}"
    vault = v_real or v_lex
    if vault is None:
        return None  # Vault와 무관
    rel = (real if v_real else lexical).relative_to(vault).as_posix()

    if not writing:
        if (
            rel.startswith(IP_DIR)
            and not rel.startswith(IP_OPEN)
            and route_is_local(vault, "40_IP/**")
        ):
            return f"{rel} — 40_IP는 로컬 LLM 전용입니다 (llm.route). Claude로 보내지 않습니다"
        if real.is_file() and is_confidential(real) and route_is_local(vault, "confidential"):
            return f"{rel} — confidential 노트는 로컬 LLM 전용입니다 (llm.route)"
        return None

    level = vault_level(vault)
    allowed = allowed_prefixes(level)
    if rel.endswith(".md") and any(rel.startswith(p) for p in allowed):
        return None
    where = ", ".join(allowed) if allowed else "없음 (Level 0: 읽기 전용)"
    return (
        f"{rel} 은(는) 사람 승인 영역입니다. Level {level} 에서 Claude가 쓸 수 있는 곳: {where}. "
        "기존 노트의 변경은 `_patches/YYYYMMDD-<주제>.md` 로 제안하세요 (Level 2 이상)."
    )


def main(stdin: IO[str] | None = None, stderr: IO[str] | None = None) -> int:
    stdin = stdin or sys.stdin
    stderr = stderr or sys.stderr
    try:
        reason = check(json.load(stdin), home_vault())
    except Block as exc:
        reason = str(exc)
    except Exception as exc:  # 판단 불가 = 차단
        reason = f"Guard가 입력을 판단할 수 없어 차단합니다 ({type(exc).__name__}: {exc})"
    if reason:
        print(f"MYELIN guard: {reason}", file=stderr)
        return BLOCK
    return 0


if __name__ == "__main__":
    sys.exit(main())
