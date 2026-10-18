"""구조화 patch — Claude(/link 등)가 사람 영역 노트의 변경을 **제안**하고,
사람이 Hub에서 적용한다 (ADR-0010).

파일: `_patches/<YYYYMMDD-HHMM>-<slug>.patch.md` — 대상 노트 하나에 변경 하나.

```markdown
---
patch: 1
target: 10_Domains/AI-ML-AX/_MOC.md
kind: append                 # append | replace | frontmatter
under: "## 핵심 Evergreen"   # append 전용(선택): 이 제목 구획의 끝에 붙인다
origin: claude
skill: link
created: 2026-10-18
rationale: 세 노트가 같은 개념을 인용 — MOC에서 빠져 있음
status: proposed
---
## append
- [[WCET 예산은 추론 지연을 포함]]
```
- `replace`: `## before` 가 본문에 **정확히 한 번** 있어야 하고 `## after` 로 바꾼다.
- `frontmatter`: `## set` 의 `key: value` — 허용 키만(tags·source·projects·aliases·confidence).
  status·origin·id·reviewed·classification·share 는 Review Gate의 몫이라 patch로 못 바꾼다.

fail-closed: 대상이 Vault 밖·링크·지식 노트 아님·40_IP·confidential 이면 거부. verified 노트에
미검증 AI 노트로 가는 링크를 새로 만들면 거부 (doctor 규칙). 적용·반려한 patch는 지우지 않고
`_patches/applied/`·`_patches/rejected/` 로 옮겨 상태를 남긴다.
"""

from __future__ import annotations

import difflib
import io
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from ruamel.yaml import YAML

from myelin_core.errors import Issue, MyelinError, NoteParseError, issues_from_validation
from myelin_core.frontmatter import Classification, Origin, Status
from myelin_core.note import extract_links, parse_note, split_frontmatter
from myelin_core.review import ReviewError, read_note, set_fields
from myelin_core.vault import scan_vault
from myelin_core.yamlio import load_yaml

PATCH_DIR = "_patches"
APPLIED_DIR = "_patches/applied"
REJECTED_DIR = "_patches/rejected"
SETTABLE_KEYS = frozenset({"tags", "source", "projects", "aliases", "confidence"})
_SECTION_RE = re.compile(r"^## (append|before|after|set)[ \t]*$", re.MULTILINE)
_NAME_RE = re.compile(r"^[\w.\- ]+\.md$", re.UNICODE)


class PatchError(MyelinError):
    """patch를 읽거나 적용할 수 없음 (fail-closed)."""


class Patch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    patch: Literal[1] = 1
    target: str = Field(min_length=1, max_length=512)
    kind: Literal["append", "replace", "frontmatter"]
    under: str | None = Field(default=None, pattern=r"^#{1,6} \S.*$")
    origin: Literal["claude", "human", "mixed"] = "claude"
    skill: str = Field(pattern=r"^[a-z][a-z-]*$")
    created: date
    rationale: str = Field(min_length=1, max_length=500)
    status: Literal["proposed", "applied", "rejected"] = "proposed"

    @field_validator("target")
    @classmethod
    def _relative(cls, v: str) -> str:
        p = PurePosixPath(v)
        if p.is_absolute() or ".." in p.parts or "\\" in v or v.startswith(PATCH_DIR):
            raise ValueError("target must be a Vault-relative note path outside _patches/")
        return p.as_posix()

    def required(self) -> set[str]:
        return {"append": {"append"}, "replace": {"before", "after"}, "frontmatter": {"set"}}[
            self.kind
        ]


@dataclass
class ParsedPatch:
    meta: Patch
    sections: dict[str, str]


