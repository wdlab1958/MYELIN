"""Level-gated Skill exposure and AI write scopes (정본 §3 Phase-gated Autonomy, §7.1 table).

| Skill      | min Level | write scope            |
|------------|-----------|------------------------|
| /ingest    | 1         | 00_Inbox/ai-drafts     |
| /distill   | 1         | 00_Inbox/ai-drafts     |
| /interview | 1         | 00_Inbox/ai-drafts     |
| /review    | 1         | 50_Journal             |
| /link      | 2         | _patches               |
| /compose   | 2         | 80_Outputs/drafts      |
| /ip-scan   | 3         | 40_IP/candidates       |

The Guard (`plugin/hooks/guard_write.py`, stdlib only) carries a copy of LEVEL_ALLOW;
`tests/plugin/test_guard_sync.py` asserts both copies are identical (ADR-0005).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from myelin_core.vault import AI_DRAFTS, IP_CANDIDATES, JOURNAL, OUTPUT_DRAFTS, PATCHES


@dataclass(frozen=True)
class Skill:
    name: str
    min_level: int
    write_scope: str
    summary: str


SKILLS: tuple[Skill, ...] = (
    Skill("ingest", 1, AI_DRAFTS, "파일·URL·PDF → literature 노트 초안 (출처·핵심 주장·인용 위치)"),
    Skill(
        "distill", 1, AI_DRAFTS, "Inbox 노트 → 원자 노트 분해, frontmatter, 중복 검사, 용어 정규화"
    ),
    Skill("interview", 1, AI_DRAFTS, "Pack 질문 은행 기반 암묵지 추출 인터뷰 → lesson 초안"),
    Skill("review", 1, JOURNAL, "주간 품질 보고서 (doctor + 지표)"),
    Skill("link", 2, PATCHES, "링크 후보 + 근거, MOC 갱신 patch 제안"),
    Skill("compose", 2, OUTPUT_DRAFTS, "목적·독자 기반 산출물 초안 (특허·제안서·설계서·보고서)"),
    Skill(
        "ip-scan",
        3,
        IP_CANDIDATES,
        "Cross-domain verified 노트에서 특허 후보 추출 (로컬 LLM 라우팅)",
    ),
)

# Level → directories (relative, posix) the AI may write to. Cumulative.
LEVEL_ALLOW: dict[int, tuple[str, ...]] = {
    0: (),
    1: (AI_DRAFTS, JOURNAL),
    2: (AI_DRAFTS, JOURNAL, PATCHES, OUTPUT_DRAFTS),
    3: (AI_DRAFTS, JOURNAL, PATCHES, OUTPUT_DRAFTS, IP_CANDIDATES),
}

LEVEL_NAMES = {0: "read-only", 1: "drafts", 2: "link-patch", 3: "scheduled review"}

# ADR-0011 기밀 라우팅: a process/session is LOCAL iff the operator exported MYELIN_LLM=local.
# The Guard (`plugin/hooks/guard_common.py`) carries a copy of these two constants.
LLM_ENV = "MYELIN_LLM"
LLM_LOCAL = "local"


def is_local_session() -> bool:
    """True only for the exact value `local`; unset/empty/other spellings are EXTERNAL."""
    return os.environ.get(LLM_ENV) == LLM_LOCAL


def available_skills(level: int) -> list[Skill]:
    return [s for s in SKILLS if s.min_level <= level]


def skill_table(level: int) -> list[dict[str, object]]:
    return [
        {
            "skill": f"/{s.name}",
            "min_level": s.min_level,
            "enabled": s.min_level <= level,
            "write_scope": s.write_scope,
            "summary": s.summary,
        }
        for s in SKILLS
    ]


def allowed_dirs(level: int) -> tuple[str, ...]:
    if level not in LEVEL_ALLOW:
        raise ValueError(f"level must be 0..3, got {level}")
    return LEVEL_ALLOW[level]
