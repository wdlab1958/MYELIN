"""Frontmatter schema v2 — 정본 §6.2 (정본이 유일한 필드 출처; 필드 추가는 ADR 선행).

```yaml
id: 20261018-0712-wcet-budget     # 자동 생성, 불변
type: evergreen                    # fleeting|literature|evergreen|moc|adr|experiment|lesson|
                                   #   checklist|idea-ip
domain: [D2, D3]                   # Pack에 선언된 Domain ID
status: verified                   # draft|unverified|verified|deprecated
origin: mixed                      # human|claude|mixed
confidence: high
classification: internal           # public|internal|confidential
share: false                       # true일 때만 Commons publish 후보
source: ["[[Lit - ROS2 Executor]]"]
created: 2026-10-18
reviewed: 2026-10-18
tags: [rtos, control-loop]
```

Validation policy (ADR-0003): the 12 spec fields are validated strictly; unknown extra
keys (Obsidian `aliases`, `cssclasses`, …) are *allowed and preserved* so user vaults keep
working. Cross-field rules that the spec assigns to `myelin doctor` (confidential+share,
date inversion) are exposed as `consistency_issues()` rather than hard validation errors,
so doctor can report them per note instead of failing the parse.
"""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NoteType(StrEnum):
    FLEETING = "fleeting"
    LITERATURE = "literature"
    EVERGREEN = "evergreen"
    MOC = "moc"
    ADR = "adr"
    EXPERIMENT = "experiment"
    LESSON = "lesson"
    CHECKLIST = "checklist"
    IDEA_IP = "idea-ip"


class Status(StrEnum):
    DRAFT = "draft"
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    DEPRECATED = "deprecated"


class Origin(StrEnum):
    HUMAN = "human"
    CLAUDE = "claude"
    MIXED = "mixed"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Classification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"

    @property
    def rank(self) -> int:
        return {"public": 0, "internal": 1, "confidential": 2}[self.value]


# id: <YYYYMMDD>-<HHMM>-<slug>  — 자동 생성, 불변
NOTE_ID_RE = re.compile(r"^(?P<date>\d{8})-(?P<time>\d{4})-(?P<slug>[a-z0-9][a-z0-9-]{0,63})$")
# Domain ID as declared in a Pack: uppercase, digits, hyphen (e.g. D1, SEC-CONSULT, LLM-SEC)
DOMAIN_ID_RE = re.compile(r"^[A-Z][A-Z0-9-]{0,31}$")
TAG_RE = re.compile(r"^[a-z0-9][a-z0-9/_-]{0,63}$")

NoteId = Annotated[str, Field(pattern=NOTE_ID_RE.pattern, description="자동 생성, 불변")]
DomainId = Annotated[str, Field(pattern=DOMAIN_ID_RE.pattern)]
Tag = Annotated[str, Field(pattern=TAG_RE.pattern)]


class Frontmatter(BaseModel):
    """Frontmatter v2 (정본 §6.2)."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True, populate_by_name=True)

    id: NoteId
    type: NoteType
    domain: list[DomainId] = Field(default_factory=list)
    status: Status = Status.DRAFT
    origin: Origin = Origin.HUMAN
    confidence: Confidence = Confidence.MEDIUM
    classification: Classification = Classification.INTERNAL
    share: bool = False
    source: list[str] = Field(default_factory=list)
    created: date
    reviewed: date | None = None
    tags: list[Tag] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id_date_is_real(cls, v: str) -> str:
        m = NOTE_ID_RE.match(v)
        assert m is not None  # pattern already enforced
        d, t = m.group("date"), m.group("time")
        try:
            date(int(d[:4]), int(d[4:6]), int(d[6:]))
        except ValueError as exc:
            raise ValueError(f"id date part {d!r} is not a calendar date") from exc
        hh, mm = int(t[:2]), int(t[2:])
        if hh > 23 or mm > 59:
            raise ValueError(f"id time part {t!r} is not a valid HHMM")
        return v

    @field_validator("domain", "tags", "source", mode="before")
    @classmethod
    def _scalar_to_list(cls, v: Any) -> Any:
        # Obsidian users often write `domain: D1` for a single value.
        if isinstance(v, str):
            return [v]
        return v

    @field_validator("domain")
    @classmethod
    def _unique_domains(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("domain list contains duplicates")
        return v

    @property
    def extra_fields(self) -> dict[str, Any]:
        return dict(self.model_extra or {})

    @property
    def is_ai_origin(self) -> bool:
        return self.origin is Origin.CLAUDE

    @property
    def is_publishable(self) -> bool:
        """Commons publish 후보 조건 (정본 §9.1): share + verified + classification ≤ internal."""
        return (
            self.share
            and self.status is Status.VERIFIED
            and self.classification.rank <= Classification.INTERNAL.rank
        )

    def consistency_issues(self) -> list[str]:
        """Cross-field contradictions the spec assigns to `myelin doctor` (§6.2)."""
        issues: list[str] = []
        if self.classification is Classification.CONFIDENTIAL and self.share:
            issues.append("classification: confidential 노트는 share: true 일 수 없다")
        if self.reviewed is not None and self.reviewed < self.created:
            issues.append(f"reviewed({self.reviewed}) 가 created({self.created}) 보다 앞선다")
        if self.status is Status.VERIFIED and self.reviewed is None:
            issues.append("status: verified 노트는 reviewed 날짜가 필요하다")
        if self.type is NoteType.MOC and not self.domain:
            issues.append("type: moc 노트는 domain 이 최소 1개 필요하다")
        return issues
