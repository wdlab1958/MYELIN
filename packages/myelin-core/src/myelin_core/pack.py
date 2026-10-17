"""Domain Pack 스키마 (명세 §5.2).

Pack 매니페스트는 fail-closed: 알 수 없는 필드는 오류다 (frontmatter와 다름).
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
)

from myelin_core.frontmatter import Classification, DomainId, NoteType
from myelin_core.versioning import parse_requirement, parse_version

PACK_NAME_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)+$"

PackName = Annotated[str, StringConstraints(pattern=PACK_NAME_PATTERN, max_length=64)]
NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PackKind(StrEnum):
    CORE = "core"
    REFERENCE = "reference"
    ORG = "org"
    PERSONAL = "personal"


class Accent(StrEnum):
    """Emboss accent 토큰 (명세 §8)."""

    VIOLET = "violet"
    CYAN = "cyan"
    LIME = "lime"
    MAGENTA = "magenta"
    AMBER = "amber"
    SLATE = "slate"


def _check_rel_path(value: str | None) -> str | None:
    """Pack 내부 상대경로만 허용한다 (절대경로·상위 이동 금지)."""
    if value is None:
        return None
    p = PurePosixPath(value)
    if not value.strip() or p.is_absolute() or ".." in p.parts or "\\" in value:
        raise ValueError("must be a relative path inside the pack (no '..', no absolute path)")
    return value


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Domain(_Strict):
    id: DomainId
    label: Annotated[str, StringConstraints(min_length=1, max_length=6)] | None = None
    name: NonEmpty
    accent: Accent = Accent.VIOLET
    description: str = ""
    sub_mocs: list[NonEmpty] = Field(min_length=1)
    note_types: list[NoteType] = Field(
        default_factory=lambda: [NoteType.EVERGREEN, NoteType.LESSON], min_length=1
    )
    taxonomy_seed: str | None = None
    templates: str | None = None
    interview_bank: str | None = None
    classification_default: Classification = Classification.INTERNAL
    compose_targets: list[NonEmpty] = Field(default_factory=list)

    @field_validator("taxonomy_seed", "templates", "interview_bank")
    @classmethod
    def _paths(cls, value: str | None) -> str | None:
        return _check_rel_path(value)

    @field_validator("sub_mocs", "note_types")
    @classmethod
    def _unique(cls, value: list[Any]) -> list[Any]:
        if len(set(value)) != len(value):
            raise ValueError("contains duplicates")
        return value


class PackManifest(_Strict):
    pack: PackName
    version: str
    kind: PackKind
    maintainer: NonEmpty
    description: str = ""
    requires: list[str] = Field(default_factory=list)
    templates: str | None = None
    # validate_default: `domains` 를 생략해도 아래 규칙(비-core는 1개 이상)이 실행되게 한다.
    domains: list[Domain] = Field(default_factory=list, validate_default=True)

    @field_validator("version")
    @classmethod
    def _semver(cls, value: str) -> str:
        parse_version(value)
        return value

    @field_validator("requires")
    @classmethod
    def _requires(cls, value: list[str], info: ValidationInfo) -> list[str]:
        names = [parse_requirement(item).name for item in value]
        if len(set(names)) != len(names):
            raise ValueError("a pack may be required only once")
        if info.data.get("pack") in names:
            raise ValueError("a pack cannot require itself")
        return value

    @field_validator("templates")
    @classmethod
    def _tpl(cls, value: str | None) -> str | None:
        return _check_rel_path(value)

    @field_validator("domains")
    @classmethod
    def _domains_rules(cls, value: list[Domain], info: ValidationInfo) -> list[Domain]:
        kind = info.data.get("kind")
        if kind is not None and kind is not PackKind.CORE and not value:
            raise ValueError(f"a {kind.value} pack must declare at least one domain")
        seen: dict[str, int] = {}
        for idx, domain in enumerate(value):
            if domain.id in seen:
                raise ValueError(
                    f"domains[{idx}].id {domain.id!r} duplicates domains[{seen[domain.id]}].id"
                )
            seen[domain.id] = idx
        return value

    @property
    def version_tuple(self) -> tuple[int, int, int]:
        return parse_version(self.version)


class Term(_Strict):
    term: NonEmpty
    aliases: list[NonEmpty] = Field(default_factory=list)
    domain: DomainId | None = None
    definition: str = ""


class TaxonomyFile(_Strict):
    terms: list[Term] = Field(min_length=1)


class Question(_Strict):
    id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
    q: NonEmpty
    follow_ups: list[NonEmpty] = Field(default_factory=list)


class InterviewBank(_Strict):
    domains: dict[DomainId, Annotated[list[Question], Field(min_length=1)]] = Field(min_length=1)
