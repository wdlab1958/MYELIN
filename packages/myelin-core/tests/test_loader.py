from pathlib import Path

import pytest

from myelin_core.errors import PackError
from myelin_core.loader import discover_packs, load_pack, resolve

ROOT = Path(__file__).resolve().parents[3]
INVALID = ROOT / "tests" / "fixtures" / "packs" / "invalid"


def write_pack(
    root: Path, name: str, *, requires: str = "", domains: str = "X", version: str = "1.0.0"
) -> Path:
    d = root / name
    d.mkdir(parents=True)
    kind = "core" if name == "myelin.core" else "personal"
    dom_yaml = "".join(
        f"\n  - id: {i}\n    name: {i}\n    sub_mocs: [a]" for i in domains.split(",") if i
    )
    req_yaml = "".join(f"\n  - {r}" for r in requires.split(";") if r)
    text = f"pack: {name}\nversion: {version}\nkind: {kind}\nmaintainer: t\n"
    if req_yaml:
        text += f"requires:{req_yaml}\n"
    if dom_yaml:
        text += f"domains:{dom_yaml}\n"
    (d / "pack.yaml").write_text(text, encoding="utf-8")
    return d


# ── 저장소의 실제 Pack ─────────────────────────────────────────────────────
def test_repository_packs_resolve() -> None:
    found = discover_packs(ROOT / "packs")
    order = resolve(["brian.physical-ai", "org.security-consulting"], found)
    assert [p.name for p in order] == [
        "myelin.core",
        "brian.physical-ai",
        "org.security-consulting",
    ]
    brian = found["brian.physical-ai"]
    assert [d.label for d in brian.domains] == ["D1", "D2", "D3", "D4"]
    assert set(brian.interview_banks["interviews.yaml"].domains) == {d.id for d in brian.domains}
    assert len(brian.taxonomies["taxonomy.yaml"].terms) >= 10


# ── 잘못된 Pack fixture: 모두 거부, 모든 Issue에 위치 ─────────────────────────
INVALID_CASES = sorted(p for p in INVALID.iterdir() if p.is_dir())


def test_there_are_at_least_ten_invalid_cases() -> None:
    assert len(INVALID_CASES) >= 10


@pytest.mark.parametrize("case", INVALID_CASES, ids=lambda p: p.name)
def test_invalid_pack_rejected_with_locations(case: Path) -> None:
    with pytest.raises(PackError) as info:
        load_pack(case)
    assert info.value.issues
    assert all(issue.loc and issue.loc != "<root>" for issue in info.value.issues)


def test_specific_invalid_locations() -> None:
    def locs(name: str) -> set[str]:
        with pytest.raises(PackError) as info:
            load_pack(INVALID / name)
        return {i.loc for i in info.value.issues}

    assert locs("01-missing-pack-name") == {"pack"}
    assert locs("04-bad-domain-id") == {"domains[0].id"}
    assert locs("08-missing-referenced-file") == {
        "domains[0].templates",
        "domains[0].interview_bank",
    }
    assert locs("10-yaml-syntax-error") == {"pack.yaml:8:13"}
    assert locs("11-path-escape") == {"domains[0].taxonomy_seed"}
    assert locs("12-interview-missing-domain") == {"domains[0].interview_bank"}


# ── 로더 경계 사례 ──────────────────────────────────────────────────────────
def test_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(PackError) as info:
        load_pack(tmp_path)
    assert info.value.issues[0].code == "missing_file"


def test_manifest_not_mapping(tmp_path: Path) -> None:
    (tmp_path / "pack.yaml").write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(PackError) as info:
        load_pack(tmp_path)
    assert info.value.issues[0].code == "not_mapping"


def test_bad_encoding(tmp_path: Path) -> None:
    (tmp_path / "pack.yaml").write_bytes(b"pack: \xff\xfe\n")
    with pytest.raises(PackError):
        load_pack(tmp_path)


def test_invalid_referenced_yaml_is_reported_with_file_prefix(tmp_path: Path) -> None:
    d = write_pack(tmp_path, "me.p")
    text = (d / "pack.yaml").read_text(encoding="utf-8")
    (d / "pack.yaml").write_text(text + "    taxonomy_seed: tax.yaml\n", encoding="utf-8")
    (d / "tax.yaml").write_text("terms: []\n", encoding="utf-8")
    with pytest.raises(PackError) as info:
        load_pack(d)
    assert info.value.issues[0].loc.startswith("tax.yaml")


