"""One Cycle hand-off (ADR-0018): schema, importer (good and bad input), routing, samples."""

from __future__ import annotations

import copy
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from myelin_core.doctor import run_doctor
from myelin_core.note import read_note
from myelin_core.onecycle import (
    PLATFORM_DOMAIN,
    SCHEMA_FILE,
    OneCycleError,
    import_findings,
    load_findings,
    route_domain,
)
from myelin_core.scaffold import add_domain
from myelin_core.vault import AI_DRAFTS, Vault

NOW = datetime(2026, 11, 26, 9, 0)
SAMPLES = Path(__file__).resolve().parents[3] / "docs/onecycle/samples"
PLATFORMS = ["llmops", "ssc", "argus", "proof-skills"]


@pytest.fixture
def vault(tmp_path: Path, repo_root: Path) -> Vault:
    dst = tmp_path / "v"
    shutil.copytree(
        repo_root / "tests/fixtures/vaults/basic",
        dst,
        ignore=shutil.ignore_patterns(".myelin", ".obsidian"),
    )
    return Vault.open(dst)


def _tree(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".myelin" not in p.parts
    }


def _sample(platform: str) -> dict[str, Any]:
    return json.loads((SAMPLES / f"findings.{platform}.sample.json").read_text(encoding="utf-8"))


def _write(tmp_path: Path, doc: Any, name: str = "f.json") -> Path:
    p = tmp_path / name
    p.write_text(doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False), "utf-8")
    return p


def test_schema_copies_are_identical_and_samples_validate(repo_root: Path) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    canonical = repo_root / "docs/onecycle/onecycle.findings.v1.schema.json"
    assert canonical.read_bytes() == SCHEMA_FILE.read_bytes()
    schema = json.loads(canonical.read_text(encoding="utf-8"))
    for platform in PLATFORMS:
        doc = _sample(platform)
        jsonschema.validate(doc, schema)
        loaded = load_findings(SAMPLES / f"findings.{platform}.sample.json")
        assert loaded.source.platform == platform
        assert all(f.simulated for f in loaded.findings)  # samples are fictional
    rd = json.loads(
        (repo_root / "docs/onecycle/onecycle.rediagnosis-request.v1.schema.json").read_text("utf-8")
    )
    assert rd["$id"] == "onecycle.rediagnosis-request/v1"
    for md in sorted(SAMPLES.glob("draft.*.sample.md")):
        fm = read_note(md).frontmatter
        assert fm.extra_fields["source_platform"] in PLATFORMS and fm.status.value == "draft"


def _mutations() -> list[tuple[str, Any]]:
    base = _sample("ssc")

    def m(fn: Any) -> Any:
        d = copy.deepcopy(base)
        fn(d)
        return d

    return [
        ("wrong schema", m(lambda d: d.__setitem__("schema", "onecycle.findings/v2"))),
        ("unknown top key", m(lambda d: d.__setitem__("extra", 1))),
        ("unknown platform", m(lambda d: d["source"].__setitem__("platform", "myelin"))),
        ("bad date", m(lambda d: d["source"].__setitem__("generated_at", "yesterday"))),
        ("date without time", m(lambda d: d["source"].__setitem__("generated_at", "2026-11-26"))),
        ("missing subject", m(lambda d: d.pop("subject"))),
        ("empty subject name", m(lambda d: d["subject"].__setitem__("name", ""))),
        ("id without platform", m(lambda d: d["findings"][0].__setitem__("id", "A.8.5"))),
        ("missing simulated", m(lambda d: d["findings"][0].pop("simulated"))),
        ("simulated as string", m(lambda d: d["findings"][0].__setitem__("simulated", "true"))),
        ("bad severity", m(lambda d: d["findings"][0].__setitem__("severity", "urgent"))),
        (
            "bad evidence kind",
            m(lambda d: d["findings"][0]["evidence"][0].__setitem__("kind", "x")),
        ),
        ("bad sha256", m(lambda d: d["findings"][0]["evidence"][0].__setitem__("sha256", "abc"))),
        ("line zero", m(lambda d: d["findings"][0].__setitem__("location", {"line": 0}))),
        ("unknown finding key", m(lambda d: d["findings"][0].__setitem__("cvss", 9.8))),
        ("null description", m(lambda d: d["findings"][0].__setitem__("description", None))),
        ("findings not a list", m(lambda d: d.__setitem__("findings", {}))),
    ]


