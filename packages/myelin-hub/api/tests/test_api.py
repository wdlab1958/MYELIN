"""P6-T1/T5/T6/T7/T9 — Hub API: reads never write, writes need a user click, promote → commit."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from .conftest import CLICK, tree_hash

READ_ENDPOINTS = [
    "/api/health",
    "/api/vault",
    "/api/stats",
    "/api/doctor",
    "/api/domains",
    "/api/notes?status=verified",
    "/api/search?q=WCET",
    "/api/notes/20260907-0800-wcet-budget",
    "/api/review",
    "/api/guard",
    "/api/git/log",
    "/api/git/status",
    "/api/packs",
    "/api/packs/brian.physical-ai",
    "/api/settings",
    "/api/obsidian",
]


def _log(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "log", "--pretty=%s"], cwd=root, capture_output=True, text=True
    ).stdout
    return out.splitlines()


def test_reads_never_write(client: TestClient, vault_root: Path) -> None:
    before = tree_hash(vault_root)
    for url in READ_ENDPOINTS:
        r = client.get(url)
        assert r.status_code == 200, (url, r.text)
    # a pure validation POST does not write either
    yaml_ok = (
        "pack: me.x\nkind: personal\nmaintainer: m\nrequires: [myelin.core]\n"
        "domains: [{id: X, name: x}]\n"
    )
    r = client.post("/api/packs/validate", json={"pack_yaml": yaml_ok})
    assert r.status_code == 200 and r.json()["ok"]
    assert tree_hash(vault_root) == before
    assert _log(vault_root) == ["fixture"]


def test_vault_summary_and_stats(client: TestClient) -> None:
    v = client.get("/api/vault").json()
    assert v["ready"] and v["level"] == 2 and v["domains"]["D1"] == "primary"
    assert {s["skill"] for s in v["skills"] if s["enabled"]} == {
        "/ingest",
        "/distill",
        "/interview",
        "/review",
        "/link",
        "/compose",
    }
    st = client.get("/api/stats?today=2026-10-18").json()
    assert st["notes"] == 35 and st["review_queue"] == 4 and st["guard_blocks_7d"] == 0
    assert client.get("/api/stats?today=bad").status_code == 400
    d = client.get("/api/domains").json()
    assert [x["id"] for x in d] == ["D1", "D3", "D4", "D2"] and d[0][
        "moc"
    ] == "10_Domains/D1/_MOC.md"
    assert d[0]["verified"] >= 1 and d[0]["name"] == "AI/ML/AX Platform"
    n = client.get("/api/notes/10_Domains/D2/WCET 예산은 측정값의 1.5배로 잡는다.md").json()
    assert n["id"] == "20260907-0800-wcet-budget" and "backlinks" in n
    assert client.get("/api/notes/../x.md").status_code in (400, 404)
    assert client.get("/api/notes/nope").status_code == 404
    assert client.get("/api/notes?order=rank").status_code == 400


def test_writes_require_user_click(client: TestClient, vault_root: Path) -> None:
    before = tree_hash(vault_root)
    draft = "00_Inbox/ai-drafts/Lit - 양자화 서베이.md"
    assert client.post(f"/api/review/promote/{draft}").status_code == 403
    assert client.post(f"/api/review/reject/{draft}").status_code == 403
    assert client.put("/api/settings", json={}).status_code == 403
    assert client.post("/api/obsidian/setup").status_code == 403
    assert client.put("/api/packs/me.x", json={"pack_yaml": "x"}).status_code == 403
    assert client.post("/api/patches/x.patch.md/apply").status_code == 403
    assert client.post("/api/patches/x.patch.md/reject").status_code == 403
    assert client.post("/api/commons/publish/x.md", json={"confirmed": True}).status_code == 403
    assert client.post("/api/onboarding", json={"name": "x", "primary": "D1"}).status_code == 403
    assert tree_hash(vault_root) == before


def test_promote_creates_commit_and_moves_note(client: TestClient, vault_root: Path) -> None:
    draft = "00_Inbox/ai-drafts/Lit - 양자화 서베이.md"
    r = client.post(f"/api/review/promote/{draft}", headers=CLICK)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["path"] == "10_Domains/D2/Lit - 양자화 서베이.md" and body["domain"] == "D2"
    assert not (vault_root / draft).exists() and (vault_root / body["path"]).exists()
    text = (vault_root / body["path"]).read_text(encoding="utf-8")
    assert "status: verified" in text and "origin: mixed" in text and "reviewed: " in text
    assert _log(vault_root)[0] == "[myelin:review] promote Lit - 양자화 서베이 → D2"
    assert client.get("/api/git/status").json()["clean"]
    assert client.get("/api/notes?status=verified&domain=D2").json()
    # promoting again → 404; promoting a non-draft path → 400
    assert client.post(f"/api/review/promote/{draft}", headers=CLICK).status_code == 404
    assert (
        client.post("/api/review/promote/10_Domains/D1/_MOC.md", headers=CLICK).status_code == 400
    )
    # explicit domain override must be configured
    other = "00_Inbox/ai-drafts/Dogbot 실험 09 초안.md"
    assert (
        client.post(
            f"/api/review/promote/{other}", headers=CLICK, json={"domain": "D9"}
        ).status_code
        == 422
    )
    r = client.post(f"/api/review/promote/{other}", headers=CLICK, json={"domain": "D1"})
    assert r.status_code == 200 and r.json()["domain"] == "D1"
    assert "domain: [D3, D1]" in (vault_root / r.json()["path"]).read_text(encoding="utf-8")


def test_promote_refuses_invalid_or_domainless(client: TestClient, vault_root: Path) -> None:
    bad = vault_root / "00_Inbox/ai-drafts/broken.md"
    bad.write_text("no frontmatter", encoding="utf-8")
    assert (
        client.post("/api/review/promote/00_Inbox/ai-drafts/broken.md", headers=CLICK).status_code
        == 422
    )
    q = client.get("/api/review").json()
    assert any(d["path"].endswith("broken.md") and d["doctor_ok"] is False for d in q["drafts"])
    nod = vault_root / "00_Inbox/ai-drafts/nodomain.md"
    nod.write_text(
        "---\nid: 20261018-1000-nd\ntype: fleeting\ncreated: 2026-10-18\norigin: claude\n---\nx\n",
        encoding="utf-8",
    )
    assert (
        client.post("/api/review/promote/00_Inbox/ai-drafts/nodomain.md", headers=CLICK).status_code
        == 422
    )
    r = client.post(
        "/api/review/promote/00_Inbox/ai-drafts/nodomain.md", headers=CLICK, json={"domain": "D1"}
    )
    assert r.status_code == 200


def test_reject_archives_with_commit(client: TestClient, vault_root: Path) -> None:
    draft = "00_Inbox/ai-drafts/평가 지표 회의 - 원자 노트 1.md"
    r = client.post(f"/api/review/reject/{draft}", headers=CLICK, json={"reason": "중복"})
    assert r.status_code == 200
    assert r.json()["path"].startswith("99_Archive/rejected/")
    assert "status: deprecated" in (vault_root / r.json()["path"]).read_text(encoding="utf-8")
    assert _log(vault_root)[0].startswith(
        "[myelin:review] reject 평가 지표 회의 - 원자 노트 1 — 중복"
    )


def test_patches_preview_apply_reject(
    client: TestClient, vault_root: Path, repo_root: Path
) -> None:
    import shutil

    src = repo_root / "tests/fixtures/skill-outputs/link"
    for p in src.glob("*.patch.md"):
        shutil.copy(p, vault_root / "_patches" / p.name)
    q = client.get("/api/review").json()
    assert {p["file"] for p in q["patches"]} == {p.name for p in src.glob("*.patch.md")}
    assert all(p["group"] == "proposed" for p in q["patches"])
    name = "20261018-1700-d2-moc-missing-links.patch.md"
    # preview is read-only and returns diff + digest + fail-closed verdict
    before = tree_hash(vault_root)
    pv = client.get(f"/api/patches/{name}/preview").json()
    assert (
        pv["ok"]
        and pv["target"] == "10_Domains/D2/_MOC.md"
        and "+- [[ISR 안에서 로그를 찍지 않는다]]" in pv["diff"]
    )
    assert len(pv["digest"]) == 16 and tree_hash(vault_root) == before
    assert client.get("/api/patches/nope.patch.md/preview").status_code == 404
    # digest mismatch → 409, nothing applied
    r = client.post(f"/api/patches/{name}/apply", headers=CLICK, json={"digest": "0" * 16})
    assert r.status_code == 409 and tree_hash(vault_root) == before
    moc_before = (vault_root / "10_Domains/D2/_MOC.md").read_text(encoding="utf-8")
    r = client.post(f"/api/patches/{name}/apply", headers=CLICK, json={"digest": pv["digest"]})
    assert r.status_code == 200 and r.json()["status"] == "applied", r.text
    moc_after = (vault_root / "10_Domains/D2/_MOC.md").read_text(encoding="utf-8")
    assert (
        moc_after.startswith(moc_before.rstrip("\n"))
        and "[[ISR 안에서 로그를 찍지 않는다]]" in moc_after
    )
    assert not (vault_root / "_patches" / name).exists()
    assert "status: applied" in (vault_root / "_patches/applied" / name).read_text(encoding="utf-8")
    assert _log(vault_root)[0] == f"[myelin:link] apply patch {name} → 10_Domains/D2/_MOC.md"
    status = client.get("/api/git/status").json()
    assert all(
        c.startswith("??") for c in status["changes"]
    )  # only the other, still-untracked patch
    assert client.post(f"/api/patches/{name}/apply", headers=CLICK).status_code == 404  # moved away
    groups = {p["file"]: p["group"] for p in client.get("/api/patches").json()}
    assert groups[name] == "applied"
    # replace patch whose `before` is not unique → preview not ok, apply 422, target untouched
    other = "20261018-1705-wcet-note-related.patch.md"
    tgt = vault_root / "10_Domains/D2/WCET 예산은 측정값의 1.5배로 잡는다.md"
    before_t = tgt.read_text(encoding="utf-8")
    pv2 = client.get(f"/api/patches/{other}/preview").json()
    if not pv2["ok"]:
        assert (
            client.post(
                f"/api/patches/{other}/apply", headers=CLICK, json={"digest": pv2["digest"]}
            ).status_code
            == 422
        )
        assert tgt.read_text(encoding="utf-8") == before_t
    r = client.post(f"/api/patches/{other}/reject", headers=CLICK)
    assert r.status_code == 200 and (vault_root / "_patches/rejected" / other).exists()
    assert client.post("/api/patches/nope.patch.md/apply", headers=CLICK).status_code == 404
    assert client.post("/api/patches/nope.patch.md/reject", headers=CLICK).status_code == 404
    # apply without digest (CLI/script callers) still works for a fresh proposed patch
    shutil.copy(src / name, vault_root / "_patches" / name)
    (vault_root / "10_Domains/D2/_MOC.md").write_text(moc_before, encoding="utf-8")
    assert client.post(f"/api/patches/{name}/apply", headers=CLICK).status_code == 200


def test_settings_roundtrip(client: TestClient, vault_root: Path) -> None:
    s = client.get("/api/settings").json()
    s["level"] = 3
    s["mcp"] = {"write_draft": True, "expose_confidential": False}
    r = client.put("/api/settings", headers=CLICK, json=s)
    assert r.status_code == 200 and r.json()["settings"]["level"] == 3
    assert "level: 3" in (vault_root / "myelin.yaml").read_text(encoding="utf-8")
    assert "Level 3" in (vault_root / "CLAUDE.md").read_text(encoding="utf-8")
    assert _log(vault_root)[0] == "[myelin:settings] update myelin.yaml"
    assert client.get("/api/vault").json()["level"] == 3
    s["level"] = 9
    assert client.put("/api/settings", headers=CLICK, json=s).status_code == 422


def test_pack_editor(client: TestClient, vault_root: Path) -> None:
    packs = {p["name"]: p for p in client.get("/api/packs").json()}
    assert packs["brian.physical-ai"]["active"] and not packs["brian.physical-ai"]["editable"]
    src = client.get("/api/packs/brian.physical-ai").json()
    assert src["pack_yaml"].startswith("#") and not src["editable"]
    yaml_text = (
        "pack: me.side\nkind: personal\nmaintainer: me\nrequires: [myelin.core>=1.0]\n"
        "domains:\n  - {id: SIDE, name: Side, accent: cyan, sub_mocs: [a]}\n"
    )
    assert (
        client.post("/api/packs/validate", json={"pack_yaml": "pack: [bad"}).json()["ok"] is False
    )
    assert (
        client.put("/api/packs/me.other", headers=CLICK, json={"pack_yaml": yaml_text}).status_code
        == 422
    )
    assert (
        client.put(
            "/api/packs/a3.x",
            headers=CLICK,
            json={"pack_yaml": yaml_text.replace("me.side", "a3.x")},
        ).status_code
        == 403
    )
    r = client.put("/api/packs/me.side", headers=CLICK, json={"pack_yaml": yaml_text})
    assert r.status_code == 200, r.text
    assert (vault_root / "packs/me.side/pack.yaml").read_text(encoding="utf-8") == yaml_text
    assert _log(vault_root)[0] == "[myelin:packs] save me.side"
    packs = {p["name"]: p for p in client.get("/api/packs").json()}
    assert packs["me.side"]["editable"] and not packs["me.side"]["active"]
    assert client.get("/api/packs/me.nope").status_code == 404


def test_onboarding_flow(empty_client: TestClient) -> None:
    c = empty_client
    root: Path = c.app.state.root  # type: ignore[attr-defined]
    assert c.get("/api/health").json()["ready"] is False
    assert c.get("/api/vault").json()["ready"] is False
    assert c.get("/api/stats").status_code == 409  # not initialised
    assert c.get("/api/packs").status_code == 200  # wizard needs the registry
    body = {
        "name": "New User",
        "primary": "D1",
        "research": "D3",
        "packs": ["brian.physical-ai"],
        "level": 1,
    }
    assert c.post("/api/onboarding", json=body).status_code == 403
    r = c.post("/api/onboarding", headers=CLICK, json=body)
    assert r.status_code == 200, r.text
    assert r.json()["welcome"] == "00_Inbox/ai-drafts/MYELIN 시작하기.md"
    assert (
        (root / "myelin.yaml").exists()
        and (root / ".git").exists()
        and (root / ".claude/settings.json").exists()
    )
    assert c.get("/api/vault").json()["ready"] is True
    assert c.get("/api/git/status").json()["clean"]
    assert _log(root) == ["[myelin:init] vault created"]
    q = c.get("/api/review").json()
    assert [d["title"] for d in q["drafts"]] == ["MYELIN 시작하기"]
    r = c.post("/api/review/promote/00_Inbox/ai-drafts/MYELIN 시작하기.md", headers=CLICK)
    assert r.status_code == 200 and r.json()["path"] == "10_Domains/D1/MYELIN 시작하기.md"
    assert _log(root)[0] == "[myelin:review] promote MYELIN 시작하기 → D1"
    assert c.get("/api/stats").json()["by_status"].get("verified", 0) >= 3  # 2 MOCs + welcome
    assert c.post("/api/onboarding", headers=CLICK, json=body).status_code == 409
    assert c.post(
        "/api/onboarding", headers=CLICK, json={"name": "x", "primary": "D9"}
    ).status_code in (409, 422)


def test_guard_events_surface(client: TestClient, vault_root: Path) -> None:
    import json
    import time

    log = vault_root / ".myelin" / "guard.log"
    log.parent.mkdir(exist_ok=True)
    log.write_text(
        json.dumps({"ts": time.time(), "message": "blocked x"}) + "\nnot json\n", encoding="utf-8"
    )
    ev = client.get("/api/guard").json()
    assert len(ev) == 1 and ev[0]["message"] == "blocked x"
    assert client.get("/api/stats").json()["guard_blocks_7d"] == 1


def test_commons_candidates_and_publish(
    client: TestClient, vault_root: Path, tmp_path: Path
) -> None:
    from myelin_core.commons import init_commons

    before = tree_hash(vault_root)
    cands = client.get("/api/commons/candidates").json()
    assert len(cands) == 6 and all(c["ok"] for c in cands)
    assert tree_hash(vault_root) == before
    good = "10_Domains/D2/WCET 예산은 측정값의 1.5배로 잡는다.md"
    assert (
        client.post(f"/api/commons/publish/{good}", json={"confirmed": True}).status_code == 403
    )  # no click
    assert (
        client.post(
            f"/api/commons/publish/{good}", headers=CLICK, json={"confirmed": False}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/commons/publish/{good}", headers=CLICK, json={"confirmed": True}
        ).status_code
        == 409
    )  # no clone
    commons = tmp_path / "commons"
    init_commons(commons)
    s = client.get("/api/settings").json()
    s["commons"] = {"enabled": False, "local": str(commons)}
    assert client.put("/api/settings", headers=CLICK, json=s).status_code == 200
    bad = "40_IP/candidates/Agentic CAD 검증 루프.md"
    r = client.post(f"/api/commons/publish/{bad}", headers=CLICK, json={"confirmed": True})
    assert r.status_code == 422 and "confidential" in r.json()["detail"]
    r = client.post(f"/api/commons/publish/{good}", headers=CLICK, json={"confirmed": True})
    assert r.status_code == 200, r.text
    assert r.json()["branch"] == "publish/20260907-0800-wcet-budget" and r.json()["pushed"] is False
    m = client.get("/api/metrics").json()
    assert m["anonymous"] is True and m["opt_in"] is False and m["payload"]["published"] == 1
    assert "brian@example.org" not in json_dumps(m["payload"])


def json_dumps(o: object) -> str:
    import json

    return json.dumps(o, ensure_ascii=False)


def test_onboarding_records_metrics(empty_client: TestClient) -> None:
    c = empty_client
    body = {"name": "New User", "primary": "D1", "packs": ["brian.physical-ai"], "level": 1}
    assert c.post("/api/onboarding", headers=CLICK, json=body).status_code == 200
    assert (
        c.post(
            "/api/review/promote/00_Inbox/ai-drafts/MYELIN 시작하기.md", headers=CLICK
        ).status_code
        == 200
    )
    m = c.get("/api/metrics").json()
    assert [e["event"] for e in m["events"]] == ["onboard_start", "first_promote"]
    assert m["onboarding_minutes"] is not None and m["onboarding_minutes"] < 15


def test_host_and_origin_guard(vault_root: Path) -> None:
    """Threat model T08 — DNS rebinding / cross-site requests are refused."""
    from myelin_hub_api.app import create_app

    app = create_app(vault_root, serve_web=False)
    with TestClient(app, base_url="http://127.0.0.1:8787") as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/health", headers={"Host": "evil.example.com"}).status_code == 403
        assert (
            c.get("/api/health", headers={"Host": "127.0.0.1.evil.example:8787"}).status_code == 403
        )
        assert c.get("/api/health", headers={"Origin": "http://evil.example"}).status_code == 403
        assert c.get("/api/health", headers={"Origin": "http://localhost:5199"}).status_code == 200
        assert c.get("/api/health", headers={"Host": "localhost:8787"}).status_code == 200
        assert c.get("/api/health", headers={"Host": "[::1]:8787"}).status_code == 200
        r = c.post("/api/review/promote/x", headers={**CLICK, "Origin": "http://evil.example"})
        assert r.status_code == 403


def test_static_no_path_traversal(
    vault_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Threat model T09 — the SPA fallback never serves files outside web/dist."""
    import myelin_hub_api.app as app_module

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>index</html>", encoding="utf-8")
    (dist / "assets" / "a.js").write_text("js", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("SECRET", encoding="utf-8")
    monkeypatch.setattr(app_module, "WEB_DIST", dist)
    app = app_module.create_app(vault_root, serve_web=True)
    with TestClient(app) as c:
        assert c.get("/assets/a.js").text == "js"
        assert "index" in c.get("/domains").text
        for probe in (
            "/../secret.txt",
            "/%2e%2e/secret.txt",
            "/assets/../../secret.txt",
            "/..%2fsecret.txt",
        ):
            r = c.get(probe)
            assert "SECRET" not in r.text, probe


def test_domains_expose_sub_moc_notes(client: TestClient, vault_root: Path) -> None:
    d = {x["id"]: x for x in client.get("/api/domains").json()}
    subs = d["D3"]["sub_moc_notes"]
    assert [s["name"] for s in subs] == d["D3"]["sub_mocs"] and all(s["note"] is None for s in subs)
    (vault_root / "10_Domains/D3/D3 - Sim2Real.md").write_text(
        "---\nid: 20261018-1000-sim2real-moc\ntype: moc\ndomain: [D3]\ncreated: 2026-10-18\n---\n"
        "# Sim2Real\n",
        encoding="utf-8",
    )
    subs = {
        s["name"]: s["note"]
        for s in {x["id"]: x for x in client.get("/api/domains").json()}["D3"]["sub_moc_notes"]
    }
    assert subs["Sim2Real"] == "10_Domains/D3/D3 - Sim2Real.md"


def test_onboarding_with_custom_domains(empty_client: TestClient) -> None:
    """A new user defines their own domains — no dependence on Brian's reference pack."""
    c = empty_client
    root: Path = c.app.state.root  # type: ignore[attr-defined]
    body = {
        "name": "새 사용자",
        "primary": "CLOUD-SEC",
        "research": "LLM-SEC",
        "level": 1,
        "custom_domains": [
            {
                "id": "cloud-sec",
                "name": "클라우드 보안",
                "description": "CSP 설정 진단",
                "accent": "cyan",
                "sub_mocs": ["IAM", "네트워크", "로깅"],
            },
            {"id": "LLM-SEC", "name": "LLM 보안", "accent": "lime"},
        ],
    }
    r = c.post("/api/onboarding", headers=CLICK, json=body)
    assert r.status_code == 200, r.text
    assert (root / "packs/me.my-domains/pack.yaml").exists()
    v = c.get("/api/vault").json()
    assert (
        v["domains"] == {"CLOUD-SEC": "primary", "LLM-SEC": "research"}
        and "me.my-domains" in v["packs"]
    )
    assert "brian.physical-ai" not in v["packs"]
    d = {x["id"]: x for x in c.get("/api/domains").json()}
    assert d["CLOUD-SEC"]["pack"] == "me.my-domains" and d["CLOUD-SEC"]["sub_mocs"] == [
        "IAM",
        "네트워크",
        "로깅",
    ]
    assert (root / "10_Domains/CLOUD-SEC/_MOC.md").exists()
    packs = {p["name"]: p for p in c.get("/api/packs").json()}
    assert packs["me.my-domains"]["editable"] and packs["me.my-domains"]["active"]
    assert c.get("/api/doctor").json()["errors"] == 0


def test_onboarding_rejects_bad_custom_domain(empty_client: TestClient) -> None:
    c = empty_client
    body = {"name": "x", "primary": "BAD", "custom_domains": [{"id": "bad!", "name": "x"}]}
    r = c.post("/api/onboarding", headers=CLICK, json=body)
    assert r.status_code == 422 and "custom domain" in r.json()["detail"]
    assert c.get("/api/vault").json()["ready"] is False


def test_settings_validation_error_is_readable(client: TestClient) -> None:
    """Hub shows people the rule, not a Pydantic trace (commons.enabled without remote)."""
    s = client.get("/api/settings").json()
    s["commons"] = {**s.get("commons", {}), "enabled": True, "remote": None}
    r = client.put("/api/settings", headers=CLICK, json=s)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "commons.remote" in detail and "원격 저장소" in detail
    assert "pydantic" not in detail and "input_value" not in detail and "type=" not in detail
    s["commons"]["remote"] = "git@github.com:org/myelin-commons.git"
    assert client.put("/api/settings", headers=CLICK, json=s).status_code == 200


def test_obsidian_setup_writes_graph_config_once(client: TestClient, vault_root: Path) -> None:
    """P9-T8: GET shows Graph View off for the fixture; one click writes + commits the config;
    a second click changes nothing. Domain colour groups match the configured Domains."""
    st = client.get("/api/obsidian").json()
    assert st["graph_enabled"] is False and st["ready"] is False
    assert st["open_url"].startswith("obsidian://open?path=") and st["vault_name"] == "basic"
    r = client.post("/api/obsidian/setup", headers=CLICK)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["touched"]) == {
        ".obsidian/core-plugins.json",
        ".obsidian/graph.json",
        ".obsidian/app.json",
    }
    assert body["status"]["ready"] is True and body["status"]["domains_without_group"] == []
    assert _log(vault_root)[0] == "[myelin:settings] obsidian graph view"
    import json

    graph = json.loads((vault_root / ".obsidian/graph.json").read_text(encoding="utf-8"))
    domains = client.get("/api/vault").json()["domains"]
    assert {f"path:10_Domains/{d}/" for d in domains} <= {g["query"] for g in graph["colorGroups"]}
    before = tree_hash(vault_root)
    r2 = client.post("/api/obsidian/setup", headers=CLICK)
    assert r2.status_code == 200 and r2.json()["touched"] == [] and r2.json()["commit"] is None
    assert tree_hash(vault_root) == before
