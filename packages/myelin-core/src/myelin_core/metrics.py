"""opt-in 익명 지표 (명세 §11.2, ADR-0009).

- `myelin.yaml` `metrics.opt_in: true` 일 때만 만든다.
- 파일로만 내보낸다. **네트워크로 보내지 않는다** — 제출은 사람이 직접 한다.
- 담지 않는 것: 이름·이메일·경로·제목·노트 id·Domain id·태그·날짜(주 단위 제외)·
  개인/reference Pack 이름.
- 숫자는 구간으로 뭉갠다 — 작은 조직에서 정확한 수가 사람을 특정하지 않게.
"""

from __future__ import annotations

import itertools
import json
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


# ── 집계 (조직 운영자, 명세 §11.2) ───────────────────────────────────────
EXPECTED_KEYS = frozenset(
    {
        "schema", "week", "level", "packs", "domains", "notes", "verified_notes",
        "verified_last_7d", "ai_drafts_pending", "ai_promotion_rate", "orphan_ratio",
        "cross_domain_ratio", "inbox_items", "commons_enabled", "mcp_write_drafts",
    }
)  # fmt: skip
_BUCKET_RE = r"^(0|\d+-\d+|\d+\+)$"


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    v = sorted(values)
    mid = len(v) // 2
    return round(v[mid] if len(v) % 2 else (v[mid - 1] + v[mid]) / 2, 2)


def validate_submission(data: Any) -> list[str]:
    """제출 파일이 익명 형식 그대로인지 — 키가 하나라도 더 있거나 값 모양이 다르면 거부."""
    import re

    if not isinstance(data, dict):
        return ["JSON 객체가 아님"]
    problems = []
    keys = set(data)
    if keys != EXPECTED_KEYS:
        extra, missing = sorted(keys - EXPECTED_KEYS), sorted(EXPECTED_KEYS - keys)
        problems.append(f"키 불일치 (추가 {extra}, 누락 {missing})")
        return problems
    if data["schema"] != SCHEMA:
        problems.append(f"schema {data['schema']}")
    if not isinstance(data["week"], str) or not re.fullmatch(r"\d{4}-W\d{2}", data["week"]):
        problems.append("week 형식")
    for k in ("notes", "verified_notes", "verified_last_7d", "ai_drafts_pending", "inbox_items"):
        if not isinstance(data[k], str) or not re.fullmatch(_BUCKET_RE, data[k]):
            problems.append(f"{k} 는 구간 문자열이어야 함")
    packs = data["packs"]
    if not isinstance(packs, list) or not all(
        isinstance(p, str) and (p == "myelin.core" or p.startswith("org.")) for p in packs
    ):
        problems.append("packs 에는 core·org Pack 이름만")
    return problems


def aggregate(files: list[Path]) -> dict[str, Any]:
    """주 단위 집계. 익명 형식이 아닌 파일은 세지 않고 거부 목록에 남긴다."""
    weeks: dict[str, list[dict[str, Any]]] = {}
    rejected: list[dict[str, str]] = []
    for f in sorted(files):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            rejected.append({"file": f.name, "reason": f"읽기 실패: {type(exc).__name__}"})
            continue
        problems = validate_submission(data)
        if problems:
            rejected.append({"file": f.name, "reason": "; ".join(problems)})
            continue
        weeks.setdefault(data["week"], []).append(data)
    table: dict[str, Any] = {}
    for week, rows in sorted(weeks.items()):
        n = len(rows)
        active = sum(1 for r in rows if r["verified_last_7d"] != "0")
        rates = [r["ai_promotion_rate"] for r in rows if r["ai_promotion_rate"] is not None]
        packs: dict[str, int] = {}
        for r in rows:
            for p in r["packs"]:
                packs[p] = packs.get(p, 0) + 1
        table[week] = {
            "submissions": n,
            "active": active,
            "active_ratio": round(active / n, 2),
            "ai_promotion_rate_median": _median(rates),
            "cross_domain_median": _median([r["cross_domain_ratio"] for r in rows]),
            "orphan_median": _median([r["orphan_ratio"] for r in rows]),
            "commons_enabled": sum(1 for r in rows if r["commons_enabled"]),
            "packs": dict(sorted(packs.items())),
        }
    return {"weeks": table, "rejected": rejected}
