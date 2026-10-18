"""Hub patch API — 미리보기는 쓰지 않고, 적용·반려는 클릭 + digest 확인 + git commit."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from myelin_core import gitops
from myelin_core.errors import Issue

MOC = "10_Domains/AI-ML-AX/_MOC.md"
P = "_patches/20261018-0900-moc.patch.md"
PATCH = (
    "---\npatch: 1\ntarget: 10_Domains/AI-ML-AX/_MOC.md\nkind: append\n"
    'under: "## 핵심 Evergreen"\norigin: claude\nskill: link\ncreated: 2026-10-18\n'
    "rationale: 같은 개념의 verified 노트가 빠짐\nstatus: proposed\n---\n## append\n- [[교훈]]\n"
)


def _log(vault: Path) -> list[str]:
    return subprocess.run(
        ["git", "-C", str(vault), "log", "--format=%s"], capture_output=True, text=True, check=True
    ).stdout.splitlines()


def test_patch_flow(
    client: TestClient,
    onboarded: Path,
    put: Callable[[str, str], str],
    act: dict[str, str],
    snapshot: Callable[[Path], dict[str, str]],
) -> None:
    put(P, PATCH)
    put("_patches/legacy.md", "# 수동 patch\n")
    rows = client.get("/api/patches").json()
    assert [r["structured"] for r in rows] == [True, False]
    before = snapshot(onboarded)
    prev = client.get("/api/patches/preview", params={"path": P}).json()
    assert "+- [[교훈]]" in prev["diff"] and len(prev["digest"]) == 16
    assert snapshot(onboarded) == before  # 미리보기는 쓰지 않는다

    wrong = client.post("/api/patches/apply", json={"path": P, "digest": "0" * 16}, headers=act)
    assert wrong.status_code == 409 and wrong.json()["issues"][0]["code"] == "digest_mismatch"
    res = client.post("/api/patches/apply", json={"path": P, "digest": prev["digest"]}, headers=act)
    assert res.status_code == 200, res.text
    assert "- [[교훈]]" in (onboarded / MOC).read_text(encoding="utf-8")
    assert _log(onboarded)[0].startswith("myelin: apply patch 20261018-0900-moc.patch.md")
    assert sorted(gitops.files_in_commit(onboarded, res.json()["commit"])) == [
        MOC,
        "_patches/applied/20261018-0900-moc.patch.md",
    ]
    again = client.post("/api/patches/apply", json={"path": P, "digest": "x"}, headers=act)
    assert again.status_code == 409

    rej = client.post("/api/patches/reject", json={"path": "_patches/legacy.md"}, headers=act)
    assert rej.status_code == 200 and (onboarded / "_patches/rejected/legacy.md").exists()
    assert client.get("/api/patches").json() == []
    bad = client.get("/api/patches/preview", params={"path": "../myelin.yaml"})
    assert bad.status_code == 409


def test_patch_commit_failure_reverts(
    client: TestClient,
    onboarded: Path,
    put: Callable[[str, str], str],
    act: dict[str, str],
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    put(P, PATCH)
    moc_before = (onboarded / MOC).read_text(encoding="utf-8")
    digest = client.get("/api/patches/preview", params={"path": P}).json()["digest"]

    def boom(*_: object, **__: object) -> str:
        raise gitops.GitError("x", [Issue("git", "hook", "git_failed")])

    monkeypatch.setattr(gitops, "commit_paths", boom)
    res = client.post("/api/patches/apply", json={"path": P, "digest": digest}, headers=act)
    assert res.status_code == 409
    assert (onboarded / MOC).read_text(encoding="utf-8") == moc_before
    assert (onboarded / P).exists() and not (onboarded / "_patches/applied").joinpath(
        "20261018-0900-moc.patch.md"
    ).exists()
