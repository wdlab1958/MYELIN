"""A/B contract test: the Hub must behave identically across Vault variants and Levels.

A = a Vault created by the Hub onboarding (org pack + one self-defined domain, Level 1).
B = the Reference Pack fixture Vault (brian.physical-ai, Level 2, 35 notes).
C = the seeded-violations fixture (broken notes present).
Invariants checked for every variant: all read endpoints answer 200 with the same top-level
shape, reads never write, the skill table follows the Level exactly, and Level changes flip the
same skills on and off in every variant.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from myelin_hub_api.app import create_app

from .conftest import CLICK, REPO_ROOT, tree_hash

READS = [
    "/api/health",
    "/api/vault",
    "/api/stats",
    "/api/doctor",
    "/api/domains",
    "/api/notes",
    "/api/notes?status=draft",
    "/api/search?q=MYELIN",
    "/api/review",
    "/api/guard",
    "/api/git/log",
    "/api/git/status",
    "/api/packs",
    "/api/settings",
    "/api/commons/candidates",
    "/api/metrics",
    "/api/patches",
]
VAULT_KEYS = {
    "ready", "root", "owner", "level", "level_name", "domains", "packs", "mcp", "skills", "git",
    "commons",
}  # fmt: skip
EXPECTED_ENABLED = {0: 0, 1: 4, 2: 6, 3: 7}


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=root, check=True, env=os.environ)


def _fixture(tmp_path: Path, name: str) -> Path:
    dst = tmp_path / name
    shutil.copytree(REPO_ROOT / "tests/fixtures/vaults" / name, dst)
    _git_init(dst)
    return dst


def _onboarded(tmp_path: Path) -> Path:
    root = tmp_path / "fresh"
    root.mkdir()
    with TestClient(create_app(root, serve_web=False)) as c:
        r = c.post(
            "/api/onboarding",
            headers=CLICK,
            json={
                "name": "A/B Tester",
                "primary": "SEC-CONSULT",
                "research": "CLOUD-SEC",
                "growth": None,
                "level": 1,
                "packs": ["a3.security-consulting"],
                "custom_domains": [
                    {"id": "CLOUD-SEC", "name": "클라우드 보안", "sub_mocs": ["IAM", "로깅"]}
                ],
            },
        )
        assert r.status_code == 200, r.text
    return root


@pytest.fixture(params=["A-onboarded", "B-reference", "C-seeded"])
def variant(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Iterator[tuple[str, TestClient, Path]]:
    name = str(request.param)
    if name == "A-onboarded":
        root = _onboarded(tmp_path)
    elif name == "B-reference":
        root = _fixture(tmp_path, "basic")
    else:
        root = _fixture(tmp_path, "seeded-violations")
    with TestClient(create_app(root, serve_web=False)) as c:
        yield name, c, root


def test_reads_same_shape_and_never_write(variant: tuple[str, TestClient, Path]) -> None:
    name, c, root = variant
    before = tree_hash(root)
    for url in READS:
        r = c.get(url)
        assert r.status_code == 200, f"{name}: {url} → {r.status_code} {r.text[:200]}"
    assert tree_hash(root) == before, f"{name}: a read endpoint wrote into the Vault"
    v = c.get("/api/vault").json()
    assert set(v) == VAULT_KEYS, f"{name}: /api/vault keys drifted: {sorted(v)}"
    assert v["ready"] is True and v["git"]["repo"] is True
    assert set(c.get("/api/git/status").json()) == {"repo", "clean", "changes"}
    assert {"notes", "kpi", "by_status", "by_origin", "by_domain", "review_queue"} <= set(
        c.get("/api/stats").json()
    )
    for d in c.get("/api/domains").json():
        assert {"id", "role", "notes", "verified", "moc", "sub_moc_notes"} <= set(d), (name, d)


def test_skill_table_follows_level_in_every_variant(
    variant: tuple[str, TestClient, Path],
) -> None:
    name, c, _ = variant
    for level in (0, 3, 1, 2):
        s = c.get("/api/settings").json()
        s["level"] = level
        r = c.put("/api/settings", headers=CLICK, json=s)
        assert r.status_code == 200, f"{name}: level {level}: {r.text}"
        v = c.get("/api/vault").json()
        enabled = [row["skill"] for row in v["skills"] if row["enabled"]]
        assert v["level"] == level and len(enabled) == EXPECTED_ENABLED[level], (
            name,
            level,
            enabled,
        )
        assert c.get("/api/git/status").json()["clean"] is True, f"{name}: settings left files"
        if level == 0:
            assert not any(row["enabled"] for row in v["skills"])
        if level >= 2:
            assert "/link" in enabled
        if level == 3:
            assert "/ip-scan" in enabled


def test_variants_agree_on_write_gate(variant: tuple[str, TestClient, Path]) -> None:
    """The HITL gate is the same regardless of Vault contents: no header → 403, never a write."""
    name, c, root = variant
    before = tree_hash(root)
    s = c.get("/api/settings").json()
    assert c.put("/api/settings", json=s).status_code == 403, name
    assert c.post("/api/review/promote/00_Inbox/ai-drafts/x.md", json={}).status_code == 403
    assert c.put("/api/packs/me.x", json={"pack_yaml": "pack: me.x"}).status_code == 403
    assert tree_hash(root) == before, name
