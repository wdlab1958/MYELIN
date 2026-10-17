"""Vault 생성·확장 렌더러 (명세 §6, ADR-0005).

모든 작업은 두 단계다:
1. plan  — 쓸 파일 전체를 메모리에서 렌더링한다 (결정론적, `today` 주입).
2. apply — 하나라도 기존 파일과 겹치면 아무것도 쓰지 않는다 (fail-closed).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from myelin_core.config import CONFIG_FILE, LEVEL_DESCRIPTIONS, VaultConfig, render_config
from myelin_core.errors import Issue, MyelinError
from myelin_core.loader import LoadedPack
from myelin_core.lock import LOCK_FILE, lock_from_packs, render_lock
from myelin_core.pack import Domain, Term

VAULT_DIRS = (
    "00_Inbox/ai-drafts",
    "00_Inbox/clips",
    "10_Domains",
    "20_Projects",
    "30_Resources",
    "40_IP",
    "50_Journal",
    "80_Outputs/drafts",
    "90_System/templates",
    "99_Archive",
    "_patches",
)
TAXONOMY_FILE = "90_System/taxonomy.md"
INTERVIEWS_FILE = "90_System/interviews.md"
CLAUDE_FILE = "CLAUDE.md"
MARK_START = "<!-- myelin:generated:start -->"
MARK_END = "<!-- myelin:generated:end -->"

GITIGNORE = """\
# MYELIN — Vault 로컬 상태 (공유하지 않음)
.myelin/
.trash/
.obsidian/workspace*.json
.obsidian/cache
"""


class ScaffoldError(MyelinError):
    """Vault를 만들거나 확장할 수 없음."""


@dataclass
class Plan:
    """상대경로 -> 텍스트. `updates` 는 기존 시스템 파일을 바꾸는 항목 (add-domain 전용)."""

    files: dict[str, str] = field(default_factory=dict)
    updates: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DomainRef:
    pack: LoadedPack
    domain: Domain


def domain_index(packs: Sequence[LoadedPack]) -> dict[str, DomainRef]:
    return {d.id: DomainRef(p, d) for p in packs for d in p.domains}


# ── 렌더링 조각 ───────────────────────────────────────────────────────────
def _display(d: Domain) -> str:
    return f"{d.label} · {d.name}" if d.label else d.name


def render_moc(d: Domain, today: date) -> str:
    subs = "\n".join(f"### {s}\n" for s in d.sub_mocs)
    return (
        "---\n"
        f"id: {today:%Y%m%d}-0000-moc-{d.id.lower()}\n"
        "type: moc\n"
        f"domain: [{d.id}]\n"
        "status: verified\n"
        "origin: human\n"
        f"classification: {d.classification_default.value}\n"
        f"created: {today.isoformat()}\n"
        "tags: [moc]\n"
        "---\n"
        f"# {_display(d)}\n\n"
        f"> {d.description or 'Domain 지형도'}\n>\n"
        "> 이 MOC에는 verified 노트만 링크한다.\n\n"
        "## Sub-MOC\n\n"
        f"{subs}\n"
        "## 핵심 Evergreen\n\n"
        "## 진행 중 Projects\n\n"
        "## 열린 질문\n"
    )


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _term_row(term: Term) -> str:
    return f"| {_cell(term.term)} | {_cell(', '.join(term.aliases))} | {_cell(term.definition)} |"


def _domain_terms(ref: DomainRef) -> list[Term]:
    seed = ref.domain.taxonomy_seed
    return ref.pack.taxonomies[seed].terms if seed else []


def render_taxonomy_section(ref: DomainRef) -> str:
    lines = [
        f"## {ref.domain.id} — {ref.domain.name}",
        "",
        "| 용어 | 별칭 | 정의 |",
        "|---|---|---|",
    ]
    seen = False
    for term in _domain_terms(ref):
        if term.domain == ref.domain.id:
            lines.append(_term_row(term))
            seen = True
    if not seen:
        lines.append("| | | |")
    return "\n".join(lines) + "\n"


def render_common_terms(refs: Sequence[DomainRef]) -> str:
    rows: dict[str, str] = {}
    for ref in refs:
        for term in _domain_terms(ref):
            if term.domain is None:
                rows[term.term] = _term_row(term)
    if not rows:
        return ""
    return "## 공통\n\n| 용어 | 별칭 | 정의 |\n|---|---|---|\n" + "\n".join(rows.values()) + "\n"


def render_taxonomy(refs: Sequence[DomainRef]) -> str:
    parts = [
        "# Taxonomy — 통제 어휘\n\n"
        "> Pack에서 가져온 용어 사전입니다. Claude는 노트를 정리할 때 이 용어를 따릅니다.\n"
        "> 새 용어는 맨 아래 **제안** 절에 적으세요.\n",
        render_common_terms(refs),
        *(render_taxonomy_section(r) for r in refs),
    ]
    return "\n".join(p for p in parts if p) + "\n## 제안\n\n"


def render_interview_section(ref: DomainRef) -> str:
    lines = [f"## {ref.domain.id} — {ref.domain.name}", ""]
    bank = ref.pack.interview_banks.get(ref.domain.interview_bank or "")
    questions = bank.domains.get(ref.domain.id, []) if bank else []
    if not questions:
        lines.append("_(질문 은행 없음 — 직접 추가하세요)_")
    for q in questions:
        lines.append(f"- **{q.id}** — {q.q}")
        lines.extend(f"  - {f}" for f in q.follow_ups)
    return "\n".join(lines) + "\n"


def render_interviews(refs: Sequence[DomainRef]) -> str:
    head = (
        "# Interview Bank — 암묵지 추출 질문\n\n"
        "> `/interview` 가 이 질문으로 경험을 묻고 lesson 노트 초안을 만듭니다.\n"
    )
    return "\n".join([head, *(render_interview_section(r) for r in refs)])


def render_generated_block(cfg: VaultConfig, refs: dict[str, DomainRef]) -> str:
    rows = ["| Role | ID | Label | Name |", "|---|---|---|---|"]
    for domain_id in cfg.domains.all():
        d = refs[domain_id].domain
        rows.append(f"| {cfg.domains.role_of(domain_id)} | {d.id} | {d.label or ''} | {d.name} |")
    return "\n".join(
        [
            MARK_START,
            "## Domains",
            "",
            *rows,
            "",
            f"## Level: {cfg.level}",
            f"- {LEVEL_DESCRIPTIONS[cfg.level]}",
            MARK_END,
        ]
    )


def render_claude_md(cfg: VaultConfig, refs: dict[str, DomainRef]) -> str:
    return f"""# MYELIN Vault — Operating Rules for Claude

