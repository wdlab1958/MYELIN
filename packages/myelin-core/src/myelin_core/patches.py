"""`_patches/` proposal format (ADR-0006, extended by the P9 port of the Desktop line) — how /link
(and later /review) propose changes to human-approval areas without writing there. Hub Review
Gate applies an approved patch through a *plan* (dry-run → diff → digest-checked apply).

File: `_patches/<YYYYMMDD-HHMM>-<slug>.patch.md`

```markdown
---
patch: 1                       # format version
target: 10_Domains/D2/_MOC.md  # Vault-relative path the change applies to
kind: append                   # append | replace | frontmatter
under: "## 최근 verified"       # append only (optional): append at the end of this heading section
origin: claude
skill: link
created: 2026-10-18
rationale: WCET 노트가 D2 MOC 에서 링크되지 않음 (근거: 3개 노트가 인용)
status: proposed               # proposed | approved | rejected | applied
---
## append
- [[WCET 예산은 측정값의 1.5배로 잡는다]]
```

- `append`: `## append` is appended at the end of the target (or at the end of the `under`
  heading section when given).
- `replace`: `## before` / `## after`; before must occur exactly once.
- `frontmatter`: `## set` with `key: value` lines — only SETTABLE_KEYS; status·origin·id·
  reviewed·classification·share belong to the Review Gate and cannot be patched.

Fail-closed plan rules: target must be a note inside the Vault, not under 40_IP/, not
confidential, and a patch may not add a link from a verified note to an unverified AI note
(doctor's fail-closed rule). Applied/rejected patches are moved to `_patches/applied/` and
`_patches/rejected/` so the proposal history stays in the Vault.
"""

from __future__ import annotations

import difflib
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq
from ruamel.yaml.error import YAMLError

from myelin_core.note import (
    NoteParseError,
    dump_note,
    extract_wikilinks,
    parse_note,
    split_frontmatter,
)
from myelin_core.schema.frontmatter import Classification, Origin, Status
from myelin_core.vault import IP, PATCHES

SECTION_RE = re.compile(r"^## (append|before|after|set)\s*$", re.M)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.M)
SETTABLE_KEYS: frozenset[str] = frozenset({"tags", "source", "projects", "aliases", "confidence"})
APPLIED_DIR = f"{PATCHES}/applied"
REJECTED_DIR = f"{PATCHES}/rejected"


class PatchError(ValueError):
    pass


class Patch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    patch: Literal[1] = 1
    target: str = Field(min_length=1)
    kind: Literal["append", "replace", "frontmatter"]
    under: str | None = None  # append only: heading text (with or without leading #s)
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
        if p.is_absolute() or ".." in p.parts or v.startswith("_patches/") or not v.endswith(".md"):
            raise ValueError(f"target {v!r} must be a Vault-relative .md path outside _patches/")
        return p.as_posix()

    @field_validator("under")
    @classmethod
    def _under_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lstrip("#").strip()
        if not v:
            raise ValueError("under must name a heading")
        return v

    def required_sections(self) -> set[str]:
        return {"append": {"append"}, "replace": {"before", "after"}, "frontmatter": {"set"}}[
            self.kind
        ]


def parse_patch(text: str, path: Path | None = None) -> Patch:
    try:
        yaml_text, body = split_frontmatter(text)
    except NoteParseError as exc:
        raise PatchError(f"{path}: {exc}") from None
    try:
        data = YAML(typ="safe").load(io.StringIO(yaml_text))
    except YAMLError as exc:
        raise PatchError(f"{path}: patch frontmatter is not valid YAML: {exc}") from None
    except RecursionError:
        raise PatchError(f"{path}: patch frontmatter is nested too deeply") from None
    if not isinstance(data, dict):
        raise PatchError(f"{path}: patch frontmatter must be a mapping")
    sections: dict[str, str] = {}
    parts = SECTION_RE.split(body)
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
    if patch.under is not None and patch.kind != "append":
        raise PatchError(f"{path}: `under` is only valid for kind: append")
    return patch


def read_patch(path: Path) -> Patch:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise PatchError(f"{path}: not UTF-8: {exc}") from None
    except OSError as exc:
        raise PatchError(f"{path}: cannot read patch: {exc}") from None
    return parse_patch(text, path)


