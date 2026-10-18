"""Shared helpers for the MYELIN Fail-closed Guard hooks. Standard library only (ADR-0002).

Decision rule (ADR-0005): any input we cannot judge is BLOCKED (exit 2 + reason on stderr).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

CONFIG_FILE = "myelin.yaml"
# ADR-0011: a session is LOCAL only when the operator set MYELIN_LLM=local (exact value).
LLM_ENV = "MYELIN_LLM"
LLM_LOCAL = "local"
IP_DIR = "40_IP"
CONFIDENTIAL = "confidential"
KNOWN_CLASSIFICATIONS = ("public", "internal", CONFIDENTIAL)
FM_DELIM = "---"
# first `---` block only; a top-level `classification:` line (no indentation)
CLASSIFICATION_RE = re.compile(r"^classification:(.*)$", re.M)
FRONTMATTER_MAX_BYTES = 64 * 1024
# top-level `level: N` only (a space is required: `level:1` is a YAML scalar, not a key)
LEVEL_RE = re.compile(r"^level:[ \t]+([0-3])[ \t]*(#.*)?$", re.M)
# C0/DEL controls and Unicode bidi overrides/isolates (filename spoofing) are never allowed
UNSAFE_CHAR_RE = re.compile("[\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]")

# Must stay identical to myelin_core.levels.LEVEL_ALLOW (tests/plugin/test_guard_sync.py).
LEVEL_ALLOW: dict[int, tuple[str, ...]] = {
    0: (),
    1: ("00_Inbox/ai-drafts", "50_Journal"),
    2: ("00_Inbox/ai-drafts", "50_Journal", "_patches", "80_Outputs/drafts"),
    3: ("00_Inbox/ai-drafts", "50_Journal", "_patches", "80_Outputs/drafts", "40_IP/candidates"),
}

PATCHES_DIR = "_patches"
BLOCK = 2
ALLOW = 0


class BlockedError(Exception):
    """Raise to block the tool call; the message is shown to Claude."""


_LOG_VAULT: Path | None = None


def block(msg: str) -> int:
    # stderr closed/EPIPE must still exit 2 (never fall through to allow, never exit 120)
    try:
        print(f"MYELIN guard: {msg}", file=sys.stderr, flush=True)
    except (OSError, ValueError):
        with contextlib.suppress(OSError, ValueError):
            sys.stderr.close()  # a closed stream is skipped by the interpreter's exit flush
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
    found = LEVEL_RE.findall(text)
    if not found:
        raise BlockedError("myelin.yaml 에 level 이 없습니다 (0~3) — 차단")
    if len(found) > 1:
        raise BlockedError("myelin.yaml 에 level 이 여러 번 있습니다 (판단 불가) — 차단")
    return int(found[0][0])


def resolve_inside(vault: Path, raw: str) -> str:
    """Return the vault-relative posix path of `raw` after resolving symlinks; block if outside."""
    if not raw or not raw.strip():
        raise BlockedError("file_path 가 비어 있습니다 — 차단")
    if UNSAFE_CHAR_RE.search(raw):
        raise BlockedError("file_path 에 제어 문자/양방향 제어 문자 — 차단")
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


def is_local_session() -> bool:
    """LOCAL iff MYELIN_LLM=local (ADR-0011). Anything else (unset, empty, 'Local') is EXTERNAL."""
    return os.environ.get(LLM_ENV) == LLM_LOCAL


def in_ip_dir(rel: str) -> bool:
    """True when the Vault-relative path is 40_IP itself or anything beneath it (NFC-normalised)."""
    norm = unicodedata.normalize("NFC", rel)
    return norm == IP_DIR or norm.startswith(IP_DIR + "/")


def require_local_for_ip(rel: str, raw: str, action: str = "쓰기") -> None:
    """40_IP/** is routed to a local LLM (myelin.yaml llm.route): refused in EXTERNAL sessions."""
    if in_ip_dir(rel) and not is_local_session():
        raise BlockedError(
            f"외부 LLM 세션에서는 40_IP/** {action}를 할 수 없습니다 → {raw} "
            f"(기밀 라우팅 ADR-0011: 로컬 모델 세션에서 {LLM_ENV}={LLM_LOCAL} 로 실행하세요)"
        )


def classification_of(path: Path) -> str | None:
    """Return the frontmatter `classification` of a note, None when the file has no frontmatter.

    Standard-library parse of the first `---` block (ADR-0011). Fail-closed: an unclosed block,
    a duplicated or unreadable key, an unknown value or an unreadable file raise BlockedError.
    """
    try:
        with path.open("rb") as fh:
            head = fh.read(FRONTMATTER_MAX_BYTES)
    except OSError as exc:
        raise BlockedError(
            f"노트를 읽을 수 없어 기밀 여부를 판단할 수 없습니다 ({exc}) — 차단"
        ) from None
    try:
        text = head.decode("utf-8")
    except UnicodeDecodeError:
        if head[:3] == b"---":
            raise BlockedError(
                f"frontmatter 를 UTF-8 로 읽을 수 없습니다 → {path.name} — 차단"
            ) from None
        return None  # binary file: no frontmatter
    text = text.removeprefix("\ufeff")
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != FM_DELIM:
        return None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r") in (FM_DELIM, "..."):
            yaml_text = "\n".join(lines[1:i])
            break
    else:
        raise BlockedError(
            f"frontmatter 가 닫히지 않아 기밀 여부를 판단할 수 없습니다 → {path.name} — 차단"
        )
    found = CLASSIFICATION_RE.findall(yaml_text)
    if not found:
        return None  # schema default (internal) — not confidential
    if len(found) > 1:
        raise BlockedError(f"classification 이 여러 번 있습니다 (판단 불가) → {path.name} — 차단")
    value = found[0].split(" #", 1)[0].strip()
    if value.startswith("#"):
        value = ""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    value = unicodedata.normalize("NFC", value).lower()
    if value not in KNOWN_CLASSIFICATIONS:
        raise BlockedError(
            f"classification 값 {value!r} 을 판단할 수 없습니다 → {path.name} — 차단 (fail-closed)"
        )
    return value


def check_allowed(rel: str, level: int, raw: str) -> None:
    allowed = LEVEL_ALLOW.get(level, ())
    require_local_for_ip(rel, raw)  # ADR-0011: regardless of Level
    if level == 0:
        raise BlockedError(f"Level 0 (read-only) — 모든 쓰기 차단 → {raw}")
    for d in allowed:
        if rel.startswith(d + "/"):  # files under the dir only, never the dir itself
            parts = Path(rel).parts
            if any(part.startswith(".") for part in parts):
                raise BlockedError(f"숨김 파일/디렉터리 쓰기 차단 → {raw}")
            if d == PATCHES_DIR:
                # only direct children `*.patch.md`; applied/ and rejected/ are Hub history
                if len(parts) != 2 or not parts[1].endswith(".patch.md"):
                    raise BlockedError(
                        f"_patches/ 에는 바로 아래 *.patch.md 만 만들 수 있습니다 → {raw}"
                    )
            elif not rel.endswith(".md"):
                raise BlockedError(f"Vault 안에서는 .md 노트만 쓸 수 있습니다 → {raw}")
            return
    raise BlockedError(
        f"{rel} 은 사람 승인 영역입니다 (Level {level} 허용: {', '.join(allowed)}). "
        "_patches/ 에 제안하세요."
    )


# ------------------------------------------------------------------ ADR-0011 read-side devices
# directories never scanned for notes (index.db holds note bodies but is binary and git-ignored)
SCAN_SKIP_DIRS = frozenset({".git", ".myelin", "node_modules"})
IGNORED_IP_FILES = frozenset({".gitkeep", ".DS_Store"})


def ip_dir_has_files(vault: Path) -> bool:
    """True when 40_IP/ holds any non-placeholder file (a symlink counts: its target may leak)."""
    ip = vault / IP_DIR
    if not ip.is_dir():
        return False
    try:
        for _dirpath, _dirnames, filenames in os.walk(ip):
            if any(f not in IGNORED_IP_FILES for f in filenames):
                return True
    except OSError as exc:
        raise BlockedError(f"40_IP/ 를 확인할 수 없습니다 ({exc}) — 차단") from None
    return False


def resolve_any(raw: str, base: Path) -> Path:
    """Resolve a user path (absolute, `~`, or relative to `base`) following symlinks."""
    if UNSAFE_CHAR_RE.search(raw):
        raise BlockedError("경로에 제어 문자/양방향 제어 문자 — 차단")
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = base / p
    try:
        return p.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise BlockedError(f"경로를 해석할 수 없습니다 ({exc}) — 차단") from None


def covers_vault(real: Path, vault: Path) -> bool:
    """True when searching `real` would traverse the whole Vault (root itself or an ancestor)."""
    return real == vault or vault.is_relative_to(real)


def check_read_target(real: Path, vault: Path, raw: str, action: str = "읽기") -> None:
    """EXTERNAL-session rule for one file path: refuse 40_IP/** and confidential notes.

    Paths outside the Vault are not governed. Missing files are allowed (the tool fails anyway).
    """
    try:
        rel = real.relative_to(vault).as_posix()
    except ValueError:
        return
    require_local_for_ip(rel, raw, action)
    try:
        is_note = real.is_file() and real.suffix.lower() == ".md"
    except OSError:
        return  # ENAMETOOLONG etc.: no program can open it either
    if is_note and classification_of(real) == CONFIDENTIAL:
        raise BlockedError(
            f"classification: confidential 노트는 외부 LLM 세션에서 {action}할 수 없습니다 → {raw} "
            f"(ADR-0011: {LLM_ENV}={LLM_LOCAL} 로컬 세션에서만)"
        )


def find_confidential_note(real: Path, vault: Path) -> str | None:
    """Vault-relative path of the first confidential note under `real` (a directory), else None.

    A symlink that resolves into 40_IP/ counts as confidential. Parse errors propagate as
    BlockedError (cannot judge = block).
    """
    try:
        for dirpath, dirnames, filenames in os.walk(real):
            dirnames[:] = sorted(d for d in dirnames if d not in SCAN_SKIP_DIRS)
            here = Path(dirpath)
            try:
                here_rel = here.resolve().relative_to(vault).as_posix()
            except ValueError:
                here_rel = ""
            if in_ip_dir(here_rel) and any(f not in IGNORED_IP_FILES for f in filenames):
                return here_rel
            for d in dirnames:  # a directory symlink into 40_IP/ is not walked but may be followed
                dp = here / d
                if dp.is_symlink():
                    try:
                        drel = dp.resolve(strict=False).relative_to(vault).as_posix()
                    except ValueError:
                        continue
                    if in_ip_dir(drel) and ip_dir_has_files(vault):
                        return (
                            (here / d).relative_to(vault).as_posix()
                            if here.is_relative_to(vault)
                            else d
                        )
            for fn in sorted(filenames):
                p = here / fn
                if p.is_symlink():
                    target = p.resolve(strict=False)
                    try:
                        trel = target.relative_to(vault).as_posix()
                    except ValueError:
                        trel = ""
                    if in_ip_dir(trel):
                        return (
                            (here / fn).relative_to(vault).as_posix()
                            if here.is_relative_to(vault)
                            else fn
                        )
                if (
                    fn.lower().endswith(".md")
                    and p.is_file()
                    and classification_of(p) == CONFIDENTIAL
                ):
                    try:
                        return p.resolve().relative_to(vault).as_posix()
                    except ValueError:
                        return fn
    except OSError as exc:
        raise BlockedError(f"디렉터리를 검사할 수 없습니다 ({exc}) — 차단") from None
    return None


def check_search_root(real: Path, vault: Path, raw: str, *, contents: bool) -> None:
    """EXTERNAL-session rule for a search/listing root.

    `contents=True` (Grep, grep -r, rg, …) also refuses roots that contain a confidential note
    anywhere beneath; `contents=False` (Glob, find, ls -R, …) only refuses roots that would list
    40_IP/** names (titles are ideas).
    """
    if covers_vault(real, vault):
        if ip_dir_has_files(vault):
            raise BlockedError(
                f"외부 LLM 세션에서는 Vault 전체({raw})를 검색/나열할 수 없습니다 — "
                "40_IP/ 에 파일이 있습니다. `path` 를 40_IP 밖의 디렉터리로 지정하세요 (ADR-0011)"
            )
        if contents:
            hit = find_confidential_note(vault, vault)
            if hit:
                raise BlockedError(
                    f"외부 LLM 세션에서는 Vault 전체({raw})를 내용 검색할 수 없습니다 — "
                    f"confidential 노트가 있습니다 ({hit}). `path` 를 좁히세요 (ADR-0011)"
                )
        return
    try:
        rel = real.relative_to(vault).as_posix()
    except ValueError:
        return  # outside the Vault and not an ancestor: not governed
    require_local_for_ip(rel, raw, "검색")
    if real.is_file():
        check_read_target(real, vault, raw, "검색")
        return
    if contents and real.is_dir():
        hit = find_confidential_note(real, vault)
        if hit:
            raise BlockedError(
                f"외부 LLM 세션에서는 {raw} 를 내용 검색할 수 없습니다 — "
                f"confidential 노트 포함 ({hit}). `path` 를 좁히세요 (ADR-0011)"
            )
