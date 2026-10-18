"""`_patches/` proposal format (ADR-0006) — how /link (and later /review) propose changes to
human-approval areas without writing there. Hub Review Gate (P6) applies an approved patch.

File: `_patches/<YYYYMMDD-HHMM>-<slug>.patch.md`

```markdown
---
patch: 1                       # format version
target: 10_Domains/D2/_MOC.md  # Vault-relative path the change applies to
kind: append                   # append | replace | frontmatter
origin: claude
skill: link
created: 2026-10-18
rationale: WCET 노트가 D2 MOC 에서 링크되지 않음 (근거: 3개 노트가 인용)
status: proposed               # proposed | approved | rejected | applied
---
## append
- [[WCET 예산은 측정값의 1.5배로 잡는다]]
```

- `append`: the body section `## append` is appended to the end of the target (or under
  `## 최근 verified` for MOCs — Hub decides).
- `replace`: `## before` / `## after` sections; before must match exactly once.
- `frontmatter`: `## set` section with `key: value` lines merged into target frontmatter.
"""

from __future__ import annotations

import io
import re
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from ruamel.yaml import YAML

from myelin_core.note import NoteParseError, split_frontmatter

SECTION_RE = re.compile(r"^## (append|before|after|set)\s*$", re.M)


class PatchError(ValueError):
    pass


class Patch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    patch: Literal[1] = 1
    target: str = Field(min_length=1)
    kind: Literal["append", "replace", "frontmatter"]
    origin: Literal["claude", "human", "mixed"] = "claude"
    skill: str = Field(pattern=r"^[a-z][a-z-]*$")
    created: date
    rationale: str = Field(min_length=1)
    status: Literal["proposed", "approved", "rejected", "applied"] = "proposed"
    sections: dict[str, str] = Field(default_factory=dict, exclude=True)

    @field_validator("target")
    @classmethod
    def _target_inside_vault(cls, v: str) -> str:
        p = Path(v)
        if p.is_absolute() or ".." in p.parts or v.startswith("_patches/"):
            raise ValueError(f"target {v!r} must be a Vault-relative path outside _patches/")
        return p.as_posix()

    def required_sections(self) -> set[str]:
        return {"append": {"append"}, "replace": {"before", "after"}, "frontmatter": {"set"}}[
            self.kind
        ]


def parse_patch(text: str, path: Path | None = None) -> Patch:
    try:
        yaml_text, body = split_frontmatter(text)
    except NoteParseError as exc:
        raise PatchError(f"{path}: {exc}") from None
    data = YAML(typ="safe").load(io.StringIO(yaml_text))
    if not isinstance(data, dict):
        raise PatchError(f"{path}: patch frontmatter must be a mapping")
    sections: dict[str, str] = {}
    parts = SECTION_RE.split(body)
    # parts = [preamble, name1, content1, name2, content2, ...]
    for i in range(1, len(parts) - 1, 2):
        sections[parts[i]] = parts[i + 1].strip("\n")
    try:
        patch = Patch.model_validate({**data, "sections": sections})
    except ValidationError as exc:
        lines = [f"  - {'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        raise PatchError(f"{path}: patch schema violation:\n" + "\n".join(lines)) from None
    missing = patch.required_sections() - set(sections)
    if missing:
        raise PatchError(f"{path}: kind {patch.kind!r} requires sections {sorted(missing)}")
    if any(not sections[s].strip() for s in patch.required_sections()):
        raise PatchError(f"{path}: required sections must not be empty")
    return patch


def read_patch(path: Path) -> Patch:
    return parse_patch(path.read_text(encoding="utf-8"), path)