def parse_patch(text: str, source: str) -> ParsedPatch:
    try:
        fm_text, body = split_frontmatter(text, source)
    except NoteParseError as err:
        raise PatchError("patch frontmatter가 없습니다", err.issues) from err
    data = load_yaml(fm_text, source, PatchError)
    if not isinstance(data, dict):
        raise PatchError("patch frontmatter는 mapping이어야 합니다", [Issue(source, "mapping")])
    try:
        meta = Patch.model_validate(data)
    except ValidationError as exc:
        raise PatchError("patch 형식 오류", issues_from_validation(exc, prefix=source)) from exc
    if meta.under and meta.kind != "append":
        raise PatchError("under 는 append 전용입니다", [Issue(f"{source}.under", meta.kind)])
    parts = _SECTION_RE.split(body)
    sections: dict[str, str] = {}
    for i in range(1, len(parts) - 1, 2):
        if parts[i] in sections:
            raise PatchError("같은 구획이 두 번 있습니다", [Issue(source, f"## {parts[i]}", "dup")])
        sections[parts[i]] = parts[i + 1].strip("\n")
    missing = meta.required() - set(sections)
    extra = set(sections) - meta.required()
    if missing or extra:
        raise PatchError(
            f"kind {meta.kind} 의 구획이 맞지 않습니다",
            [Issue(source, f"필요 {sorted(meta.required())}, 실제 {sorted(sections)}", "sections")],
        )
    if any(not sections[s].strip() for s in meta.required() if s != "after"):
        raise PatchError("빈 구획", [Issue(source, "내용 없음", "empty")])
    return ParsedPatch(meta, sections)


# ── 목록 ─────────────────────────────────────────────────────────────────
def _patch_path(vault: Path, rel: str) -> Path:
    pure = PurePosixPath(rel)
    if (
        len(pure.parts) != 2
        or pure.parts[0] != PATCH_DIR
        or not _NAME_RE.fullmatch(pure.name)
        or "\n" in rel
    ):
        raise PatchError("patch 경로가 올바르지 않습니다", [Issue("path", repr(rel), "bad_path")])
    path = vault / PATCH_DIR / pure.name
    if path.is_symlink() or (vault / PATCH_DIR).is_symlink() or not path.is_file():
        raise PatchError("patch를 찾을 수 없습니다", [Issue("path", rel, "not_found")])
    return path


def list_patches(vault: Path) -> list[dict[str, Any]]:
    """`_patches/*.md` — 구조화 patch는 적용 가능, 아니면 '수동'으로 표시."""
    root = vault / PATCH_DIR
    if not root.is_dir() or root.is_symlink():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(root.iterdir()):
        if not p.is_file() or p.is_symlink() or p.suffix != ".md":
            continue
        rel = f"{PATCH_DIR}/{p.name}"
        try:
            parsed = parse_patch(p.read_text(encoding="utf-8"), rel)
            m = parsed.meta
            out.append(
                {
                    "path": rel,
                    "structured": True,
                    "target": m.target,
                    "kind": m.kind,
                    "skill": m.skill,
                    "origin": m.origin,
                    "created": m.created.isoformat(),
                    "rationale": m.rationale,
                    "status": m.status,
                }
            )
        except (PatchError, UnicodeDecodeError) as err:
            reason = err.message if isinstance(err, PatchError) else "UTF-8 아님"
            out.append({"path": rel, "structured": False, "reason": reason})
    return out


# ── 계획 ─────────────────────────────────────────────────────────────────
@dataclass
class PatchPlan:
    patch_rel: str
    meta: Patch
    target_original: str
    target_new: str
    patch_original: str
    archived_rel: str
    archived_text: str
    diff: str
    warnings: list[str] = field(default_factory=list)

    @property
    def paths(self) -> list[str]:
        return sorted({self.meta.target, self.patch_rel, self.archived_rel})

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.patch_rel,
            "target": self.meta.target,
            "kind": self.meta.kind,
            "rationale": self.meta.rationale,
            "diff": self.diff,
            "warnings": self.warnings,
        }


def _eol(text: str) -> str:
    return "\r\n" if "\r\n" in text.split("\n", 1)[0] + "\n" else "\n"


def _body_offset(text: str) -> int:
    """닫는 `---` 줄 다음 위치 (원문 기준)."""
    lines = text.splitlines(keepends=True)
    pos = len(lines[0])
    for line in lines[1:]:
        pos += len(line)
        if line.strip() in ("---", "..."):
            return pos
    raise PatchError("대상 frontmatter를 찾을 수 없습니다", [Issue("target", "---", "no_fm")])


