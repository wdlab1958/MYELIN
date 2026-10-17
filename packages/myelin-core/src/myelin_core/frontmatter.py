"""Frontmatter 스키마 v2 (명세 §6.2)."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from myelin_core.errors import Issue

NOTE_ID_PATTERN = r"^\d{8}-\d{4}-[a-z0-9]+(?:-[a-z0-9]+)*$"
DOMAIN_ID_PATTERN = r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*$"

NoteId = Annotated[str, StringConstraints(pattern=NOTE_ID_PATTERN)]
DomainId = Annotated[str, StringConstraints(pattern=DOMAIN_ID_PATTERN, max_length=32)]


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


class Frontmatter(BaseModel):
    """노트 frontmatter. 알 수 없는 추가 필드(예: lesson의 `era`)는 보존한다."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    id: NoteId
    type: NoteType
    domain: list[DomainId] = Field(default_factory=list)
    status: Status
    origin: Origin
    confidence: Confidence = Confidence.MEDIUM
    classification: Classification = Classification.INTERNAL
    share: bool = False
    source: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    created: date
    reviewed: date | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("domain", "source", "projects", "tags", mode="before")
    @classmethod
    def _scalar_to_list(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, value: list[str]) -> list[str]:
        return [tag.lstrip("#") for tag in value if tag.strip("# ")]

    @field_validator("domain")
    @classmethod
    def _unique_domains(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("domain contains duplicates")
        return value

    @model_validator(mode="after")
    def _reviewed_not_before_created(self) -> Frontmatter:
        if self.reviewed is not None and self.reviewed < self.created:
            raise ValueError("reviewed must not be earlier than created")
        return self

    def policy_issues(self) -> list[Issue]:
        """스키마는 통과하지만 정책상 모순인 조합을 보고한다."""
        issues: list[Issue] = []
        if self.share and self.classification is Classification.CONFIDENTIAL:
            issues.append(
                Issue(
                    "share", "confidential 노트는 share: true 일 수 없습니다", "share_confidential"
                )
            )
        return issues


def id_change_issue(before: Frontmatter, after: Frontmatter) -> Issue | None:
    """노트 id는 불변이다. 바뀌었으면 Issue를 돌려준다."""
    if before.id != after.id:
        return Issue("id", f"id는 변경할 수 없습니다 ({before.id} -> {after.id})", "id_changed")
    return None
