"""T5/T7-T9 — Pack loader: real packs load & resolve; dependency/cycle/version/duplicate errors."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from myelin_core import PackError, discover_packs, load_pack, resolve_packs
from myelin_core.packs.loader import LoadedPack
from myelin_core.schema import PackKind

REAL_PACKS = [
    "myelin.core",
    "brian.physical-ai",
    "org.security-consulting",
    "org.incident-response",
]


@pytest.mark.parametrize("name", REAL_PACKS)
def test_real_pack_loads(packs_dir: Path, name: str) -> None:
    lp = load_pack(packs_dir / name)
    assert lp.name == name
    assert lp.pack.semver.major == 1


def test_core_pack_contents(packs_dir: Path) -> None:
    lp = load_pack(packs_dir / "myelin.core")
    assert lp.pack.kind is PackKind.CORE
    names = {p.stem for p in lp.template_files["templates"]}
    # one template per Frontmatter note type (정본 §6.2)
    assert names == {
        "fleeting",
        "literature",
        "evergreen",
        "moc",
        "adr",
        "experiment",
        "lesson",
        "checklist",
        "idea-ip",
    }
    assert "taxonomy.yaml" in lp.taxonomies
    assert any(t.term == "Fail-closed" for t in lp.taxonomies["taxonomy.yaml"].terms)


def test_brian_reference_pack(packs_dir: Path) -> None:
    lp = load_pack(packs_dir / "brian.physical-ai")
    assert lp.pack.kind is PackKind.REFERENCE
    assert lp.pack.domain_ids == ["D1", "D2", "D3", "D4"]
    assert {d.accent for d in lp.pack.domains} == {"violet", "cyan", "lime", "magenta"}
    for d in lp.pack.domains:
        assert len(d.sub_mocs) == 6, d.id  # 정본 §5.5 Sub-MOC 6개씩
        assert lp.interview_bank_for(d.id) is not None
        assert lp.taxonomy_for(d.id) is not None
    bank = lp.interview_bank_for("D3")
    assert bank is not None and all(q.domain is not None for q in bank.questions)
    assert {q.domain for q in bank.questions} == {"D1", "D2", "D3", "D4"}
    assert lp.template_files["templates/robotics"] and lp.template_files["templates/cad"]
    assert lp.taxonomy_for("NOPE") is None and lp.interview_bank_for("NOPE") is None


def test_a3_org_pack(packs_dir: Path) -> None:
    lp = load_pack(packs_dir / "org.security-consulting")
    assert lp.pack.kind is PackKind.ORG
    d = lp.pack.domains[0]
    assert d.id == "SEC-CONSULT" and d.classification_default.value == "internal"
    assert d.compose_targets == ["진단 보고서 초안", "제안서 섹션", "교육자료"]
    assert len(lp.template_files["templates"]) == 2


def test_a3_incident_response_pack(packs_dir: Path) -> None:
    lp = load_pack(packs_dir / "org.incident-response")
    d = lp.pack.domains[0]
    assert d.id == "IR" and d.accent == "magenta" and len(d.sub_mocs) == 6
    assert {p.stem for p in lp.template_files["templates"]} == {"timeline", "ioc", "post-mortem"}
    assert lp.interview_bank_for("IR") is not None and lp.taxonomy_for("IR") is not None


def test_discover_and_resolve_real(packs_dir: Path) -> None:
    reg = discover_packs([packs_dir])
    assert set(reg) == set(REAL_PACKS)
    order = resolve_packs(["org.security-consulting", "brian.physical-ai"], reg)
    names = [lp.name for lp in order]
    assert names[0] == "myelin.core"  # dependency first
    assert set(names) == {"myelin.core", "org.security-consulting", "brian.physical-ai"}
    # requesting only core resolves to core alone; versions satisfied
    assert [lp.name for lp in resolve_packs(["myelin.core>=1.0"], reg)] == ["myelin.core"]


def test_discover_skips_missing_root_and_nonstrict(tmp_path: Path, packs_dir: Path) -> None:
    bad = tmp_path / "packs" / "x.bad"
    bad.mkdir(parents=True)
    (bad / "pack.yaml").write_text("pack: [", encoding="utf-8")
    with pytest.raises(PackError):
        discover_packs([tmp_path / "packs"])
    assert discover_packs([tmp_path / "packs", tmp_path / "nope"], strict=False) == {}
    reg = discover_packs([packs_dir, tmp_path / "packs"], strict=False)
    assert set(reg) == set(REAL_PACKS)


def test_discover_duplicate_pack_name(tmp_path: Path, packs_dir: Path) -> None:
    other = tmp_path / "packs" / "myelin.core"
    other.mkdir(parents=True)
    (other / "pack.yaml").write_text(
        "pack: myelin.core\nkind: core\nmaintainer: x\n", encoding="utf-8"
    )
    with pytest.raises(PackError, match="already loaded"):
        discover_packs([packs_dir, tmp_path / "packs"])


# ---------------------------------------------------------------- synthetic registry helpers


def _mk(
    tmp: Path, name: str, requires: list[str], version: str = "1.0.0", domain: str | None = None
) -> Path:
    d = tmp / name
    d.mkdir(parents=True, exist_ok=True)
    kind = "core" if name == "myelin.core" else "personal"
    lines = [f"pack: {name}", f"version: {version}", f"kind: {kind}", "maintainer: t"]
    if requires:
        lines.append("requires: [" + ", ".join(requires) + "]")
    if kind != "core":
        did = domain or name.split(".")[-1].upper().replace("_", "-")
        lines += ["domains:", f"  - id: {did}", f"    name: {did}"]
    (d / "pack.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d


def test_resolve_missing_pack(tmp_path: Path) -> None:
    _mk(tmp_path, "myelin.core", [])
    _mk(tmp_path, "me.a", ["myelin.core", "me.ghost"])
    reg = discover_packs([tmp_path])
    with pytest.raises(PackError, match=r"'me\.ghost' not found.*required by me\.a"):
        resolve_packs(["me.a"], reg)
    with pytest.raises(PackError, match=r"'me\.nope' not found"):
        resolve_packs(["me.nope"], reg)


def test_resolve_version_mismatch(tmp_path: Path) -> None:
    _mk(tmp_path, "myelin.core", [], version="0.9.0")
    _mk(tmp_path, "me.a", ["myelin.core>=1.0"])
    reg = discover_packs([tmp_path])
    with pytest.raises(
        PackError, match=r"me.a requires myelin.core>=1.0.0, but myelin.core is version 0.9.0"
    ):
        resolve_packs(["me.a"], reg)
    with pytest.raises(PackError, match="<request> requires"):
        resolve_packs(["myelin.core==1.0"], reg)


def test_resolve_cycle(tmp_path: Path) -> None:
    _mk(tmp_path, "myelin.core", [])
    _mk(tmp_path, "me.a", ["myelin.core", "me.b"])
    _mk(tmp_path, "me.b", ["myelin.core", "me.c"])
    _mk(tmp_path, "me.c", ["myelin.core", "me.a"])
    reg = discover_packs([tmp_path])
    with pytest.raises(PackError, match=r"circular requires: me\.a -> me\.b -> me\.c -> me\.a"):
        resolve_packs(["me.a"], reg)


def test_resolve_duplicate_domain_across_packs(tmp_path: Path) -> None:
    _mk(tmp_path, "myelin.core", [])
    _mk(tmp_path, "me.a", ["myelin.core"], domain="X")
    _mk(tmp_path, "me.b", ["myelin.core"], domain="X")
    reg = discover_packs([tmp_path])
    with pytest.raises(PackError, match=r"domain id 'X' is declared by both me\.a and me\.b"):
        resolve_packs(["me.a", "me.b"], reg)


def test_resolve_diamond_once(tmp_path: Path) -> None:
    _mk(tmp_path, "myelin.core", [])
    _mk(tmp_path, "me.a", ["myelin.core"])
    _mk(tmp_path, "me.b", ["myelin.core", "me.a"])
    _mk(tmp_path, "me.c", ["myelin.core", "me.a"])
    reg = discover_packs([tmp_path])
    order = [lp.name for lp in resolve_packs(["me.b", "me.c"], reg)]
    assert order == ["myelin.core", "me.a", "me.b", "me.c"]
    assert all(isinstance(lp, LoadedPack) for lp in reg.values())


def test_load_pack_dir_errors(tmp_path: Path) -> None:
    with pytest.raises(PackError, match="does not exist"):
        load_pack(tmp_path / "nope")
    (tmp_path / "me.x").mkdir()
    with pytest.raises(PackError, match=r"pack\.yaml not found"):
        load_pack(tmp_path / "me.x")
    (tmp_path / "me.x" / "pack.yaml").write_bytes(b"\xff\xfe\x00")
    with pytest.raises(PackError, match="not UTF-8"):
        load_pack(tmp_path / "me.x")
    (tmp_path / "me.x" / "pack.yaml").write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(PackError, match="top level must be a mapping"):
        load_pack(tmp_path / "me.x")


def test_side_file_errors(tmp_path: Path) -> None:
    d = _mk(tmp_path, "me.s", ["myelin.core"], domain="S")
    (d / "pack.yaml").write_text(
        (d / "pack.yaml").read_text(encoding="utf-8")
        + "    sub_mocs: [A]\n    taxonomy_seed: tax.yaml\n    interview_bank: iv.yaml\n"
        + "    templates: t\n",
        encoding="utf-8",
    )
    (d / "t").mkdir()
    (d / "t" / "x.md").write_text("---\n---\n", encoding="utf-8")
    (d / "tax.yaml").write_text("terms:\n  - term: ''\n", encoding="utf-8")
    with pytest.raises(PackError, match="Taxonomy schema violation"):
        load_pack(d)
    (d / "tax.yaml").write_text("terms: []\n", encoding="utf-8")
    (d / "iv.yaml").write_text(
        "questions:\n  - {id: q, prompt: p, domain: S, sub_moc: NOPE}\n", encoding="utf-8"
    )
    with pytest.raises(PackError, match=r"sub_moc 'NOPE' is not in S\.sub_mocs"):
        load_pack(d)
    (d / "iv.yaml").write_text(
        "questions:\n  - {id: q, prompt: p, domain: S, sub_moc: A}\n", encoding="utf-8"
    )
    lp = load_pack(d)
    assert lp.interview_bank_for("S") is not None
    # templates must be a directory
    shutil.rmtree(d / "t")
    (d / "t").write_text("not a dir", encoding="utf-8")
    with pytest.raises(PackError, match="must be a directory"):
        load_pack(d)
    # symlink escaping the pack root is rejected at load time
    (d / "t").unlink()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "a.md").write_text("x", encoding="utf-8")
    (d / "t").symlink_to(outside, target_is_directory=True)
    with pytest.raises(PackError, match="escapes the pack directory"):
        load_pack(d)
