"""opt-in 익명 지표 (명세 §11.2, ADR-0009).

- `myelin.yaml` `metrics.opt_in: true` 일 때만 만든다.
- 파일로만 내보낸다. **네트워크로 보내지 않는다** — 제출은 사람이 직접 한다.
- 담지 않는 것: 이름·이메일·경로·제목·노트 id·Domain id·태그·날짜(주 단위 제외)·
  개인/reference Pack 이름.
- 숫자는 구간으로 뭉갠다 — 작은 조직에서 정확한 수가 사람을 특정하지 않게.
"""

from __future__ import annotations

import itertools
from datetime import date
from pathlib import Path
from typing import Any

from myelin_core.config import load_config
from myelin_core.errors import Issue, MyelinError
from myelin_core.lock import load_lock
from myelin_core.stats import compute_stats

SCHEMA = 1
# reference Pack 이름은 개인을 가리킬 수 있어(예: brian.*) 빼고, core·org 만 남긴다
PUBLIC_PACK_KINDS = ("core", "org")
_BUCKETS = (0, 1, 5, 10, 25, 50, 100, 250, 500, 1000)


class MetricsError(MyelinError):
    """지표를 만들 수 없음."""


def bucket(n: int) -> str:
    """정확한 수 대신 구간: 0 · 1-4 · 5-9 · … · 1000+."""
    if n <= 0:
        return "0"
    for lo, hi in itertools.pairwise(_BUCKETS[1:]):
        if lo <= n < hi:
            return f"{lo}-{hi - 1}"
    return f"{_BUCKETS[-1]}+"


def _ratio(v: float | None) -> float | None:
    return None if v is None else round(v, 1)


def anonymous_metrics(vault: Path, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    cfg = load_config(vault)
    if not cfg.metrics.opt_in:
        raise MetricsError(
            "지표 수집에 동의하지 않았습니다",
            [Issue("metrics.opt_in", "myelin.yaml 에서 true 로 바꿔야 합니다", "not_opted_in")],
        )
    s = compute_stats(vault, today)
    lock = load_lock(vault)
    iso = today.isocalendar()
    packs = sorted(p.name for p in lock.packs if p.kind.value in PUBLIC_PACK_KINDS)
    return {
        "schema": SCHEMA,
        "week": f"{iso.year}-W{iso.week:02d}",
        "level": cfg.level,
        "packs": packs,
        "domains": len(cfg.domains.all()),
        "notes": bucket(s.notes),
        "verified_notes": bucket(s.verified_notes),
        "verified_last_7d": bucket(s.verified_last_7d),
        "ai_drafts_pending": bucket(s.ai_drafts),
        "ai_promotion_rate": _ratio(s.ai_promotion_rate),
        "orphan_ratio": _ratio(s.orphan_ratio),
        "cross_domain_ratio": _ratio(s.cross_domain_ratio),
        "inbox_items": bucket(s.inbox_items),
        "commons_enabled": cfg.commons.enabled,
        "mcp_write_drafts": cfg.mcp.write_drafts,
    }