<!-- myelin init 이 만든 파일입니다. 표시된 자동 생성 구간 밖은 자유롭게 고쳐도 됩니다. -->

## Owner
- {cfg.owner.name}. 노트와 응답은 `{cfg.language}` 로, 기술 용어는 영어를 병기한다.

{render_generated_block(cfg, refs)}

## Write Policy (fail-closed)
- 새 노트는 `00_Inbox/ai-drafts/` 에만 만든다 (`origin: claude`, `status: draft`).
- 그 외 경로의 노트는 직접 고치지 않는다. 변경은 `_patches/YYYYMMDD-<topic>.md` 로 제안한다.
- `40_IP/` 와 `classification: confidential` 노트는 읽기만 하고, 외부 도구로 보내지 않는다.
- verified 승격, MOC 편집, 공유는 사람만 한다.

## Note Conventions
- 1 노트 = 1 개념. 제목은 주장형 문장을 권장한다.
- 용어는 `90_System/taxonomy.md` 를 따른다. 새 용어는 그 파일의 "제안" 절에 추가를 요청한다.
- 외부 사실에는 `source` 를 기록한다. 출처가 불분명하면 `confidence: low`.
- 템플릿: `90_System/templates/` · 인터뷰 질문: `90_System/interviews.md`

## Linking
- 링크를 제안할 때는 근거(공통 개념·인과·대조)를 한 줄로 적는다.
- `status: verified` 가 아닌 노트를 MOC에 넣자고 제안하지 않는다.

