"""T8/T11 — doctor: 0 findings on the clean fixture; exactly the seeded findings otherwise."""

from __future__ import annotations

import json
from pathlib import Path

from myelin_core.doctor import RULES, known_domains, run_doctor
from myelin_core.vault import Vault


def test_basic_vault_is_clean(fixtures_dir: Path, packs_dir: Path) -> None:
    v = Vault.open(fixtures_dir / "vaults/basic")
    report = run_doctor(v, pack_roots=[packs_dir])
    assert report.notes_scanned == 35
    assert report.findings == [], report.findings  # 오탐 0
    assert report.ok


def test_seeded_vault_detected_100_percent(fixtures_dir: Path, packs_dir: Path) -> None:
    vault_dir = fixtures_dir / "vaults/seeded-violations"
    seeded = json.loads((vault_dir / ".seeded.json").read_text(encoding="utf-8"))
    expected = {(e["rule"], e["path"]) for e in seeded["expected"]}
    v = Vault.open(vault_dir)
    report = run_doctor(v, pack_roots=[packs_dir])
    actual = {(f.rule, f.path) for f in report.findings}
    assert actual == expected  # 100% detection AND 0 false positives
    assert {f.rule for f in report.findings} >= set(RULES)  # all 8 rules exercised
    assert not report.ok and len(report.errors) == 11 and len(report.warnings) == 2
    d = report.to_dict()
    assert d["errors"] == 11 and d["by_rule"]["duplicate-id"] == 2
    for f in report.findings:
        assert f.message and f.severity in ("error", "warning", "info")


def test_known_domains_falls_back_without_packs(fixtures_dir: Path, tmp_path: Path) -> None:
    v = Vault.open(fixtures_dir / "vaults/seeded-violations")
    assert known_domains(v, pack_roots=[tmp_path]) == {"D1", "D2"}
    assert {"D1", "D2", "D3", "D4"} <= known_domains(v)
    # explicit override
    report = run_doctor(v, declared_domains={"D1"}, pack_roots=[tmp_path])
    assert any(f.rule == "domain" and "D9" in f.message for f in report.findings)


def test_doctor_resolves_aliases_and_paths(tmp_path: Path) -> None:
    root = tmp_path / "v"
    (root / "10_Domains/D1").mkdir(parents=True)
    (root / "myelin.yaml").write_text(
        "owner: {name: x}\npacks: [myelin.core]\ndomains: {primary: D1}\n", encoding="utf-8"
    )
    fm = (
        "---\nid: 20261001-09{m}-{s}\ntype: evergreen\ndomain: [D1]\n"
        "created: 2026-10-01\n{extra}---\n"
    )
    (root / "10_Domains/D1/A.md").write_text(
        fm.format(m="01", s="a", extra="aliases: [Alpha]\n") + "# A\n", encoding="utf-8"
    )
    (root / "10_Domains/D1/B.md").write_text(
        fm.format(m="02", s="b", extra="") + "[[Alpha]] [[10_Domains/D1/A]]\n", encoding="utf-8"
    )
    report = run_doctor(Vault.open(root), pack_roots=[tmp_path])
    assert not [f for f in report.findings if f.rule in ("broken-link", "orphan")]
