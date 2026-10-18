"""Hub Commons API — 사람 확인 2단계(제안 → push), Vault 불변."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from myelin_core.commons import init_commons
from myelin_core.deid import MANUAL_CHECKLIST
from myelin_core.gitops import Author

NOTE = (
    "---\n"
    "id: 20261018-0900-ok\n"
    "type: evergreen\n"
    "domain: [AI-ML-AX]\n"
    "status: verified\n"
    "origin: human\n"
    "share: true\n"
    "created: 2026-10-17\n"
    "---\n"
    "# 공개 교훈\n\n제어 루프 예산에는 추론 지연을 포함한다.\n"
)


@pytest.fixture
def commons_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "commons"
    init_commons(repo, "Example Org", Author("Admin", "admin@localhost"))
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(remote)], check=True)
    return repo


def _link(vault: Path, repo: Path) -> None:
    text = (vault / "myelin.yaml").read_text(encoding="utf-8")
    text = text.replace("  enabled: false\n", f"  enabled: true\n  path: {repo}\n", 1)
    (vault / "myelin.yaml").write_text(text, encoding="utf-8")


def test_commons_disabled_by_default(client: TestClient, onboarded: Path) -> None:
    state = client.get("/api/commons").json()
    assert state["enabled"] is False and state["ok"] is False and state["proposals"] == []


def test_commons_flow(
    client: TestClient,
    onboarded: Path,
    commons_repo: Path,
    put: Callable[[str, str], str],
    act: dict[str, str],
    snapshot: Callable[[Path], dict[str, str]],
) -> None:
    _link(onboarded, commons_repo)
    rel = put("30_Resources/교훈.md", NOTE)
    state = client.get("/api/commons").json()
    assert state["ok"] and state["org"] == "Example Org"
    assert [c["path"] for c in state["candidates"]] == [rel]

    chk = client.get("/api/commons/check", params={"path": rel}).json()
    assert chk["ok"] and chk["branch"] == "publish/20261018-0900-ok"
    assert "commons_of: 20261018-0900-ok" in chk["content"]
    assert set(chk["checklist"]) == set(MANUAL_CHECKLIST)

    vault_before = snapshot(onboarded)
    body: dict[str, Any] = {"path": rel, "id": chk["id"], "confirmed": []}
    res = client.post("/api/commons/propose", json=body, headers=act)
    assert res.status_code == 409 and res.json()["issues"][0]["code"] == "unconfirmed"
    body["confirmed"] = list(MANUAL_CHECKLIST)
    res = client.post("/api/commons/propose", json=body, headers=act)
    assert res.status_code == 200, res.text
    assert snapshot(onboarded) == vault_before  # Vault 불변

    rows = client.get("/api/commons").json()["proposals"]
    assert rows == [
        {"branch": "publish/20261018-0900-ok", "subject": "commons: 교훈", "pushed": "no"}
    ]
    no_confirm = client.post("/api/commons/push", json={"branch": rows[0]["branch"]}, headers=act)
    assert no_confirm.status_code == 400
    pushed = client.post(
        "/api/commons/push", json={"branch": rows[0]["branch"], "confirm": True}, headers=act
    )
    assert pushed.status_code == 200, pushed.text
    assert client.get("/api/commons").json()["proposals"][0]["pushed"] == "yes"
    bad = client.post("/api/commons/push", json={"branch": "main", "confirm": True}, headers=act)
    assert bad.status_code == 409


def test_commons_broken_link(
    client: TestClient, onboarded: Path, tmp_path: Path, act: dict[str, str]
) -> None:
    _link(onboarded, tmp_path / "nowhere")
    state = client.get("/api/commons").json()
    assert state["enabled"] and not state["ok"] and state["issues"]


def test_settings_metrics_opt_in(client: TestClient, onboarded: Path, act: dict[str, str]) -> None:
    assert client.get("/api/settings").json()["metrics_opt_in"] is False
    res = client.post("/api/settings", json={"metrics_opt_in": True}, headers=act)
    assert res.json()["metrics_opt_in"] is True
    assert "opt_in: true" in (onboarded / "myelin.yaml").read_text(encoding="utf-8")
