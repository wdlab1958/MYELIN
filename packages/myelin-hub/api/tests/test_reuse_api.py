"""ADR-0012 — strength on note rows, reuse KPIs, Commons citation fields, publish → push → PR."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from myelin_core.commons import init_commons

from .conftest import CLICK, tree_hash

WCET = "10_Domains/D2/WCET 예산은 측정값의 1.5배로 잡는다.md"
WCET_ID = "20260907-0800-wcet-budget"
REUSE_KEYS = {"inbound", "output_uses", "commons_cited", "strength"}


def _configure_commons(client: TestClient, commons: Path, remote: str | None = None) -> None:
    s = client.get("/api/settings").json()
    s["commons"] = {"enabled": remote is not None, "local": str(commons), "remote": remote}
    assert client.put("/api/settings", headers=CLICK, json=s).status_code == 200


def test_note_rows_carry_strength(client: TestClient, vault_root: Path) -> None:
    before = tree_hash(vault_root)
    rows = client.get("/api/notes?limit=500").json()
    assert rows and all(set(r) >= REUSE_KEYS for r in rows)
    by_path = {r["path"]: r for r in rows}
    wcet = by_path[WCET]
    assert wcet["status"] == "verified" and wcet["inbound"] == 5 and wcet["output_uses"] == 1
    assert wcet["commons_cited"] == 0 and wcet["strength"] == 2
    assert all(r["strength"] == 0 for r in rows if r["status"] != "verified")
    assert all(r["strength"] >= 1 for r in rows if r["status"] == "verified")
    one = client.get(f"/api/notes/{WCET_ID}").json()
    assert one["strength"] == 2 and one["inbound"] == 5 and "backlinks" in one
    hits = client.get("/api/search?q=WCET").json()
    assert hits and all(set(h) >= REUSE_KEYS for h in hits) and "snippet" in hits[0]
    assert tree_hash(vault_root) == before  # reads never write


def test_stats_has_reuse_kpis_and_strength_histogram(client: TestClient) -> None:
    st = client.get("/api/stats?today=2026-10-18").json()
    kpis = {k["kpi"]: k for k in st["kpi"]}
    assert {"reuse_ratio", "reuse_lag_days", "compose_sources_avg"} <= set(kpis)
    assert kpis["reuse_ratio"]["status"] == "ok" and kpis["reuse_ratio"]["target"] == "≥ 0.30"
    assert (
        kpis["reuse_lag_days"]["status"] == "alert"
        and kpis["compose_sources_avg"]["status"] == "ok"
    )
    assert st["by_strength"] == {"0": 16, "1": 10, "2": 9, "3": 0}
    assert st["reuse_ratio"] == 0.474 and st["notes"] == 35  # existing keys kept


def test_vault_commons_and_candidates_cited(client: TestClient, tmp_path: Path) -> None:
    v = client.get("/api/vault").json()
    assert set(v) == {
        "ready", "root", "owner", "level", "level_name", "domains", "packs", "mcp", "skills", "git",
        "commons",
    }  # fmt: skip
    assert v["commons"]["published_count"] == 0 and v["commons"]["cited_total"] == 0
    cands = client.get("/api/commons/candidates").json()
    assert len(cands) == 6 and all(c["cited"] == 0 and c["published"] is False for c in cands)
    # publish WCET, merge it into the clone's main (champion review), and let another owner cite it
    commons = tmp_path / "commons"
    init_commons(commons)
    _configure_commons(client, commons)
    r = client.post(f"/api/commons/publish/{WCET}", headers=CLICK, json={"confirmed": True})
    assert r.status_code == 200 and r.json()["pushed"] is False and r.json()["pr_url"] is None
    assert "git push -u origin publish/" in r.json()["next_step"]
    subprocess.run(["git", "merge", "-q", "--no-edit", r.json()["branch"]], cwd=commons, check=True)
    m = commons / "metrics" / "o1" / "2026-W42.json"
    m.parent.mkdir(parents=True)
    m.write_text(json.dumps({"owner": "o1", "week": "2026-W42", "cited_commons_ids": [WCET_ID]}))
    v = client.get("/api/vault").json()
    assert v["commons"]["published_count"] == 1 and v["commons"]["cited_total"] == 1
    cands = {c["path"]: c for c in client.get("/api/commons/candidates").json()}
    assert cands[WCET]["published"] is True and cands[WCET]["cited"] == 1
    others = [c for p, c in cands.items() if p != WCET]
    assert all(c["cited"] == 0 and c["published"] is False for c in others)
    wcet = client.get(f"/api/notes/{WCET_ID}").json()
    assert wcet["commons_cited"] == 1 and wcet["strength"] == 3  # cited in Commons → hub
    st = client.get("/api/stats?today=2026-10-18").json()
    assert st["by_strength"]["3"] == 1
    payload = client.get("/api/metrics").json()["payload"]
    assert payload["cited_commons_ids"] == [] and payload["reuse_ratio"] is not None


def test_publish_push_pr_best_effort(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commons = tmp_path / "commons"
    init_commons(commons)
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    # 1) push requested, clone has no origin and config has no remote → 200, not pushed, next_step
    _configure_commons(client, commons)
    r = client.post(
        f"/api/commons/publish/{WCET}",
        headers=CLICK,
        json={"confirmed": True, "push": True, "pr": True},
    )
    body = r.json()
    assert r.status_code == 200 and body["pushed"] is False and body["pr_url"] is None
    assert (
        body["push_error"]
        and "origin" in body["push_error"]
        and body["branch"] in body["next_step"]
    )
    # 2) commons.remote configured → origin added (gap M9), branch pushed; gh missing → PR step
    monkeypatch.setattr(shutil, "which", lambda _: None)
    _configure_commons(client, commons, remote=str(bare))
    other = "10_Domains/D1/AX 저항은 통제감 상실에서 온다.md"
    r = client.post(
        f"/api/commons/publish/{other}",
        headers=CLICK,
        json={"confirmed": True, "push": True, "pr": True},
    )
    body = r.json()
    assert r.status_code == 200 and body["pushed"] is True and body["pr_url"] is None
    assert body["pr_error"] and "gh" in body["pr_error"] and "gh pr create" in body["next_step"]
    branches = subprocess.run(
        ["git", "branch", "-a"], cwd=bare, capture_output=True, text=True
    ).stdout
    assert body["branch"] in branches
    origin = subprocess.run(
        ["git", "remote", "get-url", "origin"], cwd=commons, capture_output=True, text=True
    ).stdout.strip()
    assert origin == str(bare)
    # 3) push only, no PR requested → next_step tells how to open the PR
    third = "10_Domains/D3/Sim2Real 갭의 첫 용의자는 마찰 계수다.md"
    r = client.post(
        f"/api/commons/publish/{third}", headers=CLICK, json={"confirmed": True, "push": True}
    )
    assert r.status_code == 200 and r.json()["pushed"] is True and r.json()["pr_error"] is None
    assert "gh pr create" in r.json()["next_step"]
    # body keys are a superset of the old contract
    assert {"branch", "commit", "dest", "pushed", "pr_url", "next_step"} <= set(r.json())