def test_symlink_escape_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside.yaml"
    outside.write_text("terms: [{term: x}]\n", encoding="utf-8")
    d = write_pack(tmp_path, "me.p")
    (d / "link.yaml").symlink_to(outside)
    (d / "outside-dir").symlink_to(tmp_path, target_is_directory=True)
    text = (d / "pack.yaml").read_text(encoding="utf-8")
    (d / "pack.yaml").write_text(
        text.replace("templates", "")
        + "    taxonomy_seed: link.yaml\n    templates: outside-dir\n",
        encoding="utf-8",
    )
    with pytest.raises(PackError) as info:
        load_pack(d)
    assert {i.code for i in info.value.issues} == {"path_escape"}


def test_shared_reference_files_loaded_once(tmp_path: Path) -> None:
    d = write_pack(tmp_path, "me.p", domains="A,B")
    lines = (
        (d / "pack.yaml")
        .read_text(encoding="utf-8")
        .replace(
            "sub_mocs: [a]", "sub_mocs: [a]\n    taxonomy_seed: t.yaml\n    interview_bank: i.yaml"
        )
    )
    (d / "pack.yaml").write_text(lines, encoding="utf-8")
    (d / "t.yaml").write_text("terms: [{term: x}]\n", encoding="utf-8")
    (d / "i.yaml").write_text(
        "domains:\n  A: [{id: q, q: 왜}]\n  B: [{id: q, q: 왜}]\n", encoding="utf-8"
    )
    pack = load_pack(d)
    assert list(pack.taxonomies) == ["t.yaml"] and list(pack.interview_banks) == ["i.yaml"]


# ── discover ─────────────────────────────────────────────────────────────
def test_discover_rejects_name_mismatch_and_aggregates(tmp_path: Path) -> None:
    write_pack(tmp_path, "myelin.core", domains="")
    bad = write_pack(tmp_path, "me.p")
    bad.rename(tmp_path / "wrong-dir")
    (tmp_path / "not-a-pack").mkdir()
    with pytest.raises(PackError) as info:
        discover_packs(tmp_path)
    assert [i.code for i in info.value.issues] == ["name_mismatch"]


def test_discover_prefixes_child_errors(tmp_path: Path) -> None:
    d = tmp_path / "me.broken"
    d.mkdir()
    (d / "pack.yaml").write_text("pack: me.broken\n", encoding="utf-8")
    with pytest.raises(PackError) as info:
        discover_packs(tmp_path)
    assert all(i.loc.startswith("me.broken/") for i in info.value.issues)


# ── resolve ──────────────────────────────────────────────────────────────
def test_resolve_orders_dependencies_and_dedupes(tmp_path: Path) -> None:
    write_pack(tmp_path, "myelin.core", domains="")
    write_pack(tmp_path, "me.a", requires="myelin.core>=1.0", domains="A")
    write_pack(tmp_path, "me.b", requires="myelin.core;me.a", domains="B")
    order = resolve(["me.b", "me.a"], discover_packs(tmp_path))
    assert [p.name for p in order] == ["myelin.core", "me.a", "me.b"]


@pytest.mark.parametrize(
    ("setup", "selected", "code"),
    [
        ([("me.a", "me.missing", "A")], ["me.a"], "missing_pack"),
        ([("me.a", "me.b", "A"), ("me.b", "me.a", "B")], ["me.a"], "cycle"),
        ([("me.a", "myelin.core>=2", "A")], ["me.a"], "version_unsatisfied"),
        (
            [("me.a", "myelin.core", "X"), ("me.b", "myelin.core", "X")],
            ["me.a", "me.b"],
            "domain_conflict",
        ),
        ([("me.a", "", "A")], ["me.a"], "missing_core"),
        ([], ["me.nothing"], "missing_pack"),
    ],
)
def test_resolve_errors(
    tmp_path: Path, setup: list[tuple[str, str, str]], selected: list[str], code: str
) -> None:
    write_pack(tmp_path, "myelin.core", domains="")
    for name, req, dom in setup:
        write_pack(tmp_path, name, requires=req, domains=dom)
    with pytest.raises(PackError) as info:
        resolve(selected, discover_packs(tmp_path))
    assert code in {i.code for i in info.value.issues}


def test_resolve_without_core_requirement(tmp_path: Path) -> None:
    write_pack(tmp_path, "me.a", domains="A")
    assert [p.name for p in resolve(["me.a"], discover_packs(tmp_path), require_core=False)] == [
        "me.a"
    ]
