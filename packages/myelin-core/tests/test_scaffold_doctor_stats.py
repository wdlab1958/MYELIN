from datetime import date
from pathlib import Path

import pytest

from myelin_core.config import parse_config
from myelin_core.doctor import run_doctor
from myelin_core.errors import MyelinError
from myelin_core.loader import discover_packs, resolve
from myelin_core.scaffold import (
    MARK_START,
    Plan,
    ScaffoldError,
    apply_plan,
    plan_add_domain,
    plan_init,
)
from myelin_core.stats import compute_stats
from myelin_core.yamlio import load_yaml

ROOT = Path(__file__).resolve().parents[3]
FIX = ROOT / "tests" / "fixtures" / "vaults"
TODAY = date(2026, 10, 18)


@pytest.fixture(scope="module")
def packs() -> list:  # type: ignore[type-arg]
    return resolve(["brian.physical-ai", "org.security-consulting"], discover_packs(ROOT / "packs"))


def make_cfg(primary: str = "AI-ML-AX", **domains: object) -> object:
    return parse_config(
        {
            "owner": {"name": "t"},
            "packs": ["myelin.core", "brian.physical-ai", "org.security-consulting"],
            "domains": {"primary": primary, **domains},
        }
    )


# ── scaffold ─────────────────────────────────────────────────────────────
def test_plan_init_contents(packs: list) -> None:  # type: ignore[type-arg]
    plan = plan_init(make_cfg(research="SEC-CONSULT"), packs, TODAY)  # type: ignore[arg-type]
    f = plan.files
    assert "10_Domains/AI-ML-AX/_MOC.md" in f and "10_Domains/SEC-CONSULT/_MOC.md" in f
    assert "10_Domains/EMBEDDED-SW/_MOC.md" not in f
    assert "90_System/templates/evergreen.md" in f
    assert "90_System/templates/org.security-consulting/finding-lesson.md" in f
    assert "| WCET |" not in f["90_System/taxonomy.md"]  # 선택하지 않은 Domain 용어 제외
    assert "| RAG |" in f["90_System/taxonomy.md"] and "## 공통" in f["90_System/taxonomy.md"]
    assert "missed-finding" in f["90_System/interviews.md"]
    assert MARK_START in f["CLAUDE.md"]


def test_plan_init_unknown_domain(packs: list) -> None:  # type: ignore[type-arg]
    with pytest.raises(ScaffoldError) as info:
        plan_init(make_cfg(primary="NOPE"), packs, TODAY)  # type: ignore[arg-type]
    assert info.value.issues[0].code == "unknown_domain"


def test_apply_plan_is_all_or_nothing(tmp_path: Path) -> None:
    (tmp_path / "exists.md").write_text("mine", encoding="utf-8")
    plan = Plan(files={"new.md": "x", "exists.md": "theirs"}, updates={"no/dir/x.md": "y"})
    with pytest.raises(MyelinError) as info:
        apply_plan(tmp_path, plan)
    assert {i.code for i in info.value.issues} == {"exists", "missing_dir"}
    assert not (tmp_path / "new.md").exists()
    assert (tmp_path / "exists.md").read_text(encoding="utf-8") == "mine"


def test_plan_add_domain_without_markers_leaves_claude_md(tmp_path: Path, packs: list) -> None:  # type: ignore[type-arg]
    cfg = make_cfg()
    apply_plan(tmp_path, plan_init(cfg, packs, TODAY))  # type: ignore[arg-type]
    (tmp_path / "CLAUDE.md").write_text("내가 다시 쓴 규칙\n", encoding="utf-8")
    (tmp_path / "90_System" / "interviews.md").unlink()
    new_cfg = make_cfg(extra=["SEC-CONSULT"])
    plan = plan_add_domain(tmp_path, new_cfg, "x", packs, set(), "SEC-CONSULT", TODAY)  # type: ignore[arg-type]
    assert "CLAUDE.md" not in plan.updates
    assert plan.updates["90_System/interviews.md"].startswith("\n\n## SEC-CONSULT")
    assert "90_System/templates/org.security-consulting/finding-lesson.md" in plan.files


# ── doctor ───────────────────────────────────────────────────────────────
def test_doctor_violations_exact() -> None:
    expected_doc = load_yaml(
        (FIX / "violations.expected.yaml").read_text(encoding="utf-8"), "e", MyelinError
    )
    expected = {(e["rule"], e["path"]) for e in expected_doc["findings"]}
    findings = run_doctor(FIX / "violations", today=TODAY, check_location=False)
    assert {(f.rule, f.path) for f in findings} == expected
    assert all(str(f).startswith(f"[{f.severity}]") for f in findings)


def test_doctor_golden_clean_but_location_flags_source_tree() -> None:
    assert run_doctor(FIX / "golden" / "brian", today=TODAY, check_location=False) == []
    located = run_doctor(FIX / "golden" / "brian", today=TODAY)
    assert [(f.rule, f.severity) for f in located] == [("location", "error")]


def test_doctor_config_problems(tmp_path: Path, packs: list) -> None:  # type: ignore[type-arg]
    assert [f.rule for f in run_doctor(tmp_path, check_location=False)] == ["config"]
    apply_plan(tmp_path, plan_init(make_cfg(), packs, TODAY))  # type: ignore[arg-type]
    cfg_path = tmp_path / "myelin.yaml"
    cfg_path.write_text(
        cfg_path.read_text(encoding="utf-8").replace("extra: []", "extra: [GHOST]"),
        encoding="utf-8",
    )
    findings = run_doctor(tmp_path, today=TODAY, check_location=False)
    assert [(f.rule, f.path) for f in findings] == [("config", "myelin.yaml.domains.extra")]


def test_doctor_reports_multiple_schema_issues(tmp_path: Path, packs: list) -> None:  # type: ignore[type-arg]
    apply_plan(tmp_path, plan_init(make_cfg(), packs, TODAY))  # type: ignore[arg-type]
    (tmp_path / "30_Resources" / "bad.md").write_text("---\ntype: x\n---\n", encoding="utf-8")
    (finding,) = run_doctor(tmp_path, today=TODAY, check_location=False)
    assert finding.rule == "schema" and "(+" in finding.msg


# ── stats ────────────────────────────────────────────────────────────────
def test_stats_on_violations() -> None:
    s = compute_stats(FIX / "violations", TODAY)
    assert s.parse_errors == 1
    assert s.inbox_items == 2 and s.inbox_avg_age_days == 23.5
    assert s.ai_drafts == 1 and s.ai_promotion_rate == 0.0
    assert 0 < s.orphan_ratio < 0.2
    assert s.by_type["moc"] == 4
    assert s.as_dict()["notes"] == s.notes


def test_stats_empty_vault(tmp_path: Path) -> None:
    s = compute_stats(tmp_path, TODAY)
    assert s.notes == 0 and s.ai_promotion_rate is None and s.orphan_ratio == 0.0