def _append(text: str, content: str, under: str | None, eol: str) -> str:
    block = content.replace("\r\n", "\n").rstrip("\n").replace("\n", eol) + eol
    if under is None:
        sep = "" if text.endswith(("\n", "\r\n")) else eol
        return text + sep + block
    body_start = _body_offset(text)
    lines = text[body_start:].splitlines(keepends=True)
    idx = [i for i, ln in enumerate(lines) if ln.rstrip("\r\n") == under]
    if len(idx) != 1:
        raise PatchError(
            "under 제목이 대상에 정확히 한 번 있어야 합니다",
            [Issue("under", f"{under!r} — {len(idx)}회", "under_not_found")],
        )
    level = len(under) - len(under.lstrip("#"))
    end = len(lines)
    for j in range(idx[0] + 1, len(lines)):
        m = re.match(r"^(#{1,6}) ", lines[j])
        if m and len(m.group(1)) <= level:
            end = j
            break
    # 구획 끝의 빈 줄 앞에 넣는다
    insert = end
    while insert > idx[0] + 1 and not lines[insert - 1].strip():
        insert -= 1
    if insert > 0 and not lines[insert - 1].endswith(("\n", "\r\n")):
        lines[insert - 1] += eol
    new_lines = [*lines[:insert], block, *lines[insert:]]
    return text[:body_start] + "".join(new_lines)


def _replace(text: str, before: str, after: str, eol: str) -> str:
    body_start = _body_offset(text)
    body = text[body_start:]
    b = before.replace("\r\n", "\n").replace("\n", eol)
    a = after.replace("\r\n", "\n").replace("\n", eol)
    count = body.count(b)
    if count != 1:
        raise PatchError(
            "before 가 본문에 정확히 한 번 있어야 합니다",
            [Issue("before", f"{count}회", "before_mismatch")],
        )
    return text[:body_start] + body.replace(b, a, 1)


def _frontmatter(text: str, rel: str, set_text: str) -> str:
    rt = YAML(typ="safe")
    data = rt.load(io.StringIO(set_text))
    if not isinstance(data, dict) or not data:
        raise PatchError("set 은 key: value 목록이어야 합니다", [Issue("set", set_text[:60])])
    bad = sorted(str(k) for k in data if k not in SETTABLE_KEYS)
    if bad:
        raise PatchError(
            "patch로 바꿀 수 없는 키입니다 (Review Gate·사람의 몫)",
            [Issue("set", k, "protected_key") for k in bad],
        )
    return set_fields(text, rel, dict(data))


def _new_links(before: str, after: str) -> set[str]:
    old = {lnk.target for lnk in extract_links(before)}
    return {lnk.target for lnk in extract_links(after)} - old


def plan_patch(vault: Path, patch_rel: str, today: date) -> PatchPlan:
    ppath = _patch_path(vault, patch_rel)
    raw_patch = ppath.read_bytes().decode("utf-8")
    parsed = parse_patch(raw_patch, patch_rel)
    meta = parsed.meta
    if meta.status != "proposed":
        raise PatchError("이미 처리된 patch입니다", [Issue("status", meta.status, "done")])
    if meta.target.startswith("40_IP/"):
        raise PatchError("40_IP 는 patch 대상이 아닙니다", [Issue("target", meta.target, "ip")])
    try:
        note, text = read_note(vault, meta.target)  # 경로·링크·스키마 검사 포함
    except ReviewError as err:
        raise PatchError(f"대상: {err.message}", err.issues) from err
    if note.frontmatter.classification is Classification.CONFIDENTIAL:
        raise PatchError("confidential 노트는 patch 대상이 아닙니다", [Issue("target", "conf")])

    eol = _eol(text)
    s = parsed.sections
    if meta.kind == "append":
        new = _append(text, s["append"], meta.under, eol)
    elif meta.kind == "replace":
        new = _replace(text, s["before"], s["after"], eol)
    else:
        try:
            new = _frontmatter(text, meta.target, s["set"])
        except ReviewError as err:
            raise PatchError(err.message, err.issues) from err
    if new == text:
        raise PatchError("바뀌는 내용이 없습니다", [Issue("patch", patch_rel, "noop")])
    try:
        after_note = parse_note(new, source=meta.target)
    except NoteParseError as err:
        raise PatchError("적용 결과가 노트 스키마를 어깁니다", err.issues) from err
    if after_note.frontmatter.id != note.frontmatter.id:
        raise PatchError("id가 바뀝니다", [Issue("id", note.frontmatter.id, "id_changed")])

    warnings: list[str] = []
    added = _new_links(text, new)
    if added:
        scan = scan_vault(vault)
        by_key: dict[str, Any] = {}
        for n in scan.notes:
            key = (n.path or "").removesuffix(".md").lower()
            by_key[key] = n
            by_key.setdefault(PurePosixPath(key).name, n)
        for target in sorted(added):
            hit = by_key.get(target.removesuffix(".md").lower())
            if hit is None:
                warnings.append(f"링크 대상 없음: [[{target}]]")
                continue
            unverified_ai = (
                hit.frontmatter.origin is not Origin.HUMAN
                and hit.frontmatter.status is not Status.VERIFIED
            )
            if after_note.frontmatter.status is Status.VERIFIED and unverified_ai:
                raise PatchError(
                    "verified 노트가 미검증 AI 노트를 링크하게 됩니다 — 그 노트를 먼저 검토하세요",
                    [
                        Issue(
                            hit.path or target,
                            "origin≠human, status≠verified",
                            "links_unverified_ai",
                        )
                    ],
                )

    archived_rel = f"{APPLIED_DIR}/{ppath.name}"
    if (vault / archived_rel).exists() or (vault / archived_rel).is_symlink():
        raise PatchError(
            "같은 이름의 적용 기록이 있습니다", [Issue(archived_rel, "exists", "exists")]
        )
    diff = "".join(
        difflib.unified_diff(
            text.replace("\r\n", "\n").splitlines(keepends=True),
            new.replace("\r\n", "\n").splitlines(keepends=True),
            fromfile=f"a/{meta.target}",
            tofile=f"b/{meta.target}",
            n=2,
        )
    )
    return PatchPlan(
        patch_rel=patch_rel,
        meta=meta,
        target_original=text,
        target_new=new,
        patch_original=raw_patch,
        archived_rel=archived_rel,
        archived_text=_with_status(raw_patch, "applied", today),
        diff=diff,
        warnings=warnings,
    )