@pytest.mark.parametrize(("label", "doc"), _mutations(), ids=[m[0] for m in _mutations()])
def test_invalid_files_are_refused_by_both_validators(
    label: str, doc: Any, tmp_path: Path, vault: Vault, repo_root: Path
) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    if "date" not in label:  # `format: date-time` is an annotation for jsonschema; we enforce it
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)
    before = _tree(vault.root)
    with pytest.raises(OneCycleError):
        import_findings(vault, _write(tmp_path, doc), now=NOW)
    assert _tree(vault.root) == before


def test_empty_duplicate_unreadable_are_refused(tmp_path: Path, vault: Vault) -> None:
    before = _tree(vault.root)
    empty = _sample("ssc")
    empty["findings"] = []
    dup = _sample("llmops")
    dup["findings"].append(copy.deepcopy(dup["findings"][0]))
    for doc in (empty, dup, "{not json", "[]", '"x"'):
        with pytest.raises(OneCycleError):
            import_findings(vault, _write(tmp_path, doc), now=NOW)
    with pytest.raises(OneCycleError):
        import_findings(vault, tmp_path / "missing.json", now=NOW)
    with pytest.raises(OneCycleError):
        import_findings(vault, SAMPLES / "findings.ssc.sample.json", now=NOW, domain="NOPE")
    assert _tree(vault.root) == before


@pytest.mark.parametrize("platform", PLATFORMS)
def test_import_creates_one_valid_draft_per_finding(
    platform: str, vault: Vault, repo_root: Path
) -> None:
    before = _tree(vault.root)
    src = SAMPLES / f"findings.{platform}.sample.json"
    n = len(_sample(platform)["findings"])
    res = import_findings(vault, src, now=NOW)
    assert res.ok and len(res.created) == n and not res.skipped and not res.blocked
    assert res.domain is None and res.hint and PLATFORM_DOMAIN[platform] in res.hint
    after = _tree(vault.root)
    new = sorted(set(after) - set(before))
    assert new == sorted(c.path for c in res.created)
    assert all(p.startswith(AI_DRAFTS + "/") for p in new)
    assert {k: v for k, v in after.items() if k in before} == before  # nothing else changed
    for c in res.created:
        note = read_note(vault.root / c.path)
        fm = note.frontmatter
        assert fm.status.value == "draft" and fm.origin.value == "claude" and not fm.domain
        assert fm.extra_fields["source_platform"] == platform
        assert fm.extra_fields["simulated"] is True and "simulated" in fm.tags
        assert fm.source == [f"onecycle:{c.finding_id}"]
        assert "simulated: true" in note.body
    report = run_doctor(vault, pack_roots=[repo_root / "packs"])
    assert not [f for f in report.errors if f.path.startswith(AI_DRAFTS)]
    # idempotent: a second import creates nothing and overwrites nothing
    again = import_findings(vault, src, now=datetime(2026, 11, 27, 10, 0))
    assert not again.created and len(again.skipped) == n
    assert _tree(vault.root) == after


def test_import_never_overwrites_and_survives_promotion(vault: Vault) -> None:
    src = SAMPLES / "findings.ssc.sample.json"
    res = import_findings(vault, src, now=NOW)
    draft = vault.root / res.created[0].path
    # the human promoted it (moved) — the finding is still known
    dest = vault.root / "10_Domains/D2" / draft.name
    draft.rename(dest)
    assert import_findings(vault, src, now=NOW).skipped[0][1].startswith("10_Domains/D2/")
    # a different file already sits at the draft name → kept, not overwritten
    dest.unlink()
    draft.write_text("사람이 쓴 다른 내용\n", encoding="utf-8")
    res2 = import_findings(vault, src, now=NOW)
    assert not res2.created and res2.skipped
    assert draft.read_text(encoding="utf-8") == "사람이 쓴 다른 내용\n"


