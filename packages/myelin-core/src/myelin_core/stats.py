"""`myelin stats` — 개인 지표 (명세 §11.1)."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from myelin_core.frontmatter import NoteType, Origin, Status
from myelin_core.vault import INBOX, build_graph, scan_vault


@dataclass
class VaultStats:
    notes: int = 0
    parse_errors: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_domain: dict[str, int] = field(default_factory=dict)
    inbox_items: int = 0
    inbox_avg_age_days: float = 0.0
    ai_drafts: int = 0
    ai_promotion_rate: float | None = None  # AI 기여 노트 중 verified 비율 (목표 40~70%)
    orphan_ratio: float = 0.0  # 목표 ≤ 10%
    cross_domain_ratio: float = 0.0  # verified 중 domain 2개 이상 (목표 ≥ 15%)
    verified_last_7d: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ratio(num: int, den: int) -> float:
    return round(num / den, 3) if den else 0.0


def compute_stats(vault: Path, today: date | None = None) -> VaultStats:
    today = today or date.today()
    scan = scan_vault(vault)
    graph = build_graph(scan)
    notes = scan.notes
    s = VaultStats(notes=len(notes), parse_errors=len(scan.errors))
    s.by_type = dict(sorted(Counter(n.frontmatter.type.value for n in notes).items()))
    s.by_status = dict(sorted(Counter(n.frontmatter.status.value for n in notes).items()))
    s.by_domain = dict(sorted(Counter(d for n in notes for d in n.frontmatter.domain).items()))

    inbox = [n for n in notes if (n.path or "").startswith(INBOX)]
    s.inbox_items = len(inbox)
    if inbox:
        s.inbox_avg_age_days = round(
            sum((today - n.frontmatter.created).days for n in inbox) / len(inbox), 1
        )

    ai = [n for n in notes if n.frontmatter.origin in (Origin.CLAUDE, Origin.MIXED)]
    s.ai_drafts = sum(1 for n in ai if n.frontmatter.status is not Status.VERIFIED)
    if ai:
        s.ai_promotion_rate = _ratio(
            sum(1 for n in ai if n.frontmatter.status is Status.VERIFIED), len(ai)
        )

    checkable = [
        n
        for n in notes
        if not (n.path or "").startswith(INBOX)
        and n.frontmatter.type not in (NoteType.MOC, NoteType.FLEETING)
    ]
    orphans = [
        n
        for n in checkable
        if not graph.outgoing[n.path or ""] and not graph.incoming[n.path or ""]
    ]
    s.orphan_ratio = _ratio(len(orphans), len(checkable))

    verified = [
        n
        for n in notes
        if n.frontmatter.status is Status.VERIFIED and n.frontmatter.type is not NoteType.MOC
    ]
    s.cross_domain_ratio = _ratio(
        sum(1 for n in verified if len(n.frontmatter.domain) >= 2), len(verified)
    )
    week_ago = today - timedelta(days=7)
    s.verified_last_7d = sum(1 for n in verified if n.frontmatter.created > week_ago)
    return s
