"""T9 — stats KPIs (정본 §11.1)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from myelin_core.stats import TARGETS, compute_stats
from myelin_core.vault import Vault


def test_stats_on_basic(fixtures_dir: Path) -> None:
    v = Vault.open(fixtures_dir / "vaults/basic")
    st = compute_stats(v, date(2026, 10, 18))
    assert st.notes == 35 and st.parse_errors == 0
    assert st.inbox_dwell_days == 2.0  # 7 inbox notes created 10-15..10-17
    assert st.verified_per_week == 1  # 2026-W41 weekly review reviewed 10-12
    assert st.ai_promotion_rate is not None and 0.4 <= st.ai_promotion_rate <= 0.7
    assert 0 <= st.orphan_ratio <= 1 and st.cross_domain_ratio > 0
    assert st.outputs_per_month == 1
    assert st.by_status["verified"] == 19 and st.by_origin["claude"] == 7
    assert st.by_domain == {"D1": 11, "D2": 10, "D3": 11, "D4": 7}
    rows = st.kpi_rows()
    assert [r[0] for r in rows] == list(TARGETS)
    assert st.to_dict()["as_of"] == "2026-10-18"


def test_stats_empty_vault(tmp_path: Path) -> None:
    (tmp_path / "myelin.yaml").write_text(
        "owner: {name: x}\npacks: [myelin.core]\ndomains: {primary: D1}\n", encoding="utf-8"
    )
    st = compute_stats(Vault.open(tmp_path), date(2026, 10, 18))
    assert st.notes == 0 and st.inbox_dwell_days is None and st.ai_promotion_rate is None
    assert st.orphan_ratio == 0.0 and "-" in [r[1] for r in st.kpi_rows()]


def test_stats_counts_parse_errors(fixtures_dir: Path) -> None:
    v = Vault.open(fixtures_dir / "vaults/seeded-violations")
    st = compute_stats(v, date(2026, 10, 18))
    assert st.parse_errors == 2 and st.notes == 19


def test_kpi_status_judgement() -> None:
    from myelin_core.stats import TARGETS, kpi_status

    assert kpi_status("ai_promotion_rate", None) is None
    assert kpi_status("ai_promotion_rate", 0.5) == "ok"
    assert kpi_status("ai_promotion_rate", 0.9) == "alert"  # too high = weak gate
    assert kpi_status("ai_promotion_rate", 0.1) == "alert"
    assert (
        kpi_status("inbox_dwell_days", 7) == "ok" and kpi_status("inbox_dwell_days", 8) == "alert"
    )
    assert kpi_status("orphan_ratio", 0.2) == "alert" and kpi_status("verified_per_week", 5) == "ok"
    assert all(kpi_status(k, 0) in ("ok", "alert") for k in TARGETS)
