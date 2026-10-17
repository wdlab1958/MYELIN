"""Pack schema — 정본 §5.2 (`packs/<name>/pack.yaml`), plus the two side files a Domain may
reference: `taxonomy.yaml` (용어 사전) and `interviews.yaml` (/interview 질문 은행).

```yaml
pack: a3.security-consulting
version: 1.0.0
kind: org                 # core | reference | org | personal
maintainer: A3-AI WG
requires: [myelin.core>=1.0]
domains:
  - id: SEC-CONSULT
    name: 보안 컨설팅
    accent: violet         # Emboss accent token
    description: ...
    sub_mocs: [...]
    note_types: [evergreen, lesson, checklist, adr]
    taxonomy_seed: taxonomy.yaml
    templates: templates/
    interview_bank: interviews.yaml
    classification_default: internal
    compose_targets: [...]
```
Unknown keys are rejected (ADR-0003 §3).
"""

from __future__ import annotations

import re
from enum import StrEnum
from functools import total_ordering
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from myelin_core.schema.frontmatter import DOMAIN_ID_RE, Classification, NoteType

PACK_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(\.[a-z][a-z0-9-]*)+$")
VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<patch>\d+))?$")
REQ_RE = re.compile(
    r"^\s*(?P<name>[a-z][a-z0-9.-]*)\s*(?:(?P<op>>=|<=|==|~=|>|<)\s*(?P<ver>\d+\.\d+(?:\.\d+)?))?\s*$"
)

# Emboss accent tokens a Domain may use (ADR-0003 §6; synced with design/tokens.json by test)
ACCENTS: frozenset[str] = frozenset({"violet", "lime", "cyan", "magenta"})

PackName = Annotated[
    str, Field(pattern=PACK_NAME_RE.pattern, description="owner.name, e.g. a3.security-consulting")
]
DomainIdField = Annotated[str, Field(pattern=DOMAIN_ID_RE.pattern)]


class PackKind(StrEnum):
    CORE = "core"
    REFERENCE = "reference"
    ORG = "org"
    PERSONAL = "personal"


@total_ordering
class Version:
    """Minimal semver (major.minor[.patch]); `1.0` == `1.0.0`."""

    __slots__ = ("major", "minor", "patch")

    def __init__(self, text: str) -> None:
        m = VERSION_RE.match(text.strip())
        if not m:
            raise ValueError(f"invalid version {text!r} (expected major.minor[.patch])")
        self.major = int(m.group("major"))
        self.minor = int(m.group("minor"))
        self.patch = int(m.group("patch") or 0)

    @property
    def tuple(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Version) and self.tuple == other.tuple

    def __lt__(self, other: Version) -> bool:
        return self.tuple < other.tuple

    def __hash__(self) -> int:
        return hash(self.tuple)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __repr__(self) -> str:
        return f"Version({str(self)!r})"


