"""Renderers: templates (`{{placeholder}}`), Domain MOC, taxonomy.md, Vault CLAUDE.md.

CLAUDE.md is regenerated from packs on init/add-domain; the user's own text between the
`myelin:personal` markers is preserved verbatim (P2-T6).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime

from myelin_core.config import LEVEL_NAMES, MyelinConfig
from myelin_core.packs.loader import LoadedPack
from myelin_core.schema.pack import Domain, Taxonomy

PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
PERSONAL_START = "<!-- myelin:personal:start -->"
PERSONAL_END = "<!-- myelin:personal:end -->"
GENERATED_MARK = "<!-- myelin:generated — 이 블록은 `myelin init` / `myelin add-domain` 이 Pack에서 다시 생성한다. 개인 규칙은 아래 personal 블록에. -->"


def make_note_id(now: datetime, slug: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")[:64] or "note"
    return f"{now:%Y%m%d-%H%M}-{s}"


def render_template(text: str, values: Mapping[str, object]) -> str:
    """Replace `{{key}}` with values; lists render as YAML flow lists; missing keys → empty."""

    def repl(m: re.Match[str]) -> str:
        v = values.get(m.group(1), "")
        if isinstance(v, list | tuple):
            return "[" + ", ".join(str(x) for x in v) + "]"
        if isinstance(v, date):
            return v.isoformat()
        return str(v)

    return PLACEHOLDER_RE.sub(repl, text)


def render_moc(domain: Domain, pack: LoadedPack, cfg: MyelinConfig, now: datetime) -> str:
    role = cfg.domains.roles.get(domain.id, "extra")
    sub = (
        "\n".join(f"- [[{domain.id} - {s}|{s}]]" for s in domain.sub_mocs)
        or "- (Pack에 Sub-MOC 없음)"
    )
    targets = "\n".join(f"- {t}" for t in domain.compose_targets) or "- (없음)"
    types = ", ".join(t.value for t in domain.note_types)
    return (
        "---\n"
        f"id: {make_note_id(now, f'{domain.id}-moc')}\n"
        "type: moc\n"
        f"domain: [{domain.id}]\n"
        "status: verified\n"
        "origin: human\n"
        "confidence: high\n"
        f"classification: {domain.classification_default.value}\n"
        "share: false\n"
        "source: []\n"
        f"created: {now:%Y-%m-%d}\n"
        f"reviewed: {now:%Y-%m-%d}\n"
        "tags: [moc]\n"
        "---\n"
        f"# {domain.id} · {domain.name}\n\n"
        f"> {domain.description or domain.name}\n\n"
        f"- 역할: **{role}** (3+1 규칙) · Pack: `{pack.name}` v{pack.pack.version} · accent: `{domain.accent}`\n"
        f"- 노트 유형: {types} · 기본 보안등급: {domain.classification_default.value}\n\n"
        "## Sub-MOC\n"
        f"{sub}\n\n"
        "## 산출물 목표 (/compose)\n"
        f"{targets}\n\n"
        "## 최근 verified\n"
        "<!-- /review 가 갱신 제안을 _patches/ 에 둔다 -->\n\n"
        "## 열린 질문\n"
    )


def render_taxonomy_md(entries: Sequence[tuple[str, Taxonomy]], now: datetime) -> str:
    """entries = [(pack name, taxonomy)]; rendered as a lookup table grouped by pack."""
    out = [
        "---",
        f"id: {make_note_id(now, 'taxonomy')}",
        "type: moc",
        "domain: []",
        "status: verified",
        "origin: human",
        "confidence: high",
        "classification: internal",
        "share: false",
        "source: []",
        f"created: {now:%Y-%m-%d}",
        f"reviewed: {now:%Y-%m-%d}",
        "tags: [taxonomy, system]",
        "---",
        "# Taxonomy — 용어 정규화 사전",
        "",
        "> Pack의 `taxonomy.yaml`에서 생성. /distill 은 별칭을 대표 용어로 정규화한다. 수정은 Pack 또는 아래 개인 섹션에.",
        "",
    ]
    for pack_name, tax in entries:
        out += [f"## {pack_name}", "", "| 용어 | 별칭 | Domain | 정의 |", "|---|---|---|---|"]
        for t in tax.terms:
            out.append(
                f"| {t.term} | {', '.join(t.aliases)} | {', '.join(t.domain)} | {t.definition.replace('|', '/')} |"
            )
        out.append("")
    out += [PERSONAL_START, "", "## 개인 용어", "", PERSONAL_END, ""]
    return "\n".join(out)


def _personal_block(previous: str | None) -> str:
    if previous and PERSONAL_START in previous and PERSONAL_END in previous:
        inner = previous.split(PERSONAL_START, 1)[1].split(PERSONAL_END, 1)[0]
        return f"{PERSONAL_START}{inner}{PERSONAL_END}"
    return f"{PERSONAL_START}\n\n## 개인 규칙\n\n- (여기에 나만의 규칙을 적는다. Pack 재생성 시 보존된다.)\n\n{PERSONAL_END}"


def render_claude_md(
    cfg: MyelinConfig,
    packs: Sequence[LoadedPack],
    now: datetime,
    previous: str | None = None,
    *,
    ai_write_allow: Sequence[str],
) -> str:
    domains: list[tuple[Domain, LoadedPack]] = [
        (d, lp) for lp in packs for d in lp.pack.domains if d.id in cfg.domains.all_ids
    ]
    roles = cfg.domains.roles
    dom_lines = "\n".join(
        f"- **{d.id}** {d.name} — {roles.get(d.id, 'extra')} · `10_Domains/{d.id}/` · Sub-MOC: {', '.join(d.sub_mocs)}"
        for d, _ in domains
    )
    types = sorted({t.value for d, _ in domains for t in d.note_types})
    pack_lines = "\n".join(
        f"- `{lp.name}` v{lp.pack.version} ({lp.pack.kind.value}) — {lp.pack.maintainer}"
        for lp in packs
    )
    allow = "\n".join(f"- `{p}/`" for p in ai_write_allow)
    level = cfg.level
    skills = {
        0: "(없음 — 읽기·검색만)",
        1: "/ingest · /distill · /interview · /review",
        2: "/ingest · /distill · /interview · /review · /link · /compose",
        3: "/ingest · /distill · /interview · /review · /link · /compose · /ip-scan",
    }[level]
    routes = "\n".join(f"- `{k}` → {v}" for k, v in cfg.llm.route.items())
    generated = f"""# {cfg.owner.name}의 MYELIN Vault — Claude 운영 규칙

