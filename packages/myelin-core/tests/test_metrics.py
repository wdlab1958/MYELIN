"""P7-T5 — opt-in anonymous metrics: events, payload anonymity, commons write, aggregation."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from myelin_core.commons import init_commons
from myelin_core.metrics import (
    ALLOWED_KEYS,
    aggregate,
    events,
    onboarding_minutes,
    org_metrics,
    payload_is_anonymous,
    record_event,
    write_metrics_to_commons,
)
from myelin_core.vault import Vault


@pytest.fixture
def vault(fixtures_dir: Path, tmp_path: Path) -> Vault:
    dst = tmp_path / "vault"
    shutil.copytree(fixtures_dir / "vaults/basic", dst)
    return Vault.open(dst)


def test_events_and_onboarding_minutes(vault: Vault) -> None:
    assert events(vault.root) == [] and onboarding_minutes(vault.root) is None
    record_event(vault.root, "onboard_start", via="test")
    assert onboarding_minutes(vault.root) is None
    p = vault.root / ".myelin/metrics.jsonl"
    p.write_text(
        json.dumps({"ts": 1000.0, "event": "onboard_start"})
        + "\n"
        + "garbage\n"
        + json.dumps({"ts": 1000.0 + 12 * 60, "event": "first_promote"})
        + "\n",
        encoding="utf-8",
    )
    assert onboarding_minutes(vault.root) == 12.0
    assert [e["event"] for e in events(vault.root)] == ["onboard_start", "first_promote"]


def test_payload_is_anonymous(vault: Vault) -> None:
    payload = org_metrics(vault, date(2026, 10, 18))
    assert set(payload) == ALLOWED_KEYS
    assert payload_is_anonymous(payload, vault) == []
    assert payload["owner"] != "brian@example.org" and len(payload["owner"]) == 12
    assert payload["verified_7d"] == 1 and payload["active"] is True and payload["notes"] == 35
    leaked = {**payload, "title": "WCET 예산은 측정값의 1.5배로 잡는다"}
    problems = payload_is_anonymous(leaked, vault)
    assert any("unexpected key" in p for p in problems) and any("note title" in p for p in problems)
    assert any(
        "identifying" in p
        for p in payload_is_anonymous({**payload, "owner": "brian@example.org"}, vault)
    )
    assert any("nested" in p for p in payload_is_anonymous({**payload, "notes": {"a": 1}}))


def test_write_requires_opt_in_and_aggregates(vault: Vault, tmp_path: Path) -> None:
    commons = tmp_path / "commons"
    init_commons(commons, git=False)
    with pytest.raises(PermissionError, match="opt-in"):
        write_metrics_to_commons(vault, commons, date(2026, 10, 18))
    cfg = vault.config.model_copy(
        update={"commons": vault.config.commons.model_copy(update={"metrics_opt_in": True})}
    )
    vault.config = cfg
    record_event(vault.root, "onboard_start")
    record_event(vault.root, "first_promote")
    record_event(vault.root, "publish")
    dest = write_metrics_to_commons(vault, commons, date(2026, 10, 18))
    assert dest.name == "2026-W42.json" and dest.parent.parent.name == "metrics"
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data["published"] == 1 and data["onboarding_minutes"] is not None
    # a second (fake) owner
    other = commons / "metrics" / "abcdef012345" / "2026-W42.json"
    other.parent.mkdir(parents=True)
    other.write_text(
        json.dumps({**data, "owner": "abcdef012345", "active": False, "onboarding_minutes": 20.0}),
        encoding="utf-8",
    )
    agg = aggregate(commons)
    w = agg["2026-W42"]
    assert (
        w["users"] == 2
        and w["active_users"] == 1
        and w["active_ratio"] == 0.5
        and w["published"] == 2
    )
    assert w["onboarding_within_15"] == 1
