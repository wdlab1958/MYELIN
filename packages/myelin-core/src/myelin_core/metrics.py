"""Opt-in anonymous metrics (정본 §11.2, ADR-0010).

- Local events: `<Vault>/.myelin/metrics.jsonl` — `onboard_start`, `first_promote`, `publish` …
  (timestamps only; never note content).
- `org_metrics(vault)` computes the §11.2 contribution of ONE vault as counts/booleans keyed by an
  anonymous owner hash. `payload_is_anonymous()` is the guard used by tests and by the publisher.
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from myelin_core.index import open_index
from myelin_core.vault import RUNTIME, Vault

EVENTS_FILE = f"{RUNTIME}/metrics.jsonl"
ALLOWED_KEYS = {
    "owner",
    "week",
    "active",
    "verified_7d",
    "onboarding_minutes",
    "published",
    "proposals",
    "notes",
    "level",
    "packs_count",
    "generated",
}


def record_event(vault_root: Path, event: str, **data: Any) -> None:
    p = Path(vault_root) / EVENTS_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": time.time(), "event": event, **data}, ensure_ascii=False) + "\n")


def events(vault_root: Path) -> list[dict[str, Any]]:
    p = Path(vault_root) / EVENTS_FILE
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def onboarding_minutes(vault_root: Path) -> float | None:
    """Minutes from onboard_start to first_promote (정본 §11.2 온보딩 시간 ≤ 15분)."""
    evs = events(vault_root)
    start = next((e["ts"] for e in evs if e.get("event") == "onboard_start"), None)
    first = next((e["ts"] for e in evs if e.get("event") == "first_promote"), None)
    if start is None or first is None or first < start:
        return None
    return round((float(first) - float(start)) / 60, 2)


def org_metrics(
    vault: Vault, today: date | None = None, owner: str | None = None
) -> dict[str, Any]:
    from myelin_core.commons import owner_hash  # local import: commons imports metrics indirectly

    today = today or date.today()
    with open_index(vault) as idx:
        st = idx.stats(today)
        rows = idx.query(
            status="verified", reviewed_from=(today - timedelta(days=7)).isoformat(), limit=1000
        )
    evs = events(vault.root)
    week = f"{today.isocalendar().year}-W{today.isocalendar().week:02d}"
    return {
        "owner": owner or owner_hash(vault),
        "week": week,
        "active": len(rows) >= 1,
        "verified_7d": len(rows),
        "onboarding_minutes": onboarding_minutes(vault.root),
        "published": sum(1 for e in evs if e.get("event") == "publish"),
        "proposals": sum(1 for e in evs if e.get("event") == "propose_pack"),
        "notes": st.notes,
        "level": vault.config.level,
        "packs_count": len(vault.config.pack_names),
        "generated": datetime.now().isoformat(timespec="seconds"),
    }


def payload_is_anonymous(payload: dict[str, Any], vault: Vault | None = None) -> list[str]:
    """Return violations: unexpected keys, non-scalar values, or vault-identifying strings."""
    problems = []
    for k, v in payload.items():
        if k not in ALLOWED_KEYS:
            problems.append(f"unexpected key {k!r}")
        if isinstance(v, dict | list):
            problems.append(f"{k}: nested value not allowed")
    text = json.dumps(payload, ensure_ascii=False)
    if vault is not None:
        o = vault.config.owner
        for ident in (o.email, o.name, str(vault.root)):
            if ident and ident in text:
                problems.append(f"identifying value present: {ident!r}")
        for p in vault.iter_note_paths():
            if p.stem in text:
                problems.append(f"note title present: {p.stem!r}")
                break
    return problems


def write_metrics_to_commons(vault: Vault, commons: Path, today: date | None = None) -> Path:
    """Only when myelin.yaml commons.metrics_opt_in is true; writes metrics/<owner>/<week>.json."""
    if not vault.config.commons.metrics_opt_in:
        raise PermissionError("metrics opt-in is off (myelin.yaml commons.metrics_opt_in: false)")
    payload = org_metrics(vault, today)
    problems = payload_is_anonymous(payload, vault)
    if problems:
        raise ValueError("metrics payload is not anonymous: " + "; ".join(problems))
    dest = Path(commons) / "metrics" / str(payload["owner"]) / f"{payload['week']}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dest


def aggregate(commons: Path) -> dict[str, Any]:
    """Sum metrics/*/<week>.json into the §11.2 org table."""
    files = sorted(Path(commons).glob("metrics/*/*.json"))
    payloads = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    weeks: dict[str, dict[str, Any]] = {}
    for p in payloads:
        w = weeks.setdefault(
            p["week"],
            {"owners": set(), "active": 0, "published": 0, "proposals": 0, "onboarding": []},
        )
        w["owners"].add(p["owner"])
        w["active"] += int(bool(p.get("active")))
        w["published"] += int(p.get("published") or 0)
        w["proposals"] += int(p.get("proposals") or 0)
        if p.get("onboarding_minutes") is not None:
            w["onboarding"].append(float(p["onboarding_minutes"]))
    out = {}
    for week, w in sorted(weeks.items()):
        n = len(w["owners"])
        out[week] = {
            "users": n,
            "active_users": w["active"],
            "active_ratio": round(w["active"] / n, 2) if n else 0.0,
            "published": w["published"],
            "pack_proposals": w["proposals"],
            "onboarding_minutes_median": (
                sorted(w["onboarding"])[len(w["onboarding"]) // 2] if w["onboarding"] else None
            ),
            "onboarding_within_15": sum(1 for m in w["onboarding"] if m <= 15),
        }
    return out