## 개인 메모
"""


# ── 계획 ─────────────────────────────────────────────────────────────────
def _template_files(pack: LoadedPack, rel_dir: str | None, dest: str) -> dict[str, str]:
    if rel_dir is None:
        return {}
    src = pack.root / rel_dir
    return {
        f"{dest}/{p.relative_to(src).as_posix()}": p.read_text(encoding="utf-8")
        for p in sorted(src.rglob("*"))
        if p.is_file()
    }


def _pack_templates(pack: LoadedPack, domain_ids: set[str]) -> dict[str, str]:
    is_core = pack.manifest.kind.value == "core"
    dest = "90_System/templates" if is_core else f"90_System/templates/{pack.name}"
    files = _template_files(pack, pack.manifest.templates, dest)
    for d in pack.domains:
        if d.id in domain_ids:
            files.update(_template_files(pack, d.templates, dest))
    return files


def _selected_refs(cfg: VaultConfig, packs: Sequence[LoadedPack]) -> dict[str, DomainRef]:
    index = domain_index(packs)
    missing = cfg.missing_domains(set(index))
    if missing:
        raise ScaffoldError("선택한 Domain을 Pack에서 찾을 수 없습니다", missing)
    return {i: index[i] for i in cfg.domains.all()}


def plan_init(cfg: VaultConfig, packs: Sequence[LoadedPack], today: date) -> Plan:
    refs = _selected_refs(cfg, packs)
    ordered = list(refs.values())
    plan = Plan()
    f = plan.files
    f[CONFIG_FILE] = render_config(cfg)
    f[CLAUDE_FILE] = render_claude_md(cfg, refs)
    f[".gitignore"] = GITIGNORE
    f[LOCK_FILE] = render_lock(lock_from_packs(packs))
    f[TAXONOMY_FILE] = render_taxonomy(ordered)
    f[INTERVIEWS_FILE] = render_interviews(ordered)
    for d in VAULT_DIRS:
        f[f"{d}/.gitkeep"] = ""
    for ref in ordered:
        f[f"10_Domains/{ref.domain.id}/_MOC.md"] = render_moc(ref.domain, today)
    for pack in packs:
        f.update(_pack_templates(pack, set(refs)))
    return plan


def plan_add_domain(
    vault: Path,
    new_cfg: VaultConfig,
    new_cfg_text: str,
    packs: Sequence[LoadedPack],
    added_packs: set[str],
    domain_id: str,
    today: date,
) -> Plan:
    refs = _selected_refs(new_cfg, packs)
    ref = refs[domain_id]
    plan = Plan()
    plan.files[f"10_Domains/{domain_id}/_MOC.md"] = render_moc(ref.domain, today)
    for pack in packs:
        if pack.name in added_packs:
            plan.files.update(_pack_templates(pack, {domain_id}))
        elif pack is ref.pack and ref.domain.templates:
            plan.files.update(
                _template_files(pack, ref.domain.templates, f"90_System/templates/{pack.name}")
            )
    plan.updates[CONFIG_FILE] = new_cfg_text
    plan.updates[LOCK_FILE] = render_lock(lock_from_packs(packs))
    for rel, section in (
        (TAXONOMY_FILE, render_taxonomy_section(ref)),
        (INTERVIEWS_FILE, render_interview_section(ref)),
    ):
        current = (vault / rel).read_text(encoding="utf-8") if (vault / rel).is_file() else ""
        plan.updates[rel] = current.rstrip("\n") + "\n\n" + section
    claude = vault / CLAUDE_FILE
    if claude.is_file():
        text = claude.read_text(encoding="utf-8")
        start, end = text.find(MARK_START), text.find(MARK_END)
        if 0 <= start < end:
            block = render_generated_block(new_cfg, refs)
            plan.updates[CLAUDE_FILE] = text[:start] + block + text[end + len(MARK_END) :]
    return plan


def apply_plan(root: Path, plan: Plan) -> list[str]:
    """겹치는 파일이 하나라도 있으면 아무것도 쓰지 않는다."""
    clashes = sorted(rel for rel in plan.files if (root / rel).exists())
    missing = sorted(rel for rel in plan.updates if not (root / rel).parent.is_dir())
    if clashes or missing:
        issues = [Issue(rel, "이미 존재합니다 — 덮어쓰지 않습니다", "exists") for rel in clashes]
        issues += [Issue(rel, "상위 폴더가 없습니다", "missing_dir") for rel in missing]
        raise ScaffoldError("Vault에 쓸 수 없습니다", issues)
    written: list[str] = []
    for rel, text in {**plan.files, **plan.updates}.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        written.append(rel)
    return written
