"""ADR-0012 — myelin strength, reuse KPIs, Commons citations, publish push/PR best effort."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path

import pytest

from myelin_core.commons import (
    CommonsNote,
    commons_citations,
    commons_notes,
    commons_reuse,
    contributors,
    ensure_origin,
    init_commons,
    manual_next_step,
    open_pull_request,
    owner_hash,
    publish_note,
    push_branch,
)
from myelin_core.index import open_index
from myelin_core.metrics import (
    ALLOWED_KEYS,
    aggregate,
    aggregate_reuse,
    org_metrics,
    payload_is_anonymous,
)
from myelin_core.stats import (
    REUSED_STRENGTH,
    STRENGTH_MAX,
    TARGETS,
    NoteRef,
    compute_reuse,
    compute_stats,
    kpi_status,
    reuse_metrics,
    source_refs,
    strength_of,
)
from myelin_core.vault import Vault

NOW = datetime(2026, 10, 18, 12, 0)
TODAY = date(2026, 10, 18)
WCET = "10_Domains/D2/WCET 예산은 측정값의 1.5배로 잡는다.md"
WCET_ID = "20260907-0800-wcet-budget"


@pytest.fixture
def vault(fixtures_dir: Path, tmp_path: Path) -> Vault:
    dst = tmp_path / "vault"
    shutil.copytree(fixtures_dir / "vaults/basic", dst)
    return Vault.open(dst)


@pytest.fixture
def commons(tmp_path: Path) -> Path:
    root = tmp_path / "commons"
    init_commons(root)
    return root


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


def _ref(path: str, **kw: object) -> NoteRef:
    base: dict[str, object] = {
        "id": "20260101-0900-" + Path(path).stem.lower().replace(" ", "-"),
        "title": Path(path).stem,
        "status": "verified",
        "created": "2026-01-01",
        "source": (),
        "targets": (),
    }
    base.update(kw)
    return NoteRef(path=path, **base)  # type: ignore[arg-type]


# ----------------------------------------------------------------------------- strength
def test_strength_thresholds() -> None:
    assert strength_of(False, 99, 99, 99) == 0  # never myelinated without verification
    assert strength_of(True, 0, 0, 0) == 1
    assert strength_of(True, 1, 0, 0) == 1
    assert strength_of(True, 2, 0, 0) == 2  # inbound ≥ 2
    assert strength_of(True, 0, 1, 0) == 2  # output_uses ≥ 1
    assert strength_of(True, 5, 1, 0) == 2  # 5 inbound but only 1 output use
    assert strength_of(True, 5, 2, 0) == 3  # inbound ≥ 5 and output_uses ≥ 2
    assert strength_of(True, 0, 0, 1) == 3  # cited in Commons
    assert STRENGTH_MAX == 3 and REUSED_STRENGTH == 2


def test_source_refs_wikilink_id_and_raw() -> None:
    assert source_refs(["[[Lit - ROS2 Executor]]", "[[A|alias]] and [[B#h]]"]) == [
        "Lit - ROS2 Executor",
        "A",
        "B",
    ]
    assert source_refs(["see 20260907-0800-wcet-budget please"]) == ["20260907-0800-wcet-budget"]
    assert source_refs(["https://example.org/x", " Title "]) == ["https://example.org/x", "Title"]


def test_compute_reuse_counts_distinct_notes_and_outputs() -> None:
    a = _ref("10_Domains/D1/A.md")
    b = _ref("10_Domains/D1/B.md", targets=("A",))
    c = _ref("10_Domains/D1/C.md", targets=("A", a.id), status="draft")  # two links, one note
    out = _ref(
        "80_Outputs/Report.md",
        targets=("A",),
        source=("[[B]]", f"id {c.id}"),
        created="2026-02-01",
        status="unverified",
    )
    self_ref = _ref("10_Domains/D1/Self.md", targets=("Self",))  # self-links never count
    r = compute_reuse([a, b, c, out, self_ref])
    assert r[a.path].inbound == 3 and r[a.path].output_uses == 1 and r[a.path].strength == 3 - 1
    assert r[b.path].inbound == 0 and r[b.path].output_uses == 1 and r[b.path].strength == 2
    assert r[c.path].output_uses == 1 and r[c.path].strength == 0  # draft
    assert r[self_ref.path].inbound == 0 and r[self_ref.path].strength == 1
    # commons citations keyed by original id lift a verified note to 3
    r3 = compute_reuse([a, b], {b.id: 1})
    assert r3[b.path].commons_cited == 1 and r3[b.path].strength == 3
    assert r3[a.path].commons_cited == 0


def test_reuse_metrics_kpis_and_none_without_outputs() -> None:
    a = _ref("10_Domains/D1/A.md", created="2026-01-01")
    b = _ref("10_Domains/D1/B.md", created="2026-01-11", status="draft")
    out = _ref("80_Outputs/R.md", targets=("A", "B"), created="2026-01-31", status="unverified")
    m = reuse_metrics([a, b, out], compute_reuse([a, b, out]))
    assert m.reuse_ratio == 1.0  # the one verified note is used by an output
    assert m.reuse_lag_days == 25.0  # median of (30, 20)
    assert m.compose_sources_avg == 1.0  # only A is verified
    assert m.by_strength == {"0": 2, "1": 0, "2": 1, "3": 0}
    empty = reuse_metrics([a, b], compute_reuse([a, b]))
    assert empty.reuse_lag_days is None and empty.compose_sources_avg is None
    assert empty.reuse_ratio == 0.0
    none = reuse_metrics([], compute_reuse([]))
    assert none.reuse_ratio is None and none.by_strength == {"0": 0, "1": 0, "2": 0, "3": 0}


def test_stats_reuse_on_fixture_and_index_parity(vault: Vault) -> None:
    st = compute_stats(vault, TODAY)
    assert st.reuse_ratio is not None and 0 < st.reuse_ratio < 1
    assert st.reuse_lag_days == 31.0 and st.compose_sources_avg == 4.0  # 1 output, 4 sources
    assert sum(st.by_strength.values()) == st.notes and st.by_strength["3"] == 0
    rows = st.kpi_rows()
    assert [r[0] for r in rows] == list(TARGETS)
    assert {"reuse_ratio", "reuse_lag_days", "compose_sources_avg"} <= set(TARGETS)
    assert kpi_status("reuse_ratio", 0.29) == "alert" and kpi_status("reuse_ratio", 0.3) == "ok"
    assert (
        kpi_status("reuse_lag_days", 31) == "alert" and kpi_status("compose_sources_avg", 3) == "ok"
    )
    cited = {WCET_ID: 2}
    with open_index(vault) as idx:
        assert (
            idx.stats(TODAY, commons_cited=cited).to_dict()
            == compute_stats(vault, TODAY, commons_cited=cited).to_dict()
        )
        reuse = idx.reuse(cited)
    assert reuse[WCET].commons_cited == 2 and reuse[WCET].strength == 3
    assert compute_stats(vault, TODAY, commons_cited=cited).by_strength["3"] == 1
    # the fixture output cites 4 notes in its body → each has output_uses 1
    used = [p for p, r in reuse.items() if r.output_uses]
    assert len(used) == 4 and all(p.startswith("10_Domains/") for p in used)


# ----------------------------------------------------------------------------- commons citations
def _commons_note(
    commons: Path, rel: str, nid: str, title: str, author: str, body: str = ""
) -> None:
    p = commons / "notes" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"---\nid: {nid}\ntype: evergreen\ndomain: [D9]\nstatus: verified\norigin: human\n"
        f"confidence: high\nclassification: internal\nshare: true\nsource: []\n"
        f"created: 2026-09-01\ntags: []\npublished_from: {nid}\nauthor: {author}\n"
        f"published_by: abcdef012345\npublished: 2026-09-02\n---\n# {title}\n\n{body}\n",
        encoding="utf-8",
    )


def _vault_note(vault: Vault, rel: str, nid: str, body: str, source: str = "[]") -> None:
    p = vault.root / rel
    p.write_text(
        f"---\nid: {nid}\ntype: evergreen\ndomain: [D1]\nstatus: verified\norigin: human\n"
        f"confidence: high\nclassification: internal\nshare: false\nsource: {source}\n"
        f"created: 2026-10-01\ntags: []\n---\n# {Path(rel).stem}\n\n{body}\n",
        encoding="utf-8",
    )


def test_commons_citations_count_other_peoples_notes_only(vault: Vault, commons: Path) -> None:
    assert commons_notes(commons) == [] and commons_citations(vault, commons) == {}
    _commons_note(
        commons,
        "D9/20260901-0900-other-note-x.md",
        "20260901-0900-other-note",
        "Other Note",
        "김동료",
    )
    _commons_note(
        commons, "D9/20260901-0910-unused-y.md", "20260901-0910-unused", "Unused", "김동료"
    )
    # a note THIS vault published itself (original id lives here) is not "타인 인용"
    _commons_note(
        commons,
        "D2/20260907-0800-wcet-budget-z.md",
        WCET_ID,
        "WCET 예산은 측정값의 1.5배로 잡는다",
        "Brian",
    )
    _vault_note(
        vault, "10_Domains/D1/Cites by link.md", "20261001-0900-cites-link", "see [[Other Note]]"
    )
    _vault_note(
        vault,
        "10_Domains/D1/Cites by source.md",
        "20261001-0910-cites-source",
        "body",
        source='["[[Other Note]]", "20260901-0900-other-note"]',
    )
    cn = commons_notes(commons)
    assert [c.author for c in cn] == ["Brian", "김동료", "김동료"]
    assert isinstance(cn[0], CommonsNote) and cn[1].published_from == "20260901-0900-other-note"
    cites = commons_citations(vault, commons)
    assert cites == {"20260901-0900-other-note": 2}  # WCET (own) and Unused excluded
    # org-level reuse: metrics payloads from other owners + in-clone citations
    me = owner_hash(vault)
    for owner, ids in (
        ("o1", [WCET_ID, "20260901-0900-other-note"]),
        ("o2", [WCET_ID]),
        (me, [WCET_ID]),
    ):
        for week in ("2026-W41", "2026-W42"):
            f = commons / "metrics" / owner / f"{week}.json"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps({"owner": owner, "week": week, "cited_commons_ids": ids}))
    _commons_note(
        commons,
        "D9/20260901-0920-citing-w.md",
        "20260901-0920-citing",
        "Citing",
        "박동료",
        "uses [[Other Note]]",
    )
    assert commons_reuse(commons) == {
        WCET_ID: 3,
        "20260901-0900-other-note": 2,
    }  # owners once, not per week
    assert commons_reuse(commons, exclude_owner=me) == {WCET_ID: 2, "20260901-0900-other-note": 2}
    top = contributors(commons)
    assert top[0] == {"author": "Brian", "published": 1, "cited": 3}
    assert top[1] == {"author": "김동료", "published": 2, "cited": 2}
    assert top[2] == {"author": "박동료", "published": 1, "cited": 0}
    agg = aggregate_reuse(commons)
    assert agg["reuse_total"] == 5 and agg["top_contributors"] == top
    # the weekly table gains a `reuse` column (citations reported that week across owners)
    week = aggregate(commons)["2026-W42"]
    assert week["reuse"] == 4 and week["users"] == 3


def test_org_metrics_carries_reuse_and_cited_ids(vault: Vault, commons: Path) -> None:
    payload = org_metrics(vault, TODAY)
    assert set(payload) == ALLOWED_KEYS and payload["cited_commons_ids"] == []
    assert payload["reuse_ratio"] == 0.474 and payload["reuse_lag_days"] == 31.0
    assert payload_is_anonymous(payload, vault) == []
    bad = {**payload, "cited_commons_ids": ["WCET 예산은 측정값의 1.5배로 잡는다"]}
    assert any("list of note ids" in p for p in payload_is_anonymous(bad))
    assert any("nested" in p for p in payload_is_anonymous({**payload, "notes": [1]}))
    # with a configured clone, cited ids are reported (ids only)
    _commons_note(
        commons,
        "D9/20260901-0900-other-note-x.md",
        "20260901-0900-other-note",
        "Other Note",
        "김동료",
    )
    _vault_note(vault, "10_Domains/D1/Cites.md", "20261001-0900-cites", "see [[Other Note]]")
    vault.config = vault.config.model_copy(
        update={"commons": vault.config.commons.model_copy(update={"local": str(commons)})}
    )
    payload = org_metrics(vault, TODAY)
    assert payload["cited_commons_ids"] == ["20260901-0900-other-note"]
    assert payload_is_anonymous(payload, vault) == []
    assert "Other Note" not in json.dumps(payload, ensure_ascii=False)


# ----------------------------------------------------------------------------- publish → push → PR
def test_publish_push_without_origin_is_best_effort(vault: Vault, commons: Path) -> None:
    res = publish_note(vault, WCET, commons, confirmed=True, now=NOW, push=True, open_pr=True)
    assert not res.pushed and res.pr_url is None and res.push_error and "origin" in res.push_error
    assert res.pr_error and _git(commons, "rev-parse", "--verify", res.branch)  # commit kept
    step = manual_next_step(commons, res)
    assert step and f"git push -u origin {res.branch}" in step and "gh pr create" in step


def test_publish_adds_origin_from_commons_remote(
    vault: Vault, commons: Path, tmp_path: Path
) -> None:
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    assert ensure_origin(commons, None) is None
    res = publish_note(
        vault, WCET, commons, confirmed=True, now=NOW, push=True, open_pr=False, remote=str(bare)
    )
    assert res.pushed and res.push_error is None and res.pr_url is None and res.pr_error is None
    assert _git(commons, "remote", "get-url", "origin") == str(bare)
    assert (
        res.branch
        in subprocess.run(["git", "branch", "-a"], cwd=bare, capture_output=True, text=True).stdout
    )
    assert manual_next_step(commons, res) is None or "gh pr create" in manual_next_step(
        commons, res
    )  # type: ignore[operator]
    # a second push to the same (now existing) origin ignores `remote`
    assert ensure_origin(commons, "git@elsewhere:x.git") == str(bare)


def test_push_failure_and_missing_gh_never_raise(
    vault: Vault, commons: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git(commons, "remote", "add", "origin", str(tmp_path / "does-not-exist.git"))
    pushed, err = push_branch(commons, "main")
    assert not pushed and err and "git push" in err
    monkeypatch.setattr(shutil, "which", lambda _: None)
    url, err = open_pull_request(commons, "publish/x", "main")
    assert url is None and err and "gh" in err
    res = publish_note(vault, WCET, commons, confirmed=True, now=NOW, push=True, open_pr=True)
    assert not res.pushed and res.pr_url is None and res.push_error
    assert _git(commons, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    step = manual_next_step(commons, res)
    assert step is not None and res.branch in step
