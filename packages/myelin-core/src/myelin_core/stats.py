"""`myelin stats` — personal KPIs (정본 §11.1) computed from the Vault.

| KPI | definition | 3-month target |
|---|---|---|
| inbox_dwell_days      | mean age (days) of notes still in 00_Inbox         | ≤ 7 |
| verified_per_week     | verified, reviewed within the last 7 days  | ≥ 5 member / ≥ 10 Brian |
| ai_promotion_rate     | verified / notes with origin claude|mixed  | 0.4-0.7 (high = weak) |
| orphan_ratio          | notes with zero links / notes                      | ≤ 0.10 |
| cross_domain_ratio    | notes with ≥ 2 domains / notes                     | ≥ 0.15 |
| outputs_per_month     | 80_Outputs notes created in the last 30 days       | ≥ 2 |
| totals                | notes by status / origin / type / domain           | — |
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from myelin_core.note import Note
from myelin_core.schema.frontmatter import Origin, Status
from myelin_core.vault import INBOX, OUTPUTS, Vault

TARGETS: dict[str, str] = {
    "inbox_dwell_days": "≤ 7",
    "verified_per_week": "≥ 5 (구성원) / ≥ 10 (Brian)",
    "ai_promotion_rate": "0.40 ~ 0.70",
    "orphan_ratio": "≤ 0.10",
    "cross_domain_ratio": "≥ 0.15",
    "outputs_per_month": "≥ 2",
}


@dataclass
class Stats:
    as_of: str
    notes: int
    inbox_dwell_days: float | None
    verified_per_week: int
    ai_promotion_rate: float | None
    orphan_ratio: float
    cross_domain_ratio: float
    outputs_per_month: int
    by_status: dict[str, int] = field(default_factory=dict)
    by_origin: dict[str, int] = field(default_factory=dict)
    by_type: dict[str, int] = field(default_factory=dict)
    by_domain: dict[str, int] = field(default_factory=dict)
    parse_errors: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def kpi_rows(self) -> list[tuple[str, str, str]]:
        def fmt(v: float | int | None) -> str:
            return "-" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v))

        return [(k, fmt(getattr(self, k)), TARGETS[k]) for k in TARGETS]


def compute_stats(
    vault: Vault, today: date, notes: list[Note] | None = None, parse_errors: int = 0
) -> Stats:
    if notes is None:
        notes, errs = vault.read_all()
        parse_errors = len(errs)
    total = len(notes)
    rels = {id(n): vault.rel(n.path) for n in notes if n.path}
    inbox = [n for n in notes if rels[id(n)].startswith(INBOX + "/")]
    dwell = (
        (sum((today - n.frontmatter.created).days for n in inbox) / len(inbox)) if inbox else None
    )
    week_ago = today - timedelta(days=7)
    verified_week = sum(
        1
        for n in notes
        if n.frontmatter.status is Status.VERIFIED
        and n.frontmatter.reviewed
        and week_ago < n.frontmatter.reviewed <= today
    )
    ai = [n for n in notes if n.frontmatter.origin in (Origin.CLAUDE, Origin.MIXED)]
    promo = (
        (sum(1 for n in ai if n.frontmatter.status is Status.VERIFIED) / len(ai)) if ai else None
    )
    inbound: Counter[str] = Counter()
    stems = {n.path.stem for n in notes if n.path}
    for n in notes:
        for t in n.link_targets:
            if t in stems:
                inbound[t] += 1
    orphans = sum(1 for n in notes if n.path and not n.links and inbound[n.path.stem] == 0)
    cross = sum(1 for n in notes if len(n.frontmatter.domain) >= 2)
    month_ago = today - timedelta(days=30)
    outputs = sum(
        1
        for n in notes
        if rels[id(n)].startswith(OUTPUTS + "/") and month_ago < n.frontmatter.created <= today
    )
    by_domain: Counter[str] = Counter(d for n in notes for d in n.frontmatter.domain)
    return Stats(
        as_of=today.isoformat(),
        notes=total,
        inbox_dwell_days=round(dwell, 2) if dwell is not None else None,
        verified_per_week=verified_week,
        ai_promotion_rate=round(promo, 3) if promo is not None else None,
        orphan_ratio=round(orphans / total, 3) if total else 0.0,
        cross_domain_ratio=round(cross / total, 3) if total else 0.0,
        outputs_per_month=outputs,
        by_status=dict(sorted(Counter(n.frontmatter.status.value for n in notes).items())),
        by_origin=dict(sorted(Counter(n.frontmatter.origin.value for n in notes).items())),
        by_type=dict(sorted(Counter(n.frontmatter.type.value for n in notes).items())),
        by_domain=dict(sorted(by_domain.items())),
        parse_errors=parse_errors,
    )