def test_dry_run_writes_nothing(vault: Vault) -> None:
    before = _tree(vault.root)
    res = import_findings(vault, SAMPLES / "findings.llmops.sample.json", now=NOW, dry_run=True)
    assert len(res.created) == 2 and _tree(vault.root) == before


def test_guard_blocks_secrets_and_customer_names_flags_code(tmp_path: Path, vault: Vault) -> None:
    (vault.root / ".myelin").mkdir(exist_ok=True)
    (vault.root / ".myelin/customer-names.txt").write_text("테스트고객사\n", encoding="utf-8")
    doc = _sample("ssc")
    base = doc["findings"][0]
    secret = copy.deepcopy(base) | {
        "id": "ssc:x/secret",
        "description": "설정에 password=Sup3rS3cret!! 가 있었다",
    }
    customer = copy.deepcopy(base) | {"id": "ssc:x/customer", "title": "테스트고객사 포털 점검"}
    code = copy.deepcopy(base) | {
        "id": "ssc:x/code",
        "description": "```\n" + "\n".join(f"stmt_{i}();" for i in range(40)) + "\n```",
    }
    doc["findings"] = [base, secret, customer, code]
    res = import_findings(vault, _write(tmp_path, doc), now=NOW)
    assert not res.ok
    assert {i for i, _ in res.blocked} == {"ssc:x/secret", "ssc:x/customer"}
    assert all("Sup3r" not in r and "테스트고객사" not in r for _, r in res.blocked)
    created = {c.finding_id: c for c in res.created}
    assert set(created) == {base["id"], "ssc:x/code"}
    assert created["ssc:x/code"].flagged == ["large-code-block"]
    flagged = read_note(vault.root / created["ssc:x/code"].path)
    assert "guard-flag" in flagged.frontmatter.tags and "고객정보 가드 표시" in flagged.body
    drafts = "".join(p.read_text("utf-8") for p in (vault.root / AI_DRAFTS).glob("*.md"))
    assert "Sup3rS3cret" not in drafts and "테스트고객사" not in drafts
    # an unreadable guard policy refuses the whole import
    (vault.root / "90_System/infoguard.yaml").write_text("nope: 1\n", encoding="utf-8")
    with pytest.raises(OneCycleError):
        import_findings(vault, SAMPLES / "findings.argus.sample.json", now=NOW)


def test_hostile_titles_cannot_escape_or_break_frontmatter(tmp_path: Path, vault: Vault) -> None:
    doc = _sample("argus")
    doc["findings"][0]["title"] = '../../10_Domains/D1/x\n---\nstatus: verified\n"] #'
    res = import_findings(vault, _write(tmp_path, doc), now=NOW)
    assert len(res.created) == 1
    p = vault.root / res.created[0].path
    assert p.parent == vault.root / AI_DRAFTS
    assert read_note(p).frontmatter.status.value == "draft"


def test_routing_uses_the_platform_domain_when_configured(vault: Vault, repo_root: Path) -> None:
    assert route_domain("ssc", ["D1"]) is None and route_domain(None, ["SSC"]) is None
    assert route_domain("SSC", ["D1", "SSC"]) == "SSC"
    assert route_domain("proof-skills", ["PROOF-SKILLS"]) == "PROOF-SKILLS"
    add_domain(vault, "ARGUS", NOW, pack_name="wdlab.onecycle", pack_roots=[repo_root / "packs"])
    v = Vault.open(vault.root)
    res = import_findings(v, SAMPLES / "findings.argus.sample.json", now=NOW)
    assert res.domain == "ARGUS" and res.hint is None
    assert read_note(v.root / res.created[0].path).frontmatter.domain == ["ARGUS"]
    res2 = import_findings(v, SAMPLES / "findings.ssc.sample.json", now=NOW, domain="D2")
    assert read_note(v.root / res2.created[0].path).frontmatter.domain == ["D2"]
    assert not run_doctor(v, pack_roots=[repo_root / "packs"]).errors
