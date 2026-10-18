"""Hub API 흐름 — 온보딩 → 검토 → 승격(git commit), 설정, Domain, Pack."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from myelin_core import gitops
from myelin_core.errors import Issue
from myelin_hub_api.service import HubService

Put = Callable[[str, str], str]
AI = "00_Inbox/ai-drafts/WCET 예산.md"


def _log(vault: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(vault), "log", "--format=%s"], capture_output=True, text=True, check=True
    )
    return out.stdout.splitlines()


def test_uninitialized_state(client: TestClient, target: Path) -> None:
    state = client.get("/api/state").json()
    assert state["initialized"] is False and state["vault"] == str(target)
    res = client.get("/api/dashboard")
    assert res.status_code == 409 and res.json()["issues"][0]["code"] == "not_initialized"
    ob = client.get("/api/onboarding").json()
    assert ob["target_issues"] == [] and "myelin.core" not in [p["name"] for p in ob["packs"]]
    assert ob["levels"]["1"].startswith("초안")


def test_onboarding_preview_and_apply(
    client: TestClient, target: Path, act: dict[str, str], onboard_body: dict[str, Any]
) -> None:
    preview = client.post("/api/onboarding/preview", json=onboard_body, headers=act).json()
    assert preview["domains"] == ["AI-ML-AX", "ROBOTICS-LEARNING"] and preview["files"] > 20
    assert not target.exists()
    res = client.post("/api/onboarding/apply", json=onboard_body, headers=act)
    body = res.json()
    assert body["initialized"] and body["git"] and len(body["commit"]) == 40
    assert _log(target) == ["myelin: start vault history"]
    again = client.post("/api/onboarding/apply", json=onboard_body, headers=act)
    assert again.status_code == 400
    bad = client.post("/api/onboarding/apply", json={**onboard_body, "level": 9}, headers=act)
    assert bad.status_code == 422
    extra = client.post("/api/onboarding/apply", json={**onboard_body, "x": 1}, headers=act)
    assert extra.status_code == 422


def test_onboarding_without_git(
    client: TestClient, target: Path, act: dict[str, str], onboard_body: dict[str, Any]
) -> None:
    res = client.post("/api/onboarding/apply", json={**onboard_body, "git": False}, headers=act)
    assert res.json()["git"] is False and res.json()["commit"] is None


def test_review_promote_commits(
    client: TestClient,
    onboarded: Path,
    put: Put,
    make_draft: Callable[..., str],
    act: dict[str, str],
) -> None:
    put(AI, make_draft())
    queue = client.get("/api/review").json()
    assert [q["path"] for q in queue] == [AI] and queue[0]["ai"] is True
    note = client.get("/api/note", params={"path": AI}).json()
    assert note["frontmatter"]["origin"] == "claude" and "본문" in note["body"]
    assert client.get("/api/dashboard").json()["review_count"] == 1

    res = client.post("/api/review/promote", json={"path": AI, "id": queue[0]["id"]}, headers=act)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["path"] == "10_Domains/AI-ML-AX/WCET 예산.md"
    assert _log(onboarded)[0] == "myelin: promote 20261018-0900-wcet (WCET 예산)"
    # 초안은 아직 git에 없던 파일이므로 commit에는 새 위치만 담긴다
    assert gitops.files_in_commit(onboarded, out["commit"]) == [out["path"]]
    assert client.get("/api/review").json() == []
    dash = client.get("/api/dashboard").json()
    assert dash["stats"]["by_status"]["verified"] >= 1
    assert dash["commits"][0]["subject"].startswith("myelin: promote")

    again = client.post("/api/review/promote", json={"path": AI, "id": out["id"]}, headers=act)
    assert again.status_code == 409


def test_review_reject_and_refusals(
    client: TestClient,
    onboarded: Path,
    put: Put,
    make_draft: Callable[..., str],
    act: dict[str, str],
) -> None:
    put(AI, make_draft())
    wrong = client.post("/api/review/promote", json={"path": AI, "id": "x"}, headers=act)
    assert wrong.status_code == 409 and wrong.json()["issues"][0]["code"] == "id_mismatch"
    escape = client.post("/api/review/promote", json={"path": "../x.md", "id": "x"}, headers=act)
    assert escape.status_code == 409
    assert client.get("/api/note", params={"path": "myelin.yaml"}).status_code == 409
    res = client.post(
        "/api/review/reject", json={"path": AI, "id": "20261018-0900-wcet"}, headers=act
    )
    assert res.json()["path"] == "99_Archive/rejected/WCET 예산.md"
    assert _log(onboarded)[0].startswith("myelin: reject")


def test_promote_requires_git_then_git_init(
    client: TestClient,
    target: Path,
    put: Put,
    make_draft: Callable[..., str],
    act: dict[str, str],
    onboard_body: dict[str, Any],
) -> None:
    client.post("/api/onboarding/apply", json={**onboard_body, "git": False}, headers=act)
    put(AI, make_draft())
    body = {"path": AI, "id": "20261018-0900-wcet"}
    res = client.post("/api/review/promote", json=body, headers=act)
    assert res.status_code == 409 and res.json()["issues"][0]["code"] == "no_repo"
    assert (target / AI).exists()  # 아무것도 바뀌지 않음
    assert client.post("/api/git/init", json={}, headers=act).status_code == 200
    assert client.post("/api/git/init", json={}, headers=act).status_code == 409
    assert client.post("/api/review/promote", json=body, headers=act).status_code == 200


def test_commit_failure_reverts(
    client: TestClient,
    onboarded: Path,
    put: Put,
    make_draft: Callable[..., str],
    act: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    put(AI, make_draft())
    original = (onboarded / AI).read_text(encoding="utf-8")

    def boom(*_: object, **__: object) -> str:
        raise gitops.GitError("git commit 실패", [Issue("git", "hook rejected", "git_failed")])

    monkeypatch.setattr(gitops, "commit_paths", boom)
    res = client.post(
        "/api/review/promote", json={"path": AI, "id": "20261018-0900-wcet"}, headers=act
    )
    assert res.status_code == 409
    assert (onboarded / AI).read_text(encoding="utf-8") == original
    assert not (onboarded / "10_Domains/AI-ML-AX/WCET 예산.md").exists()


def test_settings(client: TestClient, onboarded: Path, act: dict[str, str]) -> None:
    s = client.get("/api/settings").json()
    assert s["level"] == 1 and s["mcp_write_drafts"] is False and s["git"] is True
    assert s["llm"]["route"]["40_IP/**"] == "local"
    yaml_before = (onboarded / "myelin.yaml").read_text(encoding="utf-8")
    res = client.post("/api/settings", json={"level": 2, "mcp_write_drafts": True}, headers=act)
    assert res.json()["level"] == 2 and res.json()["mcp_write_drafts"] is True
    after = (onboarded / "myelin.yaml").read_text(encoding="utf-8")
    assert "# 3+1 규칙" in after and after != yaml_before  # 주석 보존
    assert _log(onboarded)[0] == "myelin: update settings via Hub"
    same = client.post("/api/settings", json={"level": 2}, headers=act).json()
    assert same["commit"] is None
    # LLM 라우팅(기밀 경계)은 Hub에서 바꿀 수 없다
    route = client.post("/api/settings", json={"llm": {"default": "claude"}}, headers=act)
    assert route.status_code == 422
    assert client.post("/api/settings", json={"level": 7}, headers=act).status_code == 422


def test_domains_and_add(client: TestClient, onboarded: Path, act: dict[str, str]) -> None:
    d = client.get("/api/domains").json()
    assert [x["id"] for x in d["domains"]] == ["AI-ML-AX", "ROBOTICS-LEARNING"]
    assert d["domains"][0]["role"] == "primary" and d["domains"][0]["label"] == "D1"
    assert d["open_roles"] == ["growth", "extra"]
    assert "SEC-CONSULT" in [a["id"] for a in d["addable"]]
    body = {"domain": "SEC-CONSULT", "role": "extra", "pack": "org.security-consulting"}
    res = client.post("/api/domains/add", json=body, headers=act)
    assert res.status_code == 200, res.text
    assert (onboarded / "10_Domains/SEC-CONSULT/_MOC.md").is_file()
    assert _log(onboarded)[0] == "myelin: add domain SEC-CONSULT (extra)"
    assert client.post("/api/domains/add", json=body, headers=act).status_code == 400


def test_add_domain_commit_failure_reverts(
    client: TestClient, onboarded: Path, act: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    before = (onboarded / "myelin.yaml").read_text(encoding="utf-8")

    def boom(*_: object, **__: object) -> str:
        raise gitops.GitError("x", [Issue("git", "x")])

    monkeypatch.setattr(gitops, "commit_paths", boom)
    body = {"domain": "EMBEDDED-SW", "role": "growth"}
    assert client.post("/api/domains/add", json=body, headers=act).status_code == 409
    assert (onboarded / "myelin.yaml").read_text(encoding="utf-8") == before
    assert not (onboarded / "10_Domains/EMBEDDED-SW").joinpath("_MOC.md").exists()


def test_packs(client: TestClient, onboarded: Path, act: dict[str, str]) -> None:
    packs = {p["name"]: p for p in client.get("/api/packs").json()}
    assert (
        packs["brian.physical-ai"]["installed"]
        and not packs["org.security-consulting"]["installed"]
    )
    assert (
        packs["brian.physical-ai"]["terms"] > 0 and len(packs["brian.physical-ai"]["domains"]) == 4
    )
    src = client.get("/api/packs/brian.physical-ai/source").json()["yaml"]
    assert src.startswith("pack:") or "pack: brian.physical-ai" in src
    assert client.get("/api/packs/nope/source").status_code == 404
    ok = client.post("/api/packs/validate", json={"yaml": src}, headers=act).json()
    assert ok["ok"] and ok["pack"] == "brian.physical-ai"
    broken = client.post("/api/packs/validate", json={"yaml": "pack: [x\n"}, headers=act).json()
    assert not broken["ok"] and broken["issues"]
    schema = client.post(
        "/api/packs/validate", json={"yaml": "pack: me.x\nversion: 1\n"}, headers=act
    ).json()
    assert not schema["ok"] and any("kind" in i["loc"] for i in schema["issues"])
    assert not HubService.validate_pack("x" * 200_001)["ok"]


def test_packs_before_onboarding(client: TestClient) -> None:
    assert all(not p["installed"] for p in client.get("/api/packs").json())