def check_patch_name(name: str) -> None:
    """`<slug>.patch.md`, one path component, fits a filename (fail-closed on anything else)."""
    if (
        not name.endswith(".patch.md")
        or "/" in name
        or "\\" in name
        or "\x00" in name
        or name.startswith(".")
        or len(name.encode("utf-8")) > 255
    ):
        raise PatchError(f"bad patch name {name!r}")


def history_dest(vault_root: Path, group_dir: str, name: str) -> Path:
    """Where a patch lands in `_patches/applied|rejected/` — never overwrites earlier history."""
    base = vault_root / group_dir
    dest = base / name
    stem = name[: -len(".patch.md")]
    n = 2
    while dest.exists():
        dest = base / f"{stem} ({n}).patch.md"
        n += 1
    return dest


def digest(text: str) -> str:
    """Short content digest used to detect a patch file changing between preview and apply."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ----------------------------------------------------------------------------- plan
@dataclass
class PatchPlan:
    name: str  # patch file name
    patch: Patch
    patch_text: str
    target: str
    original: str
    result: str
    issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def digest(self) -> str:
        return digest(self.patch_text)

    @property
    def diff(self) -> str:
        return "".join(
            difflib.unified_diff(
                self.original.splitlines(keepends=True),
                self.result.splitlines(keepends=True),
                fromfile=f"a/{self.target}",
                tofile=f"b/{self.target}",
                n=2,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target": self.target,
            "kind": self.patch.kind,
            "under": self.patch.under,
            "rationale": self.patch.rationale,
            "skill": self.patch.skill,
            "status": self.patch.status,
            "ok": self.ok,
            "issues": self.issues,
            "diff": self.diff,
            "digest": self.digest,
            "sections": self.patch.sections,
        }


def _apply_append(text: str, content: str, under: str | None) -> str:
    body = content.rstrip("\n") + "\n"
    if under is None:
        return text.rstrip("\n") + "\n" + body
    # find the heading section: from the heading line to the next heading of same/higher level
    headings = list(HEADING_RE.finditer(text))
    for i, m in enumerate(headings):
        if m.group(2).strip() == under:
            level = len(m.group(1))
            end = len(text)
            for nxt in headings[i + 1 :]:
                if len(nxt.group(1)) <= level:
                    end = nxt.start()
                    break
            head = text[:end].rstrip("\n") + "\n"
            tail = text[end:]
            return head + body + ("\n" + tail if tail and not tail.startswith("\n") else tail)
    raise PatchError(f"heading {under!r} not found in target")


def _apply_replace(text: str, before: str, after: str) -> str:
    n = text.count(before)
    if n != 1:
        raise PatchError(f"`before` must occur exactly once in the target (found {n})")
    return text.replace(before, after, 1)


def _apply_frontmatter(text: str, set_text: str, target: str) -> str:
    note = parse_note(text, Path(target))
    for line in set_text.splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise PatchError(f"bad frontmatter line in patch: {line!r}")
        key, val = line.split(":", 1)
        key = key.strip()
        if key not in SETTABLE_KEYS:
            raise PatchError(
                f"frontmatter key {key!r} cannot be patched (allowed: {sorted(SETTABLE_KEYS)}); "
                "status/origin/id/reviewed/classification/share belong to the Review Gate"
            )
        value = YAML(typ="safe").load(io.StringIO(val.strip()))
        if isinstance(value, list):
            seq = CommentedSeq(value)
            seq.fa.set_flow_style()  # keep `tags: [a, b]` on one line like the templates
            note.raw_frontmatter[key] = seq
        else:
            note.raw_frontmatter[key] = value
    return dump_note(note)


def plan_patch(vault_root: Path, name: str) -> PatchPlan:
    """Dry-run: parse the patch, check fail-closed rules, compute the resulting text + diff."""
    check_patch_name(name)
    pfile = vault_root / PATCHES / name
    if not pfile.is_file():
        raise PatchError(f"patch not found: {name}")
    patch = read_patch(pfile)
    patch_text = pfile.read_text(encoding="utf-8")
    target_path = (vault_root / patch.target).resolve(strict=False)
    try:
        target_rel = target_path.relative_to(vault_root.resolve()).as_posix()
    except ValueError:
        raise PatchError(f"target escapes the Vault: {patch.target}") from None
    plan = PatchPlan(
        name=name, patch=patch, patch_text=patch_text, target=target_rel, original="", result=""
    )
    if patch.status in ("applied", "rejected"):
        plan.issues.append(f"patch already {patch.status}")
    if target_rel.startswith(IP + "/"):
        plan.issues.append("40_IP/ 노트는 patch 로 바꿀 수 없다")
    if not target_path.is_file():
        plan.issues.append(f"target missing: {target_rel}")
        return plan
    original = target_path.read_text(encoding="utf-8")
    plan.original = original
    try:
        note = parse_note(original, target_path)
    except NoteParseError as exc:
        plan.issues.append(f"target is not a valid note: {exc}")
        return plan
    if note.frontmatter.classification is Classification.CONFIDENTIAL:
        plan.issues.append("confidential 노트는 patch 로 바꿀 수 없다")
    try:
        if patch.kind == "append":
            result = _apply_append(original, patch.sections["append"], patch.under)
        elif patch.kind == "replace":
            result = _apply_replace(original, patch.sections["before"], patch.sections["after"])
        else:
            result = _apply_frontmatter(original, patch.sections["set"], target_rel)
    except (PatchError, NoteParseError) as exc:
        plan.issues.append(str(exc))
        return plan
    try:
        new_note = parse_note(result, target_path)
    except NoteParseError as exc:
        plan.issues.append(f"result would break the target's frontmatter: {exc}")
        return plan
    plan.result = result
    # fail-closed link rule: a verified note may not gain links to unverified AI notes
    if note.frontmatter.status is Status.VERIFIED:
        before_links = {lk.target for lk in note.links}
        for lk in extract_wikilinks(new_note.body):
            if lk.target in before_links:
                continue
            for cand in vault_root.rglob(f"{lk.target}.md"):
                try:
                    fm = parse_note(cand.read_text(encoding="utf-8"), cand).frontmatter
                except NoteParseError:
                    continue
                if fm.origin is Origin.CLAUDE and fm.status is not Status.VERIFIED:
                    plan.issues.append(
                        f"verified 노트에 미검증 AI 노트 [[{lk.target}]] 링크를 추가할 수 없다"
                    )
    return plan


def _with_status(patch_text: str, status: str) -> str:
    new, n = re.subn(r"^status:\s*\w+\s*$", f"status: {status}", patch_text, count=1, flags=re.M)
    if n == 0:
        new = patch_text.replace("\n---\n", f"\nstatus: {status}\n---\n", 1)
    return new


def apply_plan(vault_root: Path, plan: PatchPlan) -> list[str]:
    """Write the planned result and move the patch to _patches/applied/. Returns touched paths."""
    if not plan.ok:
        raise PatchError("plan has issues: " + "; ".join(plan.issues))
    target = vault_root / plan.target
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(plan.result, encoding="utf-8")
    tmp.replace(target)
    src = vault_root / PATCHES / plan.name
    dest = history_dest(vault_root, APPLIED_DIR, plan.name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_with_status(plan.patch_text, "applied"), encoding="utf-8")
    src.unlink()
    return [plan.target, f"{PATCHES}/{plan.name}", dest.relative_to(vault_root).as_posix()]


def reject_patch(vault_root: Path, name: str) -> list[str]:
    """Move a proposed patch to _patches/rejected/ with status: rejected. Returns touched paths."""
    check_patch_name(name)
    src = vault_root / PATCHES / name
    if not src.is_file():
        raise PatchError(f"patch not found: {name}")
    try:
        payload = _with_status(src.read_text(encoding="utf-8"), "rejected").encode("utf-8")
    except UnicodeDecodeError:
        payload = src.read_bytes()  # junk can still be rejected: archived verbatim
    dest = history_dest(vault_root, REJECTED_DIR, name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(payload)
    src.unlink()
    return [f"{PATCHES}/{name}", dest.relative_to(vault_root).as_posix()]


def list_patches(vault_root: Path) -> list[dict[str, Any]]:
    """Proposed patches plus applied/rejected history, newest first within each group."""
    out: list[dict[str, Any]] = []
    for group, rel in (("proposed", PATCHES), ("applied", APPLIED_DIR), ("rejected", REJECTED_DIR)):
        d = vault_root / rel
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.patch.md"), reverse=True):
            try:
                patch = read_patch(p)
                out.append(
                    patch.model_dump(mode="json")
                    | {"file": p.name, "group": group, "sections": patch.sections}
                )
            except PatchError as exc:
                out.append({"file": p.name, "group": group, "error": str(exc), "status": "invalid"})
    return out
