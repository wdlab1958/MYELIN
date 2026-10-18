"""Shared helpers for the MYELIN Fail-closed Guard hooks. Standard library only (ADR-0002).

Decision rule (ADR-0005): any input we cannot judge is BLOCKED (exit 2 + reason on stderr).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

CONFIG_FILE = "myelin.yaml"
LEVEL_RE = re.compile(r"^level:\s*([0-3])\s*(#.*)?$", re.M)

# Must stay identical to myelin_core.levels.LEVEL_ALLOW (tests/plugin/test_guard_sync.py).
LEVEL_ALLOW: dict[int, tuple[str, ...]] = {
    0: (),
    1: ("00_Inbox/ai-drafts", "50_Journal"),
    2: ("00_Inbox/ai-drafts", "50_Journal", "_patches", "80_Outputs/drafts"),
    3: ("00_Inbox/ai-drafts", "50_Journal", "_patches", "80_Outputs/drafts", "40_IP/candidates"),
}

BLOCK = 2
ALLOW = 0


class BlockedError(Exception):
    """Raise to block the tool call; the message is shown to Claude."""


_LOG_VAULT: Path | None = None


def block(msg: str) -> int:
    print(f"MYELIN guard: {msg}", file=sys.stderr)
    _log_block(msg)
    return BLOCK


def _log_block(msg: str) -> None:
    """Append a JSONL event to <Vault>/.myelin/guard.log so the Hub can show blocks (P6)."""
    vault = _LOG_VAULT
    if vault is None:
        for c in (os.environ.get("MYELIN_VAULT"), os.environ.get("CLAUDE_PROJECT_DIR")):
            if c and (Path(c) / CONFIG_FILE).is_file():
                vault = Path(c)
                break
    if vault is None:
        return
    try:
        log_dir = vault / ".myelin"
        log_dir.mkdir(exist_ok=True)
        with (log_dir / "guard.log").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), "message": msg}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read_event() -> dict:
    raw = sys.stdin.read()
    try:
        ev = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BlockedError(f"hook input is not JSON ({exc}) — blocking (fail-closed)") from None
    if not isinstance(ev, dict):
        raise BlockedError("hook input is not a JSON object — blocking (fail-closed)")
    return ev


def find_vault(ev: dict) -> Path:
    """MYELIN_VAULT → CLAUDE_PROJECT_DIR → event cwd → os.getcwd(); must contain myelin.yaml."""
    candidates = [
        os.environ.get("MYELIN_VAULT"),
        os.environ.get("CLAUDE_PROJECT_DIR"),
        ev.get("cwd") if isinstance(ev.get("cwd"), str) else None,
        str(Path.cwd()),
    ]
    tried: list[str] = []
    for c in candidates:
        if not c:
            continue
        p = Path(c)
        tried.append(str(p))
        try:
            root = p.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if (root / CONFIG_FILE).is_file():
            global _LOG_VAULT
            _LOG_VAULT = root
            return root
    raise BlockedError(f"Vault 를 찾을 수 없습니다 (myelin.yaml 없음). 확인한 경로: {tried} — 차단")


def vault_level(vault: Path) -> int:
    try:
        text = (vault / CONFIG_FILE).read_text(encoding="utf-8")
    except OSError as exc:
        raise BlockedError(f"myelin.yaml 을 읽을 수 없습니다 ({exc}) — 차단") from None
    m = LEVEL_RE.search(text)
    if not m:
        raise BlockedError("myelin.yaml 에 level 이 없습니다 (0~3) — 차단")
    return int(m.group(1))


def resolve_inside(vault: Path, raw: str) -> str:
    """Return the vault-relative posix path of `raw` after resolving symlinks; block if outside."""
    if not raw or not raw.strip():
        raise BlockedError("file_path 가 비어 있습니다 — 차단")
    if "\x00" in raw:
        raise BlockedError("file_path 에 NUL 문자 — 차단")
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = vault / p
    # resolve() follows symlinks in every existing component; a nonexistent leaf is kept.
    try:
        real = p.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise BlockedError(f"경로를 해석할 수 없습니다 ({exc}) — 차단") from None
    try:
        rel = real.relative_to(vault)
    except ValueError:
        raise BlockedError(f"Vault 밖 쓰기 차단 → {raw}") from None
    if ".." in Path(raw).parts:
        # resolved inside, but written with `..` — still refuse; tools must use clean paths
        raise BlockedError(f"'..' 가 포함된 경로는 허용하지 않습니다 → {raw}")
    return rel.as_posix()


def check_allowed(rel: str, level: int, raw: str) -> None:
    allowed = LEVEL_ALLOW.get(level, ())
    if level == 0:
        raise BlockedError(f"Level 0 (read-only) — 모든 쓰기 차단 → {raw}")
    for d in allowed:
        if rel.startswith(d + "/"):  # files under the dir only, never the dir itself
            if Path(rel).name.startswith("."):
                raise BlockedError(f"숨김 파일 쓰기 차단 → {raw}")
            return
    raise BlockedError(
        f"{rel} 은 사람 승인 영역입니다 (Level {level} 허용: {', '.join(allowed)}). "
        "_patches/ 에 제안하세요."
    )