class Requirement:
    """`name`, `name>=1.0`, `name==1.2.3`, `name~=1.0` (compatible: same major, >= given)."""

    __slots__ = ("name", "op", "version")

    def __init__(self, text: str) -> None:
        m = REQ_RE.match(text)
        if not m:
            raise ValueError(f"invalid requirement {text!r} (expected e.g. 'myelin.core>=1.0')")
        self.name: str = m.group("name")
        self.op: str | None = m.group("op")
        self.version: Version | None = Version(m.group("ver")) if m.group("ver") else None
        if not PACK_NAME_RE.match(self.name):
            raise ValueError(f"invalid pack name in requirement {text!r}")

    def satisfied_by(self, v: Version) -> bool:
        if self.op is None or self.version is None:
            return True
        r = self.version
        return {
            ">=": v >= r,
            "<=": v <= r,
            "==": v == r,
            ">": v > r,
            "<": v < r,
            "~=": v.major == r.major and v >= r,
        }[self.op]

    def __str__(self) -> str:
        return self.name if self.op is None else f"{self.name}{self.op}{self.version}"

    def __repr__(self) -> str:
        return f"Requirement({str(self)!r})"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Domain(_Strict):
    id: DomainIdField
    name: str = Field(min_length=1, max_length=80)
    accent: str = "violet"
    description: str = ""
    sub_mocs: list[str] = Field(default_factory=list, max_length=12)
    note_types: list[NoteType] = Field(
        default_factory=lambda: [NoteType.EVERGREEN, NoteType.LESSON]
    )
    taxonomy_seed: str | None = None
    templates: str | None = None
    interview_bank: str | None = None
    classification_default: Classification = Classification.INTERNAL
    compose_targets: list[str] = Field(default_factory=list)

    @field_validator("accent")
    @classmethod
    def _accent_is_token(cls, v: str) -> str:
        if v not in ACCENTS:
            raise ValueError(f"accent {v!r} is not an Emboss accent token {sorted(ACCENTS)}")
        return v

    @field_validator("sub_mocs", "compose_targets")
    @classmethod
    def _non_empty_unique(cls, v: list[str]) -> list[str]:
        cleaned = [s.strip() for s in v]
        if any(not s for s in cleaned):
            raise ValueError("entries must be non-empty strings")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("entries must be unique")
        return cleaned

    @field_validator("note_types")
    @classmethod
    def _note_types_non_empty(cls, v: list[NoteType]) -> list[NoteType]:
        if not v:
            raise ValueError("note_types must list at least one note type")
        if len(set(v)) != len(v):
            raise ValueError("note_types must be unique")
        return v

    @field_validator("taxonomy_seed", "templates", "interview_bank")
    @classmethod
    def _relative_inside_pack(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if v.startswith(("/", "~")) or ".." in v.split("/"):
            raise ValueError(f"path {v!r} must be relative and inside the pack directory")
        return v.rstrip("/") or v


class Pack(_Strict):
    pack: PackName
    version: str = "1.0.0"
    kind: PackKind
    maintainer: str = Field(min_length=1)
    requires: list[str] = Field(default_factory=list)
    description: str = ""
    domains: list[Domain] = Field(default_factory=list)
    # Core pack provisions (note type templates shared by every vault)
    templates: str | None = None
    taxonomy_seed: str | None = None

    @field_validator("version")
    @classmethod
    def _semver(cls, v: str) -> str:
        return str(Version(v))

    @field_validator("requires")
    @classmethod
    def _requirements_parse(cls, v: list[str]) -> list[str]:
        names = [Requirement(r).name for r in v]
        if len(set(names)) != len(names):
            raise ValueError("requires lists the same pack more than once")
        return v

    @model_validator(mode="after")
    def _domains_consistent(self) -> Pack:
        ids = [d.id for d in self.domains]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate domain id(s) in pack: {dupes}")
        if self.kind is PackKind.CORE:
            if self.domains:
                raise ValueError(
                    "core pack must not declare domains (it provides note types/templates only)"
                )
        elif not self.domains:
            raise ValueError(f"{self.kind.value} pack must declare at least one domain")
        if self.kind is not PackKind.CORE and not any(
            Requirement(r).name == "myelin.core" for r in self.requires
        ):
            raise ValueError(
                "non-core pack must require myelin.core (e.g. requires: [myelin.core>=1.0])"
            )
        if self.pack == "myelin.core" and self.kind is not PackKind.CORE:
            raise ValueError("pack 'myelin.core' must have kind: core")
        return self

    @property
    def semver(self) -> Version:
        return Version(self.version)

    @property
    def requirements(self) -> list[Requirement]:
        return [Requirement(r) for r in self.requires]

    @property
    def domain_ids(self) -> list[str]:
        return [d.id for d in self.domains]

    def referenced_paths(self) -> dict[str, str]:
        """Relative paths this pack references → label (for existence checks by the loader)."""
        refs: dict[str, str] = {}
        if self.templates:
            refs[self.templates] = "templates"
        if self.taxonomy_seed:
            refs[self.taxonomy_seed] = "taxonomy_seed"
        for d in self.domains:
            if d.taxonomy_seed:
                refs[d.taxonomy_seed] = f"domains[{d.id}].taxonomy_seed"
            if d.templates:
                refs[d.templates] = f"domains[{d.id}].templates"
            if d.interview_bank:
                refs[d.interview_bank] = f"domains[{d.id}].interview_bank"
        return refs


# ------------------------------------------------------------------ side files


class TaxonomyTerm(_Strict):
    term: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    definition: str = ""
    domain: list[DomainIdField] = Field(default_factory=list)

    @field_validator("domain", "aliases", mode="before")
    @classmethod
    def _scalar_to_list(cls, v: object) -> object:
        return [v] if isinstance(v, str) else v


class Taxonomy(_Strict):
    """`taxonomy.yaml` — 용어 정규화 사전.

    /distill 용어 정규화와 90_System/taxonomy.md 렌더링의 원천.
    """

    terms: list[TaxonomyTerm] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_terms(self) -> Taxonomy:
        seen: dict[str, str] = {}
        for t in self.terms:
            for key in [t.term, *t.aliases]:
                k = key.casefold()
                if k in seen and seen[k] != t.term:
                    raise ValueError(
                        f"term/alias {key!r} is claimed by both {seen[k]!r} and {t.term!r}"
                    )
                seen[k] = t.term
        return self


class InterviewQuestion(_Strict):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    prompt: str = Field(min_length=1)
    domain: DomainIdField | None = None
    sub_moc: str | None = None
    follow_ups: list[str] = Field(default_factory=list)
    yields: NoteType = NoteType.LESSON


class InterviewBank(_Strict):
    """`interviews.yaml` — /interview 암묵지 추출 질문 은행."""

    questions: list[InterviewQuestion] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> InterviewBank:
        ids = [q.id for q in self.questions]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate question id(s): {dupes}")
        return self