def _with_status(raw: str, status: str, today: date) -> str:
    out, n = re.subn(r"(?m)^status:[ \t]*proposed[ \t]*$", f"status: {status}", raw, count=1)
    if n == 0:
        out = re.sub(r"(?m)^(patch:[ \t]*1[ \t]*)$", rf"\1\nstatus: {status}", raw, count=1)
    return re.sub(r"(?m)^(status: \w+)$", rf"\1\ndecided: {today.isoformat()}", out, count=1)


# ── 적용 · 반려 · 되돌리기 ───────────────────────────────────────────────
def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".myelin-tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(text.encode("utf-8"))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _create(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise PatchError("보관 폴더가 링크입니다", [Issue(str(path.parent), "symlink")])
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o644)
    with os.fdopen(fd, "wb") as fh:
        fh.write(text.encode("utf-8"))


def apply_plan(vault: Path, plan: PatchPlan) -> None:
    target = vault / plan.meta.target
    if target.read_bytes().decode("utf-8") != plan.target_original:
        raise PatchError("계획 이후 대상이 바뀌었습니다", [Issue(plan.meta.target, "stale")])
    _atomic_write(target, plan.target_new)
    try:
        _create(vault / plan.archived_rel, plan.archived_text)
    except BaseException:
        _atomic_write(target, plan.target_original)
        raise
    (vault / plan.patch_rel).unlink()


def revert_plan(vault: Path, plan: PatchPlan) -> None:
    _atomic_write(vault / plan.meta.target, plan.target_original)
    (vault / plan.patch_rel).write_bytes(plan.patch_original.encode("utf-8"))
    (vault / plan.archived_rel).unlink(missing_ok=True)


@dataclass
class RejectPlan:
    patch_rel: str
    patch_original: str
    archived_rel: str
    archived_text: str

    @property
    def paths(self) -> list[str]:
        return sorted({self.patch_rel, self.archived_rel})


def plan_reject(vault: Path, patch_rel: str, today: date) -> RejectPlan:
    ppath = _patch_path(vault, patch_rel)
    raw = ppath.read_bytes().decode("utf-8")
    archived = f"{REJECTED_DIR}/{ppath.name}"
    if (vault / archived).exists():
        raise PatchError("같은 이름의 반려 기록이 있습니다", [Issue(archived, "exists", "exists")])
    try:
        parse_patch(raw, patch_rel)
        text = _with_status(raw, "rejected", today)
    except PatchError:
        text = raw  # 수동(비구조화) patch도 반려(보관)는 할 수 있다
    return RejectPlan(patch_rel, raw, archived, text)


def apply_reject(vault: Path, plan: RejectPlan) -> None:
    _create(vault / plan.archived_rel, plan.archived_text)
    (vault / plan.patch_rel).unlink()


def revert_reject(vault: Path, plan: RejectPlan) -> None:
    (vault / plan.patch_rel).write_bytes(plan.patch_original.encode("utf-8"))
    (vault / plan.archived_rel).unlink(missing_ok=True)