{GENERATED_MARK}

## Vault
- Owner: {cfg.owner.name}{f" · {cfg.owner.team}" if cfg.owner.team else ""} · 언어: {cfg.language} · 생성: {now:%Y-%m-%d}
- 정본은 이 Vault의 Markdown + YAML. 모든 변경은 Git commit. AI 커밋은 `[myelin:<skill>]` 접두사.
- Frontmatter v2 필수: id · type · created (그 외 status/origin/confidence/classification/share/source/reviewed/tags). 스키마: `90_System/`의 템플릿을 따른다.

## Fail-closed — AI 쓰기 허용 경로 (그 외 경로는 Guard가 차단한다)
{allow}
- 그 외(특히 `10_Domains/`, `40_IP/`, `90_System/`, `myelin.yaml`)는 **사람 승인 영역**. 변경이 필요하면 `_patches/`에 제안 파일을 만든다.
- AI가 만든 노트는 `origin: claude`, `status: draft`로 `00_Inbox/ai-drafts/`에만 생성한다. verified 승격은 사람이 Hub Review Gate에서만 한다.

## Level {level} — {LEVEL_NAMES[level]}
- 사용 가능 Skill: {skills}
- 0 read-only | 1 drafts | 2 link-patch | 3 scheduled review

## Domains (3+1)
{dom_lines}
- 허용 note type: {", ".join(types)}
- Domain 추가는 `myelin add-domain <ID>` 로만 (Pack = 데이터).

## 보안등급 · LLM 라우팅
- classification: public | internal | confidential. `confidential` 노트와 `40_IP/`는 외부 LLM에 올리지 않는다.
{routes}
- share: true 는 Commons 공개 후보 표시일 뿐이며, 공개는 사람이 Hub에서 한다.

## 용어
- `90_System/taxonomy.md` 의 대표 용어로 정규화한다 (/distill).

## Packs
{pack_lines}
"""
    return generated + "\n" + _personal_block(previous) + "\n"
