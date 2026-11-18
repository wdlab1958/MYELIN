"""Deterministic reproductions of the TLC counterexamples found for the Hub (formal/, 2026-11-18).

Each test replays one trace of a `MC_bug*.cfg` run against the real HubService / API and asserts
the frozen property (`formal/<concern>/tla/Properties.tla`), not an API shape:

- F2  hub-config-stale-cache        P2  a Settings save never removes a Domain
- F8  hub-config-stale-cache        P1  no Hub answer is built from a stale myelin.yaml
- F4  review-gate-promote-toctou    P3  what is verified is what the human read
- F5  hub-pack-save-atomicity       P7  overlapping saves never fail each other
- F6  hub-pack-save-atomicity       P6  a save is all-or-nothing
- F7  hub-onboard-atomicity         P8  a failed onboarding leaves nothing behind (+ retry works)
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from myelin_core.config import load_config
from myelin_core.note import read_note
from myelin_hub_api import service as service_module

from .conftest import CLICK, REPO_ROOT, tree_hash

NEW_DOMAIN = "SEC-CONSULT"  # declared by packs/a3.security-consulting, not in the basic fixture
DRAFT = "00_Inbox/ai-drafts/Lit - 양자화 서베이.md"
MARK_READ = "사람이 읽은 문장"
MARK_REWRITTEN = "읽은 뒤에 AI 가 바꿔 쓴 문장"


def _cli_add_domain(vault_root: Path, domain: str) -> None:
    """The other process of the trace: `myelin add-domain` (CliAddDomain)."""
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


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True).stdout


def _pack_yaml(name: str, domain: str = "MY-DOMAIN") -> str:
    return (
        f"pack: {name}\nversion: 1.0.0\nkind: personal\nmaintainer: me\n"
        "requires: [myelin.core>=1.0]\ndomains:\n"
        f"  - id: {domain}\n    name: 내 Domain\n    accent: violet\n    description: d\n"
        "    sub_mocs: [a]\n    note_types: [evergreen]\n    classification_default: internal\n"
    )


# --------------------------------------------------------------------------- F2 (P2)
def test_f2_settings_put_between_get_and_put_keeps_domain(
    client: TestClient, vault_root: Path
) -> None:
    """trace_partial_P2_F2.md: BrowserGet -> CliAddDomain(d1) -> BrowserPut must not drop d1."""
    got = client.get("/api/settings")  # Settings.tsx save(): current = GET /api/settings
    current = got.json()
    _cli_add_domain(vault_root, NEW_DOMAIN)  # another process writes myelin.yaml in the window
    current["level"] = 3
    headers = {**CLICK, "If-Match": got.headers.get("etag", "")}
    r = client.put("/api/settings", headers=headers, json=current)
    # P2: whatever the Hub answers, the Domain added by the CLI is still configured
    assert NEW_DOMAIN in load_config(vault_root).domains.all_ids, (
        f"P2 violated (lost update): PUT /api/settings -> {r.status_code} dropped {NEW_DOMAIN}"
    )
    assert r.status_code == 412, r.text  # the client is told to read again
    # …and after reading again the save goes through without losing anything
    again = client.get("/api/settings")
    body = again.json()
    body["level"] = 3
    r2 = client.put(
        "/api/settings", headers={**CLICK, "If-Match": again.headers["etag"]}, json=body
    )
    assert r2.status_code == 200, r2.text
    cfg = load_config(vault_root)
    assert NEW_DOMAIN in cfg.domains.all_ids and cfg.level == 3


# --------------------------------------------------------------------------- F8 (P1)
def test_f8_vault_summary_is_not_built_from_a_stale_config(
    client: TestClient, vault_root: Path
) -> None:
    """trace_bug_P1.md with the decision = GET /api/vault (the Settings / Dashboard header)."""
    assert NEW_DOMAIN not in client.get("/api/vault").json()["domains"]  # Hub has loaded
    _cli_add_domain(vault_root, NEW_DOMAIN)
    on_disk = set(load_config(vault_root).domains.all_ids)
    first = client.get("/api/vault").json()  # the very next answer
    assert set(first["domains"]) == on_disk, (
        f"P1 violated (stale answer): /api/vault lists {sorted(first['domains'])}, "
        f"myelin.yaml has {sorted(on_disk)}"
    )


# --------------------------------------------------------------------------- F4 (P3)
def _rewrite_draft(vault_root: Path) -> None:
    """WriterRewrite(n): a skill / MCP write_draft / the editor replaces the waiting draft."""
    p = vault_root / DRAFT
    p.write_text(p.read_text(encoding="utf-8") + f"\n{MARK_REWRITTEN}\n", encoding="utf-8")


def test_f4_promote_never_verifies_text_the_human_did_not_read(
    client: TestClient, vault_root: Path
) -> None:
    """MC_bug trace: BrowserRead(n1) -> WriterRewrite(n1) -> HumanClick(n1) -> HubPromote(n1)."""
    p = vault_root / DRAFT
    p.write_text(p.read_text(encoding="utf-8") + f"\n{MARK_READ}\n", encoding="utf-8")
    read = client.get(f"/api/notes/{DRAFT}").json()  # "내용 읽기"
    assert MARK_READ in read["body"]
    _rewrite_draft(vault_root)  # after the human read it, before the click arrives
    r = client.post(
        f"/api/review/promote/{DRAFT}", headers=CLICK, json={"digest": read.get("digest")}
    )
    verified = sorted((vault_root / "10_Domains").rglob(Path(DRAFT).name))
    for v in verified:  # P3: verified content == the content that was read
        assert read_note(v).frontmatter.status.value != "verified" or (
            MARK_REWRITTEN not in v.read_text(encoding="utf-8")
        ), f"P3 violated: {v.relative_to(vault_root)} is verified with text nobody read"
    assert r.status_code == 409, r.text
    assert (vault_root / DRAFT).is_file() and not verified  # nothing moved, nothing committed
    assert MARK_REWRITTEN in (vault_root / DRAFT).read_text(encoding="utf-8")  # writer's text kept


def test_f4_promote_after_reading_again_succeeds(client: TestClient, vault_root: Path) -> None:
    """MC_sanity_reread: the rewritten draft is promoted once the human has read *that* text."""
    _rewrite_draft(vault_root)
    read = client.get(f"/api/notes/{DRAFT}").json()
    assert MARK_REWRITTEN in read["body"]
    r = client.post(f"/api/review/promote/{DRAFT}", headers=CLICK, json={"digest": read["digest"]})
    assert r.status_code == 200, r.text
    dest = vault_root / r.json()["path"]
    assert MARK_REWRITTEN in dest.read_text(encoding="utf-8")
    assert read_note(dest).frontmatter.status.value == "verified"


# --------------------------------------------------------------------------- F5 (P7)
def test_f5_double_click_save_pack_never_fails_on_the_other_request(
    client: TestClient, vault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MC_bug trace: WriteTmp(r1) WriteTmp(r2) ReadBackup(r1) Move(r1) ReadBackup(r2) Move(r2)."""
    svc = client.app.state.service  # type: ignore[attr-defined]
    text = _pack_yaml("me.twice")
    barrier = threading.Barrier(2)
    order = threading.Lock()
    real_move = shutil.move

    def move_after_both_wrote(src: Any, dst: Any, *a: Any, **k: Any) -> Any:
        # Hold each request at "about to move" until the other one has written its temp file
        # too (the trace). When writes are serialised the second request never gets here while
        # the first is inside, so the wait simply times out and the save proceeds.
        with contextlib.suppress(threading.BrokenBarrierError):
            barrier.wait(timeout=2)
        with order:
            return real_move(src, dst, *a, **k)

    monkeypatch.setattr(service_module.shutil, "move", move_after_both_wrote)
    results: list[Any] = []

    def click() -> None:
        try:
            results.append(svc.save_pack("me.twice", text))
        except BaseException as exc:  # what the API would turn into a 4xx/5xx
            results.append(exc)

    threads = [threading.Thread(target=click) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    errors = [r for r in results if isinstance(r, BaseException)]
    assert not errors, f"P7 violated (race): a save failed on the other request — {errors!r}"
    assert len(results) == 2
    final = vault_root / "packs/me.twice/pack.yaml"
    assert final.read_text(encoding="utf-8") == text  # P4 / P5
    assert not (vault_root / "packs/me.twice/pack.yaml.tmp").exists()
    assert _git(vault_root, "status", "--porcelain", "--", "packs") == ""  # P6


# --------------------------------------------------------------------------- F6 (P6)
def test_f6_save_pack_is_all_or_nothing_when_the_commit_is_refused(
    client: TestClient, vault_root: Path
) -> None:
    """MC_bug_p6 trace: WriteTmp ReadBackup Move LoadOkCommitFails — the Vault stays untouched."""
    hook = vault_root / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\necho refused by the pre-commit device >&2\nexit 1\n")
    hook.chmod(0o755)
    before = tree_hash(vault_root)
    status_before = _git(vault_root, "status", "--porcelain")
    r = client.put("/api/packs/me.new", headers=CLICK, json={"pack_yaml": _pack_yaml("me.new")})
    assert r.status_code == 500 and "commit" in r.text
    assert tree_hash(vault_root) == before, (
        "P6 violated: pack.yaml was written although its commit was refused"
    )
    assert _git(vault_root, "status", "--porcelain") == status_before  # nothing left staged
    # an existing pack is restored, not deleted
    hook.unlink()
    assert (
        client.put(
            "/api/packs/me.new", headers=CLICK, json={"pack_yaml": _pack_yaml("me.new")}
        ).status_code
        == 200
    )
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    before = tree_hash(vault_root)
    r = client.put(
        "/api/packs/me.new", headers=CLICK, json={"pack_yaml": _pack_yaml("me.new", "OTHER")}
    )
    assert r.status_code == 500
    assert tree_hash(vault_root) == before
    assert _git(vault_root, "status", "--porcelain") == ""  # .gitignore is committed by now


# --------------------------------------------------------------------------- F7 (P8, P9, P10)
ONBOARD = {
    "name": "Kim",
    "primary": "MY-DOMAIN",
    "packs": [],
    "level": 1,
    "custom_domains": [{"id": "MY-DOMAIN", "name": "내 Domain", "sub_mocs": ["a"]}],
}


def _files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*")}


def test_f7_failed_onboarding_leaves_nothing_and_can_be_retried(empty_client: TestClient) -> None:
    """MC_bug trace: Start WritePack InitVault Welcome Fail — the first commit is refused because
    the chosen folder already holds a note without frontmatter (an existing Obsidian folder)."""
    root: Path = empty_client.app.state.root  # type: ignore[attr-defined]
    old = root / "10_Domains" / "MY-DOMAIN" / "예전 메모.md"
    old.parent.mkdir(parents=True)
    old.write_text("# frontmatter 없는 기존 노트\n", encoding="utf-8")
    before = _files(root)
    r = empty_client.post("/api/onboarding", headers=CLICK, json=ONBOARD)
    assert r.status_code >= 400 and "예전 메모.md" in r.text  # the cause is reported
    left = _files(root) - before
    # P8: nothing the failed request created remains (P9: no myelin.yaml naming a deleted pack)
    assert not left, f"P8 violated: half-initialised Vault left behind — {sorted(left)[:8]}"
    assert old.read_text(encoding="utf-8") == "# frontmatter 없는 기존 노트\n"  # user file intact
    assert empty_client.get("/api/health").json()["ready"] is False
    # the user fixes the cause; the same request now succeeds (S_NeverRetryOk)
    old.unlink()
    r2 = empty_client.post("/api/onboarding", headers=CLICK, json=ONBOARD)
    assert r2.status_code == 200, r2.text
    assert (root / "packs/me.my-domains/pack.yaml").is_file()  # P9
    assert "[myelin:init]" in _git(root, "log", "--oneline")  # P10
    assert empty_client.get("/api/health").json()["ready"] is True
