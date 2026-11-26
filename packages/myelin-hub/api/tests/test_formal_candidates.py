"""Reproductions for the S2 candidates of the 2026-11-21 round that were only *suspected*
(`formal/CANDIDATES.md`, C2·C3·C5). Each test forces the interleaving the candidate describes and
asserts the property; each failed before the 2026-11-26 fix.

- C2 hub-add-domain-stale-vault     a Hub Domain add never drops a Domain another process added
- C3 commons-publish-base-branch    Commons publishes run one at a time (shared clone)
- C5 promote-dest-check-then-write  promote/reject never overwrite a note that appeared meanwhile
"""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from myelin_core.config import load_config
from myelin_hub_api import service as service_module

from .conftest import CLICK, REPO_ROOT

DRAFT = "00_Inbox/ai-drafts/Lit - 양자화 서베이.md"
HUMAN = "사람이 방금 만든 노트 — 덮어쓰면 안 된다\n"


def _cli_add_domain(vault_root: Path, domain: str) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "myelin_cli",
            "add-domain",
            domain,
            "--vault",
            str(vault_root),
            "--packs-dir",
            str(REPO_ROOT / "packs"),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_c2_hub_add_domain_keeps_a_domain_added_meanwhile(
    client: TestClient, vault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hub reads myelin.yaml → (registry scan) → CLI adds SEC-CONSULT → Hub writes IR."""
    real = service_module.discover_packs
    fired: list[bool] = []

    def scan_then_cli(*args: Any, **kwargs: Any) -> Any:
        reg = real(*args, **kwargs)
        if not fired:
            fired.append(True)
            _cli_add_domain(vault_root, "SEC-CONSULT")  # the other process, inside the window
        return reg

    monkeypatch.setattr(service_module, "discover_packs", scan_then_cli)
    r = client.post("/api/domains", headers=CLICK, json={"id": "IR"})
    assert fired, r.text
    domains = load_config(vault_root).domains.all_ids
    assert "SEC-CONSULT" in domains, (
        f"lost update: the Hub wrote a stale Domain list back ({domains}, HTTP {r.status_code})"
    )
    # either outcome is acceptable as long as nothing is lost: refused (409) or added on top
    assert r.status_code in (200, 409), r.text
    assert ("IR" in domains) == (r.status_code == 200)
    if r.status_code == 409:  # the retry the message asks for succeeds
        assert client.post("/api/domains", headers=CLICK, json={"id": "IR"}).status_code == 200
        assert {"SEC-CONSULT", "IR"} <= set(load_config(vault_root).domains.all_ids)


def test_c5_promote_never_overwrites_a_note_created_in_the_window(
    client: TestClient, vault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = vault_root / "10_Domains/D2" / Path(DRAFT).name
    real = service_module.dump_note

    def dump_then_obsidian(note: Any) -> str:
        text = real(note)
        dest.write_text(HUMAN, encoding="utf-8")  # Obsidian creates the same file name now
        return text

    monkeypatch.setattr(service_module, "dump_note", dump_then_obsidian)
    r = client.post(f"/api/review/promote/{DRAFT}", headers=CLICK)
    assert r.status_code == 409, r.text
    assert dest.read_text(encoding="utf-8") == HUMAN  # neither overwritten nor rolled back away
    assert (vault_root / DRAFT).is_file()  # the draft is still in the queue


def test_c5_reject_never_overwrites_an_archive_entry_created_in_the_window(
    client: TestClient, vault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = vault_root / "99_Archive/rejected" / Path(DRAFT).name
    real = service_module.HubService._mutation

    def mutation_after_clash(self: Any, rels: list[str]) -> Any:
        cm = real(self, rels)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(HUMAN, encoding="utf-8")  # appears after reject picked its file name
        return cm

    monkeypatch.setattr(service_module.HubService, "_mutation", mutation_after_clash)
    r = client.post(f"/api/review/reject/{DRAFT}", headers=CLICK, json={"reason": "x"})
    assert r.status_code == 409, r.text
    assert dest.read_text(encoding="utf-8") == HUMAN
    assert (vault_root / DRAFT).is_file()


def test_c3_commons_publish_holds_the_write_lock(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """publish_note switches branches in the one Commons clone, so two publishes must not overlap:
    while one runs, another thread cannot enter a serialised Hub write."""
    svc = client.app.state.service  # type: ignore[attr-defined]
    seen: dict[str, bool] = {}

    def fake_publish(*args: Any, **kwargs: Any) -> Any:
        def other() -> None:
            got = svc._write_lock.acquire(timeout=0.3)
            seen["other_entered"] = got
            if got:
                svc._write_lock.release()

        t = threading.Thread(target=other)
        t.start()
        t.join()
        raise service_module.CommonsError("stop here")

    monkeypatch.setattr(service_module, "publish_note", fake_publish)
    monkeypatch.setattr(type(svc), "_commons_path", lambda self: Path("/nonexistent-commons"))
    monkeypatch.setattr(type(svc), "_deid_rule", lambda self: None)
    r = client.post(
        "/api/commons/publish/10_Domains/D2/x.md", headers=CLICK, json={"confirmed": True}
    )
    assert r.status_code == 422
    assert seen == {"other_entered": False}
