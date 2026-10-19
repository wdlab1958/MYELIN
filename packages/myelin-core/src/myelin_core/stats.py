"""`myelin stats` — personal KPIs (정본 §11.1 + ADR-0012 재사용 지표) computed from the Vault.

| KPI | definition | 3-month target |
|---|---|---|
| inbox_dwell_days      | mean age (days) of notes still in 00_Inbox         | ≤ 7 |
| verified_per_week     | verified, reviewed within the last 7 days  | ≥ 5 member / ≥ 10 Brian |
| ai_promotion_rate     | verified / notes with origin claude|mixed  | 0.4-0.7 (high = weak) |
| orphan_ratio          | notes with zero links / notes                      | ≤ 0.10 |
| cross_domain_ratio    | notes with ≥ 2 domains / notes                     | ≥ 0.15 |
| outputs_per_month     | 80_Outputs notes created in the last 30 days       | ≥ 2 |
| reuse_ratio           | verified notes with strength ≥ 2 / verified notes  | ≥ 0.30 (ADR-0012) |
| reuse_lag_days        | median days from source note → output that cites it | ≤ 30 (ADR-0012) |
| compose_sources_avg   | mean verified source notes per 80_Outputs note     | ≥ 3 (ADR-0012) |
| totals                | notes by status / origin / type / domain / strength | — |

Myelin strength (ADR-0012, "쓸수록 빨라지는 지식 신경망"): a note is myelinated by being
verified AND reused. `compute_reuse()` is the single definition shared by the full-scan path
(`compute_stats`) and the SQLite index (`VaultIndex.reuse` / `VaultIndex.stats`).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import PurePosixPath

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
    "reuse_ratio": "≥ 0.30",
    "reuse_lag_days": "≤ 30",
    "compose_sources_avg": "≥ 3",
}
# numeric form of TARGETS (lo, hi) for the Hub's 목표 이탈 judgement (§11.1 · §12)
BOUNDS: dict[str, tuple[float | None, float | None]] = {
    "inbox_dwell_days": (None, 7),
    "verified_per_week": (5, None),
    "ai_promotion_rate": (0.40, 0.70),
    "orphan_ratio": (None, 0.10),
    "cross_domain_ratio": (0.15, None),
    "outputs_per_month": (2, None),
    "reuse_ratio": (0.30, None),
    "reuse_lag_days": (None, 30),
    "compose_sources_avg": (3, None),
}


def kpi_status(kpi: str, value: float | int | None) -> str | None:
    """'ok' / 'alert' / None (no data). ai_promotion_rate alerts on both sides (high = weak)."""
    if value is None:
        return None
    lo, hi = BOUNDS[kpi]
    ok = (lo is None or value >= lo) and (hi is None or value <= hi)
    return "ok" if ok else "alert"


# ----------------------------------------------------------------------------- myelin strength
# Thresholds (ADR-0012). strength 0 = not verified · 1 = verified · 2 = reused · 3 = hub/cited.
STRENGTH_MAX = 3
REUSED_STRENGTH = 2  # "reused" = strength ≥ 2 (what reuse_ratio counts)
STRENGTH2_INBOUND = 2  # strength 2 when inbound ≥ 2 …
STRENGTH2_OUTPUT_USES = 1  # … or output_uses ≥ 1
STRENGTH3_COMMONS_CITED = 1  # strength 3 when commons_cited ≥ 1 …
STRENGTH3_INBOUND = 5  # … or (inbound ≥ 5 and output_uses ≥ 2)
STRENGTH3_OUTPUT_USES = 2

_WIKILINK_RE = re.compile(r"\[\[([^\[\]|#]+?)(?:#[^\[\]|]*)?(?:\|[^\[\]]*)?\]\]")
_NOTE_ID_RE = re.compile(r"\d{8}-\d{4}-[a-z0-9][a-z0-9-]*")


def strength_of(verified: bool, inbound: int, output_uses: int, commons_cited: int) -> int:
    """Derive myelin strength 0..3 from the reuse counters (thresholds above)."""
    if not verified:
        return 0
    if commons_cited >= STRENGTH3_COMMONS_CITED or (
        inbound >= STRENGTH3_INBOUND and output_uses >= STRENGTH3_OUTPUT_USES
    ):
        return 3
    if inbound >= STRENGTH2_INBOUND or output_uses >= STRENGTH2_OUTPUT_USES:
        return 2
    return 1


@dataclass(frozen=True)
class NoteRef:
    """The minimal view of a note that the reuse computation needs (full scan or index row)."""

    path: str  # Vault-relative, posix
    id: str
    title: str
    status: str
    created: str  # ISO date
    source: tuple[str, ...]
    targets: tuple[str, ...]  # body wikilink targets

    @classmethod
    def from_note(cls, vault: Vault, note: Note) -> NoteRef:
        assert note.path is not None
        fm = note.frontmatter
        return cls(
            path=vault.rel(note.path),
            id=fm.id,
            title=note.title,
            status=fm.status.value,
            created=fm.created.isoformat(),
            source=tuple(fm.source),
            targets=tuple(sorted(note.link_stems)),
        )

    @property
    def stem(self) -> str:
        return PurePosixPath(self.path).stem

    @property
    def is_output(self) -> bool:
        return self.path.startswith(OUTPUTS + "/")

    @property
    def is_verified(self) -> bool:
        return self.status == Status.VERIFIED.value


@dataclass(frozen=True)
class Reuse:
    inbound: int  # distinct notes whose body links to this note
    output_uses: int  # distinct 80_Outputs notes citing it (source: list or body link)
    commons_cited: int  # citations of its Commons copy by other vaults/notes (0 when unknown)
    strength: int  # 0..3, see strength_of()

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def source_refs(entries: Sequence[str]) -> list[str]:
    """Candidate note keys named by `source:` entries: wikilink targets, note ids, raw strings."""
    out: list[str] = []
    for s in entries:
        links = _WIKILINK_RE.findall(s)
        if links:
            out += [t.strip() for t in links]
            continue
        ids = _NOTE_ID_RE.findall(s)
        out += ids if ids else [s.strip()]
    return out


class _Resolver:
    """target (stem · title · id) → note path. Stems win over titles over ids on collision."""

    def __init__(self, refs: Sequence[NoteRef]) -> None:
        self._by: dict[str, str] = {}
        for key in ("id", "title", "stem"):
            for r in refs:
                self._by[getattr(r, key)] = r.path

    def __call__(self, target: str) -> str | None:
        return self._by.get(target)


def compute_reuse(
    refs: Sequence[NoteRef], commons_cited: Mapping[str, int] | None = None
) -> dict[str, Reuse]:
    """Per-note reuse counters + strength, keyed by Vault-relative path (ADR-0012)."""
    resolve = _Resolver(refs)
    inbound: dict[str, set[str]] = {r.path: set() for r in refs}
    output_uses: dict[str, set[str]] = {r.path: set() for r in refs}
    for r in refs:
        for t in r.targets:
            p = resolve(t)
            if p is not None and p != r.path:
                inbound[p].add(r.path)
        if r.is_output:
            for t in (*r.targets, *source_refs(r.source)):
                p = resolve(t)
                if p is not None and p != r.path:
                    output_uses[p].add(r.path)
    cited = commons_cited or {}
    out: dict[str, Reuse] = {}
    for r in refs:
        i, o, c = len(inbound[r.path]), len(output_uses[r.path]), int(cited.get(r.id, 0))
        out[r.path] = Reuse(i, o, c, strength_of(r.is_verified, i, o, c))
    return out


def output_sources(refs: Sequence[NoteRef]) -> dict[str, set[str]]:
    """80_Outputs note path → paths of the notes it draws on (body links + source: entries)."""
    resolve = _Resolver(refs)
    out: dict[str, set[str]] = {}
    for r in refs:
        if not r.is_output:
            continue
        srcs = out.setdefault(r.path, set())
        for t in (*r.targets, *source_refs(r.source)):
            p = resolve(t)
            if p is not None and p != r.path:
                srcs.add(p)
    return out


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


@dataclass(frozen=True)
class ReuseMetrics:
    reuse_ratio: float | None
    reuse_lag_days: float | None
    compose_sources_avg: float | None
    by_strength: dict[str, int]


def reuse_metrics(refs: Sequence[NoteRef], reuse: Mapping[str, Reuse]) -> ReuseMetrics:
    """The three reuse KPIs (ADR-0012) + strength histogram from `compute_reuse()` output."""
    by_path = {r.path: r for r in refs}
    verified = [r for r in refs if r.is_verified]
    reused = sum(1 for r in verified if reuse[r.path].strength >= REUSED_STRENGTH)
    ratio = round(reused / len(verified), 3) if verified else None
    lags: list[float] = []
    per_output: list[int] = []
    for out_path, srcs in output_sources(refs).items():
        created = date.fromisoformat(by_path[out_path].created)
        per_output.append(sum(1 for p in srcs if by_path[p].is_verified))
        lags += [float((created - date.fromisoformat(by_path[p].created)).days) for p in srcs]
    med = _median(lags)
    avg = round(sum(per_output) / len(per_output), 2) if per_output else None
    hist = Counter(str(reuse[r.path].strength) for r in refs)
    return ReuseMetrics(
        reuse_ratio=ratio,
        reuse_lag_days=round(med, 1) if med is not None else None,
        compose_sources_avg=avg,
        by_strength={str(s): hist.get(str(s), 0) for s in range(STRENGTH_MAX + 1)},
    )


# ----------------------------------------------------------------------------- stats
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
    # ADR-0012 reuse KPIs (None = no data)
    reuse_ratio: float | None = None
    reuse_lag_days: float | None = None
    compose_sources_avg: float | None = None
    by_strength: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def kpi_rows(self) -> list[tuple[str, str, str]]:
        def fmt(v: float | int | None) -> str:
            return "-" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v))

        return [(k, fmt(getattr(self, k)), TARGETS[k]) for k in TARGETS]


def compute_stats(
    vault: Vault,
    today: date,
    notes: list[Note] | None = None,
    parse_errors: int = 0,
    commons_cited: Mapping[str, int] | None = None,
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
        for t in n.link_stems:
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
    refs = [NoteRef.from_note(vault, n) for n in notes if n.path]
    rm = reuse_metrics(refs, compute_reuse(refs, commons_cited))
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
        reuse_ratio=rm.reuse_ratio,
        reuse_lag_days=rm.reuse_lag_days,
        compose_sources_avg=rm.compose_sources_avg,
        by_strength=rm.by_strength,
    )


__all__: list[str] = [
    "BOUNDS",
    "REUSED_STRENGTH",
    "STRENGTH_MAX",
    "TARGETS",
    "NoteRef",
    "Reuse",
    "ReuseMetrics",
    "Stats",
    "compute_reuse",
    "compute_stats",
    "kpi_status",
    "output_sources",
    "reuse_metrics",
    "source_refs",
    "strength_of",
]
