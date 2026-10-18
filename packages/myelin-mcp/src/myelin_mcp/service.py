"""MCP 도구의 실제 로직 — 서버 프레임워크와 분리해 직접 테스트한다 (ADR-0006)."""

from __future__ import annotations

import os
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

from myelin_core.config import load_config
from myelin_core.doctor import run_doctor
from myelin_core.errors import Issue, MyelinError, NoteParseError
from myelin_core.frontmatter import NoteType
from myelin_core.index import VaultIndex
from myelin_core.lock import load_lock
from myelin_core.note import parse_note
from myelin_core.policy import ReadPolicy
from myelin_core.resources import myelin_guard
from myelin_core.stats import compute_stats
from myelin_core.vault import AI_DRAFTS, is_note_path

DRAFT_TYPES = (NoteType.FLEETING, NoteType.LITERATURE, NoteType.EVERGREEN, NoteType.LESSON)
_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
NOT_AVAILABLE = "찾을 수 없거나 Claude로 보낼 수 없는 노트입니다 (보호 노트는 로컬 LLM 전용)"


class ServiceError(MyelinError):
    """도구 호출 오류 — 메시지는 그대로 Claude에게 전달된다."""


def _fail(msg: str, loc: str = "arguments") -> ServiceError:
    return ServiceError(msg, [Issue(loc, msg)])


class VaultService:
    def __init__(self, vault: Path) -> None:
        if not myelin_guard.is_vault(vault):
            raise _fail(
                f"MYELIN Vault가 아닙니다 (myelin.yaml + 90_System/myelin.lock.yaml 필요): {vault}"
            )
        self.vault = vault.resolve()
        self.config = load_config(self.vault)
        self.lock = load_lock(self.vault)
        self.policy = ReadPolicy.from_config(self.config)
        self.index = VaultIndex(self.vault, self.policy)
        self.index.refresh(force=True)

    @property
    def write_enabled(self) -> bool:
        return self.config.mcp.write_drafts

    # ── 읽기 ───────────────────────────────────────────────────────────
    def search_notes(
        self,
        query: str,
        domain: str | None = None,
        note_type: str | None = None,
        status: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        self.index.refresh()
        try:
            return self.index.search(query, domain, note_type, status, limit)
        except ValueError as exc:
            raise _fail(str(exc), "query") from exc

    def query_frontmatter(self, **filters: Any) -> list[dict[str, Any]]:
        self.index.refresh()
        return self.index.query(**filters)

    def _rel_note_path(self, path: str) -> str:
        """Vault 안의 지식 노트 경로만 허용 (정규화·realpath·심볼릭 링크 탈출 차단)."""
        raw = Path(path)
        lexical = Path(os.path.abspath(raw if raw.is_absolute() else self.vault / raw))
        real = Path(os.path.realpath(lexical))
        for candidate in (lexical, real):
            try:
                rel = candidate.relative_to(self.vault)
            except ValueError:
                raise _fail(NOT_AVAILABLE, "path") from None
            if not is_note_path(rel):
                raise _fail(NOT_AVAILABLE, "path")
        return real.relative_to(self.vault).as_posix()

    def get_note(self, path: str | None = None, note_id: str | None = None) -> dict[str, Any]:
        if (path is None) == (note_id is None):
            raise _fail("path 와 id 중 하나만 지정하세요")
        self.index.refresh()
        found = (
            self.index.get(path=self._rel_note_path(path))
            if path is not None
            else self.index.get(note_id=note_id)
        )
        if found is None:
            raise _fail(NOT_AVAILABLE, "path" if path is not None else "id")
        return found

    def list_domains(self) -> list[dict[str, Any]]:
        self.index.refresh()
        counts = self.index.domain_counts()
        roles = {d: self.config.domains.role_of(d) for d in self.config.domains.all()}
        out = []
        for pack in self.lock.packs:
            for d in pack.domains:
                if d.id in roles:
                    out.append(
                        {
                            "id": d.id,
                            "label": d.label,
                            "name": d.name,
                            "role": roles[d.id],
                            "pack": pack.name,
                            "notes": counts.get(d.id, 0),
                        }
                    )
        return out

    def vault_stats(self) -> dict[str, Any]:
        # 경로·내용 없이 숫자만 돌려준다 (보호 노트의 존재 정보도 집계로만)
        stats = compute_stats(self.vault).as_dict()
        findings = run_doctor(self.vault)
        stats["doctor"] = {
            "errors": sum(1 for f in findings if f.severity == "error"),
            "warnings": sum(1 for f in findings if f.severity == "warning"),
            "by_rule": dict(Counter(f.rule for f in findings)),
        }
        stats["index"] = self.index.counts()
        stats["level"] = self.config.level
        return stats

    # ── 쓰기 (opt-in) ─────────────────────────────────────────────────
    def write_draft(
        self,
        title: str,
        body: str,
        note_type: str = "literature",
        domain: list[str] | None = None,
        source: list[str] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if not self.write_enabled:
            raise _fail("myelin.yaml 의 mcp.write_drafts 가 false 입니다", "mcp.write_drafts")
        if note_type not in {t.value for t in DRAFT_TYPES}:
            allowed = ", ".join(t.value for t in DRAFT_TYPES)
            raise _fail(f"note_type 은 {allowed} 중 하나", "note_type")
        domains = domain or []
        unknown = [d for d in domains if d not in self.lock.domain_ids()]
        if unknown:
            raise _fail(f"설치되지 않은 Domain: {', '.join(unknown)}", "domain")
        safe_title = _UNSAFE.sub(" ", title).strip().lstrip(".")[:100].strip()
        if not safe_title:
            raise _fail("title 이 비어 있습니다", "title")
        rel = f"{AI_DRAFTS}{safe_title}.md"

        # Level·경로 판정은 Guard와 같은 코드로 (규칙을 두 곳에 두지 않는다)
        event = {"tool_name": "Write", "tool_input": {"file_path": rel}, "cwd": str(self.vault)}
        reason = myelin_guard.check(event, self.vault)
        if reason:
            raise _fail(reason, "path")
        target = self.vault / rel
        if target.exists():
            raise _fail(f"이미 있습니다 — 덮어쓰지 않습니다: {rel}", "title")

        now = now or datetime.now()
        slug = re.sub(r"[^a-z0-9]+", "-", safe_title.lower()).strip("-")[:40] or f"mcp{now:%S}"
        text = (
            "---\n"
            f"id: {now:%Y%m%d-%H%M}-{slug}\n"
            f"type: {note_type}\n"
            f"domain: [{', '.join(domains)}]\n"
            "status: draft\n"
            "origin: claude\n"
            "confidence: low\n"
            "classification: internal\n"
            f"source: [{', '.join(_yaml_str(s) for s in source or [])}]\n"
            f"created: {date(now.year, now.month, now.day).isoformat()}\n"
            "tags: []\n"
            "---\n"
            f"# {safe_title}\n\n{body.strip()}\n"
        )
        try:
            parse_note(text, source=rel)
        except NoteParseError as exc:
            raise ServiceError("초안이 노트 스키마를 통과하지 못했습니다", exc.issues) from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8") as fh:  # 'x' — 경쟁 상황에서도 덮어쓰지 않는다
            fh.write(text)
        self.index.refresh(force=True)
        return {"path": rel, "status": "draft", "origin": "claude"}


def _yaml_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
