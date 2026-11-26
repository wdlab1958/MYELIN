"""One Cycle Dev. Framework hand-off — MYELIN is the receiving end (WBS 3.6, ADR-0018).

Other platforms (LLMOps · SSC · ARGUS · Proof-Skills) hand knowledge over as files:

1. Markdown drafts they drop into `<Vault>/00_Inbox/ai-drafts/` with frontmatter
   `source_platform: llmops|ssc|argus|proof-skills`. Frontmatter v2 keeps unknown keys, so these
   are ordinary AI drafts: Review Gate, doctor and the pre-commit device apply unchanged.
   `route_domain()` proposes the Domain when a draft names none.
2. An `onecycle.findings/v1` JSON file. `import_findings()` turns it into one draft note per
   finding.

The importer is deterministic code (no LLM). It creates new files in `00_Inbox/ai-drafts` only,
never overwrites, never edits `myelin.yaml`, never runs git, and is idempotent on the finding id.
Every note passes the customer-information guard (`infoguard`) before it is written: a blocked
note is not written at all, a flagged one is written with a visible marker for the reviewer.
A file that is invalid or has no findings is refused — nothing is written.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from myelin_core.infoguard import GuardError, GuardPolicy, GuardReport, scan_text
from myelin_core.note import NoteParseError, format_validation_error, parse_note
from myelin_core.schema.frontmatter import DOMAIN_ID_RE
from myelin_core.vault import AI_DRAFTS, ARCHIVE, DOMAINS, Vault

SCHEMA_ID = "onecycle.findings/v1"
SCHEMA_FILE = Path(__file__).resolve().parent / "schema" / "onecycle.findings.v1.schema.json"
SOURCE_PLATFORM_KEY = "source_platform"
Platform = Literal["llmops", "ssc", "proof-skills", "argus"]
PLATFORMS: tuple[str, ...] = ("llmops", "ssc", "proof-skills", "argus")
# Routing rule: where a draft from each platform belongs when its Domain is configured.
# PROOF-SKILLS is declared by the pack shipped with WDLAB-Proof-Skills, the others by
# packs/wdlab.onecycle.
PLATFORM_DOMAIN: dict[str, str] = {
    "llmops": "LLMOPS",
    "ssc": "SSC",
    "argus": "ARGUS",
    "proof-skills": "PROOF-SKILLS",
}
PLATFORM_LABEL: dict[str, str] = {
    "llmops": "WDLAB-LLMOps",
    "ssc": "SSC",
    "argus": "ARGUS",
    "proof-skills": "WDLAB-Proof-Skills",
}
MAX_FILE_BYTES = 8 * 1024 * 1024
_BAD_NAME = re.compile(r'[\\/:*?"<>|#^\[\]\x00-\x1f\x7f‪-‮⁦-⁩]+')
_MARKER_RE = re.compile(r"onecycle:[^\s\"'\]]+")


class OneCycleError(ValueError):
    """The hand-off file is refused (invalid, empty, unreadable). Nothing was written."""


# ----------------------------------------------------------------------------- schema (strict)
class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Source(_Strict):
    platform: Platform
    version: str | None = None
    run_id: str | None = None
    generated_at: str

    @field_validator("generated_at")
    @classmethod
    def _is_datetime(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("generated_at must be an RFC 3339 date-time") from None
        if "T" not in v.upper():
            raise ValueError("generated_at must be an RFC 3339 date-time")
        return v


class Subject(_Strict):
    name: str = Field(min_length=1)
    repo: str | None = None
    commit: str | None = None
    environment: str | None = None


class Evidence(_Strict):
    kind: Literal["trace", "test", "tlc_log", "proof", "alert", "scan", "doc", "commit"]
    ref: str = Field(min_length=1)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class Location(_Strict):
    file: str | None = None
    line: int | None = Field(default=None, ge=1)
    component: str | None = None


class Links(_Strict):
    mitre: list[str] | None = None
    iso27001: list[str] | None = None
    upstream: list[str] | None = None


class Finding(_Strict):
    id: str = Field(pattern=r"^(llmops|ssc|proof-skills|argus):.+")
    title: str = Field(min_length=1)
    description: str | None = None
    category: Literal["quality", "security", "formal", "operations"]
    severity: Literal["critical", "high", "medium", "low", "info"]
    status: Literal["open", "confirmed", "fixed", "accepted", "false_positive"]
    simulated: bool
    evidence: list[Evidence]
    location: Location | None = None
    recommendation: str | None = None
    links: Links | None = None


class FindingsFile(_Strict):
    schema_id: Literal["onecycle.findings/v1"] = Field(alias="schema")
    source: Source
    subject: Subject
    findings: list[Finding]


def load_findings(path: Path) -> FindingsFile:
    """Read and validate an `onecycle.findings/v1` file. Raises OneCycleError."""
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise OneCycleError(f"{path.name}: larger than {MAX_FILE_BYTES} bytes — refused")
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise OneCycleError(f"cannot read {path}: {exc}") from None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OneCycleError(f"{path.name}: not a JSON file: {exc}") from None
    if not isinstance(raw, dict):
        raise OneCycleError(f"{path.name}: top level must be an object")
    for key in ("source", "subject"):  # explicit nulls are not "absent"
        _reject_nulls(raw.get(key), f"{path.name}: {key}")
    for i, f in enumerate(
        raw.get("findings") or [] if isinstance(raw.get("findings"), list) else []
    ):
        _reject_nulls(f, f"{path.name}: findings[{i}]")
    try:
        doc = FindingsFile.model_validate(raw)
    except ValidationError as exc:
        raise OneCycleError(
            f"{path.name}: not a valid {SCHEMA_ID} file: {format_validation_error(exc)}"
        ) from None
    if not doc.findings:
        raise OneCycleError(f"{path.name}: no findings — nothing to import")
    ids = [f.id for f in doc.findings]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise OneCycleError(f"{path.name}: duplicate finding id(s) {dupes}")
    return doc


def _reject_nulls(obj: Any, where: str) -> None:
    """JSON Schema has no `null` type anywhere in v1; Pydantic's Optional would let it through."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if v is None:
                raise OneCycleError(f"{where}.{k}: null is not allowed")
            _reject_nulls(v, f"{where}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if v is None:
                raise OneCycleError(f"{where}[{i}]: null is not allowed")
            _reject_nulls(v, f"{where}[{i}]")


# ----------------------------------------------------------------------------- routing
def route_domain(source_platform: object, configured: list[str]) -> str | None:
    """Domain for a draft from `source_platform`, or None when that Domain is not in the Vault."""
    if not isinstance(source_platform, str):
        return None
    dom = PLATFORM_DOMAIN.get(source_platform.strip().lower())
    return dom if dom and dom in configured else None


# ----------------------------------------------------------------------------- rendering
def _slug(text: str, limit: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s or "finding")[:limit].strip("-") or "finding"


def _file_name(text: str) -> str:
    return re.sub(r"\s+", " ", _BAD_NAME.sub(" ", text)).strip(" .")[:100].strip(" .") or "finding"


def _one_line(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _yaml_str(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)  # a JSON string is a valid YAML scalar


def marker(finding_id: str) -> str:
    return f"onecycle:{finding_id}"


def _tag(text: str) -> str:
    return _slug(text, 40)


def render_finding_note(
    doc: FindingsFile, f: Finding, *, domain: str | None, now: datetime, flags: GuardReport | None
) -> str:
    platform = doc.source.platform
    digest = hashlib.sha1(f.id.encode("utf-8")).hexdigest()[:6]
    note_id = f"{now:%Y%m%d-%H%M}-{_slug(f.title)}-{digest}"
    tags = ["onecycle", _tag(platform), f.category, f"sev-{f.severity}"]
    if f.simulated:
        tags.append("simulated")
    if flags is not None and flags.flagged:
        tags.append("guard-flag")
    fm = [
        "---",
        f"id: {note_id}",
        "type: lesson",
        f"domain: [{domain}]" if domain else "domain: []",
        "status: draft",
        "origin: claude",
        f"confidence: {'low' if f.simulated else 'medium'}",
        "classification: internal",
        "share: false",
        f"source: [{_yaml_str(marker(f.id))}]",
        f"created: {now:%Y-%m-%d}",
        f"tags: [{', '.join(dict.fromkeys(tags))}]",
        f"{SOURCE_PLATFORM_KEY}: {platform}",
        f"onecycle_schema: {SCHEMA_ID}",
        f"onecycle_status: {f.status}",
        f"simulated: {'true' if f.simulated else 'false'}",
        "---",
    ]
    label = PLATFORM_LABEL[platform]
    body = [
        f"# {_one_line(f.title)}",
        "",
        f"> {label} 가 넘긴 `{SCHEMA_ID}` 파일에서 만든 초안이다. 내용은 그 파일의 값 그대로이며 "
        "MYELIN 이 판단하거나 보탠 것은 없다. 확인한 뒤 승격한다.",
    ]
    if f.simulated:
        body.append(
            "> **simulated: true** — 실제 대상에서 측정한 결과가 아니다(데모·모의 모드). "
            "사실로 인용하지 않는다."
        )
    if flags is not None and flags.flagged:
        body.append(
            "> **고객정보 가드 표시** — 승격 전에 확인: "
            + ", ".join(sorted({h.rule for h in flags.flags}))
        )
    body += [
        "",
        "| 항목 | 값 |",
        "|---|---|",
        f"| finding id | `{f.id}` |",
        f"| 출처 플랫폼 | {label}"
        + (f" {doc.source.version}" if doc.source.version else "")
        + (f" · run `{doc.source.run_id}`" if doc.source.run_id else "")
        + " |",
        f"| 생성 시각 | {doc.source.generated_at} |",
        f"| 대상 | {_one_line(doc.subject.name)}"
        + (f" · {doc.subject.environment}" if doc.subject.environment else "")
        + " |",
        f"| 분류 · 심각도 · 상태 | {f.category} · {f.severity} · {f.status} |",
    ]
    if f.location is not None:
        loc = " · ".join(
            x
            for x in (
                f.location.component,
                f.location.file and f"`{f.location.file}`",
                f.location.line and f"line {f.location.line}",
            )
            if x
        )
        if loc:
            body.append(f"| 위치 | {loc} |")
    body += ["", "## 내용", "", (f.description or "(설명 없음)").strip(), ""]
    body += ["## 증거 (참조만 — 원본은 출처 플랫폼에 있다)", ""]
    if f.evidence:
        for e in f.evidence:
            body.append(
                f"- {e.kind}: `{_one_line(e.ref)}`"
                + (f" (sha256 `{e.sha256}`)" if e.sha256 else "")
            )
    else:
        body.append("- (증거 참조 없음 — 출처 파일에 evidence 가 비어 있다)")
    body += ["", "## 권고", "", (f.recommendation or "(권고 없음)").strip(), ""]
    if f.links is not None:
        rows = [
            ("MITRE ATT&CK", f.links.mitre),
            ("ISO/IEC 27001", f.links.iso27001),
            ("선행 finding", f.links.upstream),
        ]
        if any(v for _, v in rows):
            body += ["## 연결", ""]
            body += [f"- {k}: {', '.join(f'`{x}`' for x in v)}" for k, v in rows if v]
            body.append("")
    body += [
        "## 교훈 (사람이 채운다)",
        "",
        "- 다른 프로젝트에서 같은 문제를 어떻게 먼저 찾을 수 있나?",
        "- 고객명·시스템명·IP·코드는 적지 않는다 (`docs/guides/knowledge-management-policy.md`).",
        "",
    ]
    return "\n".join(fm) + "\n" + "\n".join(body)


# ----------------------------------------------------------------------------- import
@dataclass
class ImportedNote:
    finding_id: str
    path: str
    flagged: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    created: list[ImportedNote] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (finding id, existing path)
    blocked: list[tuple[str, str]] = field(default_factory=list)  # (finding id, masked reason)
    domain: str | None = None
    hint: str | None = None

    @property
    def ok(self) -> bool:
        return not self.blocked

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "domain": self.domain,
            "created": [c.__dict__ for c in self.created],
            "skipped": [{"finding_id": i, "path": p} for i, p in self.skipped],
            "blocked": [{"finding_id": i, "reason": r} for i, r in self.blocked],
            "hint": self.hint,
        }


def existing_markers(vault: Vault) -> dict[str, str]:
    """`onecycle:<finding id>` → note path, for drafts, promoted and rejected notes."""
    found: dict[str, str] = {}
    for base in (AI_DRAFTS, DOMAINS, f"{ARCHIVE}/rejected"):
        d = vault.root / base
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.md")):
            try:
                head = p.read_text(encoding="utf-8", errors="replace")[:4000]
            except OSError:
                continue
            fm = head.split("\n---", 1)[0]
            for m in _MARKER_RE.findall(fm):
                found.setdefault(m, vault.rel(p))
    return found


def import_findings(
    vault: Vault,
    path: Path,
    *,
    now: datetime,
    domain: str | None = None,
    dry_run: bool = False,
) -> ImportResult:
    """One draft per finding in `00_Inbox/ai-drafts`. Raises OneCycleError when the file (or the
    guard policy, or `domain`) is refused; then nothing is written."""
    doc = load_findings(path)
    configured = list(vault.config.domains.all_ids)
    if domain is not None:
        if not DOMAIN_ID_RE.match(domain) or domain not in configured:
            raise OneCycleError(f"domain {domain!r} is not configured in this Vault")
        target: str | None = domain
    else:
        target = route_domain(doc.source.platform, configured)
    try:
        policy = GuardPolicy.load(vault.root)
    except GuardError as exc:
        raise OneCycleError(f"customer-information guard policy unreadable: {exc}") from None
    res = ImportResult(domain=target)
    if target is None:
        want = PLATFORM_DOMAIN[doc.source.platform]
        res.hint = (
            f"Domain {want} 이(가) Vault 에 없어 초안에 domain 을 넣지 않았다 — "
            f"`myelin add-domain {want}` 후 Review Gate 에서 Domain 을 고르거나 --domain 을 준다"
        )
    known = existing_markers(vault)
    drafts = vault.root / AI_DRAFTS
    for f in doc.findings:
        mk = marker(f.id)
        if mk in known:
            res.skipped.append((f.id, known[mk]))
            continue
        text = render_finding_note(doc, f, domain=target, now=now, flags=None)
        report = scan_text(text, policy)
        if report.blocked:
            res.blocked.append((f.id, GuardReport(report.blocks).summary()))
            continue
        if report.flagged:
            text = render_finding_note(doc, f, domain=target, now=now, flags=report)
        try:
            parse_note(text)
        except NoteParseError as exc:  # a title that breaks the frontmatter etc. — fail-closed
            res.blocked.append((f.id, f"rendered note is not valid Frontmatter v2: {exc}"))
            continue
        digest = hashlib.sha1(f.id.encode("utf-8")).hexdigest()[:6]
        label = PLATFORM_LABEL[doc.source.platform]
        name = f"{_file_name(f'{label} - {_one_line(f.title)}')} ({digest}).md"
        rel = f"{AI_DRAFTS}/{name}"
        if not dry_run:
            drafts.mkdir(parents=True, exist_ok=True)
            try:
                with (drafts / name).open("x", encoding="utf-8") as fh:  # never overwrite
                    fh.write(text)
            except FileExistsError:
                res.skipped.append((f.id, rel))
                continue
        res.created.append(ImportedNote(f.id, rel, sorted({h.rule for h in report.flags})))
        known[mk] = rel
    return res
