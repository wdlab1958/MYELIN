"""CHAOS — fault injection against the Hub API.

Contract under hostile/broken input: a correct result or a clean 4xx/5xx **with `detail`**; never a
traceback, never data loss, never a write outside the Vault, never a half-moved Vault (a failed
write leaves the working tree exactly as it was — ADR-0009: one user action = one commit).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from myelin_hub_api.app import INTENT_HEADER, create_app

from .conftest import CLICK, REPO_ROOT, tree_hash

DRAFT = "00_Inbox/ai-drafts/Lit - 양자화 서베이.md"
OTHER_DRAFT = "00_Inbox/ai-drafts/Dogbot 실험 09 초안.md"
PATCH_NAME = "20261018-1700-d2-moc-missing-links.patch.md"
PATCH_SRC = REPO_ROOT / "tests/fixtures/skill-outputs/link" / PATCH_NAME
CONFIDENTIAL = "40_IP/candidates/Agentic CAD 검증 루프.md"
FM = "---\nid: 20261018-1000-{slug}\ntype: fleeting\ncreated: 2026-10-18\n{extra}---\n{body}"


def note(slug: str, extra: str = "", body: str = "x\n") -> str:
    return FM.format(slug=slug, extra=extra, body=body)


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True).stdout


def porcelain(root: Path) -> list[str]:
    return sorted(ln for ln in git(root, "status", "--porcelain").splitlines() if ln.strip())


def log(root: Path) -> list[str]:
    return git(root, "log", "--pretty=%s").splitlines()


def detail(r: Any) -> str:
    assert r.headers.get("content-type", "").startswith("application/json"), r.text
    body = r.json()
    assert "detail" in body, body
    return json.dumps(body["detail"], ensure_ascii=False)


def clean_error(r: Any, *statuses: int) -> str:
    """Status in the allowed set and a JSON `detail` — the only acceptable failure shape."""
    assert r.status_code in statuses, (r.status_code, r.text[:300])
    return detail(r)


# =============================================================================== 1. broken notes
BROKEN: dict[str, bytes] = {
    "unterminated.md": b"---\nid: x\n",
    "list.md": b"---\n- a\n- b\n---\nx\n",
    "string.md": b"---\njust a string\n---\nx\n",
    "tabs.md": b"---\nid:\t20261018-1000-tabs\n\ttype: fleeting\n---\nx\n",
    "missing.md": b"---\ntype: fleeting\n---\nx\n",
    "badstatus.md": note("bs", "status: wat\n").encode(),
    "zero.md": b"",
    "bin.md": os.urandom(4096),
    "dupkey.md": note("dup", "id: 20261018-1000-dup2\n").encode(),
    "deep.md": note("deep", "extra: " + "[" * 2000 + "]" * 2000 + "\n").encode(),
    "anchor.md": note("anc", "tags: &a [a, *a]\n").encode(),
}
ODD_BUT_VALID: dict[str, bytes] = {
    "bom.md": b"\xef\xbb\xbf" + note("bom").encode(),
    "crlf.md": note("crlf").replace("\n", "\r\n").encode(),
    "domstr.md": note("ds", "domain: D1\n").encode(),
    "datestr.md": note("dt").replace("created: 2026-10-18", "created: '2026-10-18'").encode(),
    "nul.md": note("nul", body="x\x00y\n").encode(),
}
READS = [
    "/api/notes",
    "/api/search?q=lorem",
    "/api/review",
    "/api/stats?today=2026-10-18",
    "/api/doctor",
    "/api/domains",
    "/api/commons/candidates",
    "/api/metrics",
    "/api/patches",
    "/api/vault",
]


def test_broken_notes_are_reported_not_fatal(client: TestClient, vault_root: Path) -> None:
    d = vault_root / "00_Inbox/ai-drafts"
    for name, data in {**BROKEN, **ODD_BUT_VALID}.items():
        (d / name).write_bytes(data)
    for url in READS:
        assert client.get(url).status_code == 200, url
    drafts = {Path(x["path"]).name: x for x in client.get("/api/review").json()["drafts"]}
    for name in BROKEN:
        assert drafts[name]["doctor_ok"] is False and drafts[name]["error"], name
    for name in ODD_BUT_VALID:
        assert drafts[name]["doctor_ok"] is True, name
        assert client.get(f"/api/notes/00_Inbox/ai-drafts/{name}").status_code == 200
    doc = client.get("/api/doctor").json()
    assert doc["by_rule"]["schema"] == len(BROKEN)
    assert client.get("/api/stats?today=2026-10-18").json()["parse_errors"] == len(BROKEN)
    # index rebuild from scratch with the garbage still present
    client.app.state.service.index.rebuild()  # type: ignore[attr-defined]
    assert client.get("/api/stats?today=2026-10-18").json()["notes"] == 35 + len(ODD_BUT_VALID)
    # Review Gate on garbage: promote refuses, reject archives it verbatim (no data loss)
    clean_error(client.post("/api/review/promote/00_Inbox/ai-drafts/bin.md", headers=CLICK), 422)
    r = client.post("/api/review/reject/00_Inbox/ai-drafts/bin.md", headers=CLICK)
    assert r.status_code == 200 and (vault_root / r.json()["path"]).read_bytes() == BROKEN["bin.md"]
    assert not (d / "bin.md").exists()
    assert all(ln.startswith("??") for ln in porcelain(vault_root))  # only my untracked junk
    r = client.post(
        "/api/review/promote/00_Inbox/ai-drafts/crlf.md", headers=CLICK, json={"domain": "D1"}
    )
    assert (
        r.status_code == 200 and "status: verified" in (vault_root / r.json()["path"]).read_text()
    )


def test_5mb_note_does_not_stall_search(client: TestClient, vault_root: Path) -> None:
    big = vault_root / "30_Resources/big.md"
    big.write_text(note("big", body="가나다 lorem ipsum " * 300_000), encoding="utf-8")
    t = time.perf_counter()
    r = client.get("/api/search?q=lorem%20ipsum")
    assert r.status_code == 200 and time.perf_counter() - t < 10
    assert r.json()[0]["path"] == "30_Resources/big.md" and "[lorem]" in r.json()[0]["snippet"]
    assert client.get("/api/notes/30_Resources/big.md").status_code == 200


def test_symlink_escape_inside_vault_is_never_followed(
    client: TestClient, vault_root: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text(note("out", body="SECRET-OUTSIDE\n"), encoding="utf-8")
    (vault_root / "30_Resources/esc.md").symlink_to(outside)
    (vault_root / "30_Resources/dangling.md").symlink_to(tmp_path / "nope.md")
    (vault_root / "30_Resources/dirlink").symlink_to(tmp_path)
    for url in READS:
        assert client.get(url).status_code == 200, url
    assert client.get("/api/search?q=SECRET-OUTSIDE").json() == []
    clean_error(client.get("/api/notes/30_Resources/esc.md"), 400, 404)
    clean_error(client.get("/api/notes/30_Resources/dirlink/outside.md"), 400, 404)
    clean_error(client.post("/api/review/reject/30_Resources/esc.md", headers=CLICK), 400)
    assert outside.read_text(encoding="utf-8").endswith("SECRET-OUTSIDE\n")


# =============================================================================== 2. myelin.yaml
CORRUPT_CONFIGS = {
    "empty": "",
    "invalid-yaml": "a: [b",
    "list": "- a\n",
    "level-9": "owner: {name: x}\npacks: [myelin.core]\ndomains: {primary: D1}\nlevel: 9\n",
    "level-neg": "owner: {name: x}\npacks: [myelin.core]\ndomains: {primary: D1}\nlevel: -1\n",
    "level-str": "owner: {name: x}\npacks: [myelin.core]\ndomains: {primary: D1}\nlevel: two\n",
    "dup-roles": "owner: {name: x}\npacks: [myelin.core]\ndomains: {primary: D1, research: D1}\n",
    "dup-key": (
        "owner: {name: x}\npacks: [myelin.core]\ndomains: {primary: D1}\nlevel: 1\nlevel: 2\n"
    ),
}


@pytest.mark.parametrize("case", sorted(CORRUPT_CONFIGS))
def test_corrupt_config_reports_not_ready_and_blocks_onboarding(
    vault_root: Path, case: str
) -> None:
    (vault_root / "myelin.yaml").write_text(CORRUPT_CONFIGS[case], encoding="utf-8")
    before = tree_hash(vault_root)
    with TestClient(create_app(vault_root, serve_web=False)) as c:  # must start
        h = c.get("/api/health").json()
        assert h["ok"] and h["ready"] is False and "myelin.yaml" in h["error"]
        assert c.get("/api/vault").json()["ready"] is False
        assert "myelin.yaml" in clean_error(c.get("/api/stats"), 409)
        assert c.get("/api/packs").status_code == 200  # the wizard still works
        body = {"name": "x", "primary": "D1", "custom_domains": [{"id": "NEW", "name": "n"}]}
        assert "already initialised" in clean_error(
            c.post("/api/onboarding", headers=CLICK, json=body), 409
        )
        # fail-closed: nothing (not even the personal pack) is written over an existing Vault
        assert tree_hash(vault_root) == before and not (vault_root / "packs").exists()
    # the user fixes the file → next process is ready (no stale state)
    (vault_root / "myelin.yaml").write_text(
        "owner: {name: x}\npacks: [myelin.core, brian.physical-ai]\ndomains: {primary: D1}\n",
        encoding="utf-8",
    )
    with TestClient(create_app(vault_root, serve_web=False)) as c:
        assert c.get("/api/health").json()["ready"] is True


def test_missing_config_blocks_onboarding_over_existing_files(vault_root: Path) -> None:
    (vault_root / "myelin.yaml").unlink()
    before = tree_hash(vault_root)
    with TestClient(create_app(vault_root, serve_web=False)) as c:
        assert c.get("/api/health").json()["ready"] is False
        body = {
            "name": "x",
            "primary": "D1",
            "packs": ["brian.physical-ai"],
            "custom_domains": [{"id": "NEW", "name": "n"}],
        }
        clean_error(c.post("/api/onboarding", headers=CLICK, json=body), 409, 422)
        assert tree_hash(vault_root) == before and not (vault_root / "packs").exists()


def test_config_with_unknown_pack_or_undeclared_domain_is_reported(vault_root: Path) -> None:
    (vault_root / "myelin.yaml").write_text(
        "owner: {name: x}\npacks: [myelin.core, zz.nope]\ndomains: {primary: ZZZ}\n",
        encoding="utf-8",
    )
    with TestClient(create_app(vault_root, serve_web=False)) as c:
        assert c.get("/api/health").json()["ready"] is True
        for url in READS:
            assert c.get(url).status_code == 200, url
        assert c.get("/api/doctor").json()["by_rule"].get("domain", 0) > 0
        assert [d["id"] for d in c.get("/api/domains").json()] == ["ZZZ"]
        s = c.get("/api/settings").json()
        assert c.put("/api/settings", headers=CLICK, json=s).status_code == 200  # CLAUDE.md skipped


# =============================================================================== 3. git failures
def _prepare_patch(vault_root: Path) -> None:
    shutil.copy(PATCH_SRC, vault_root / "_patches" / PATCH_NAME)
    subprocess.run(["git", "add", "--", "_patches"], cwd=vault_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "patch"], cwd=vault_root, check=True)


def test_git_index_lock_leaves_vault_untouched(client: TestClient, vault_root: Path) -> None:
    _prepare_patch(vault_root)
    (vault_root / ".git/index.lock").write_text("", encoding="utf-8")
    before, status = tree_hash(vault_root), porcelain(vault_root)
    settings = client.get("/api/settings").json()
    attempts = [
        client.post(f"/api/review/promote/{DRAFT}", headers=CLICK),
        client.post(f"/api/review/reject/{OTHER_DRAFT}", headers=CLICK, json={"reason": "x"}),
        client.post(f"/api/patches/{PATCH_NAME}/apply", headers=CLICK),
        client.post(f"/api/patches/{PATCH_NAME}/reject", headers=CLICK),
        client.put("/api/settings", headers=CLICK, json={**settings, "level": 3}),
    ]
    for r in attempts:
        assert "index.lock" in clean_error(r, 500)
    assert tree_hash(vault_root) == before, "a failed commit must not leave files moved"
    assert porcelain(vault_root) == status and log(vault_root)[0] == "patch"
    (vault_root / ".git/index.lock").unlink()
    assert client.post(f"/api/review/promote/{DRAFT}", headers=CLICK).status_code == 200
    assert porcelain(vault_root) == [] and log(vault_root)[0].startswith("[myelin:review] promote")


def test_git_identity_missing_is_clean_error_without_partial_state(
    client: TestClient, vault_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        monkeypatch.delenv(k, raising=False)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    before = tree_hash(vault_root)
    r = client.post(f"/api/review/promote/{DRAFT}", headers=CLICK)
    assert "git commit" in clean_error(r, 500)
    assert tree_hash(vault_root) == before and log(vault_root) == ["fixture"]
    assert porcelain(vault_root) == ["?? .myelin/"]  # runtime dir only (no .gitignore yet)


def test_vault_without_git_is_initialised_on_first_write(
    client: TestClient, vault_root: Path
) -> None:
    shutil.rmtree(vault_root / ".git")
    assert client.get("/api/git/status").json() == {"repo": False, "clean": True, "changes": []}
    assert client.get("/api/git/log").json() == []
    r = client.post(f"/api/review/promote/{DRAFT}", headers=CLICK)
    assert r.status_code == 200 and (vault_root / ".git").is_dir()
    assert log(vault_root) == [
        "[myelin:review] promote Lit - 양자화 서베이 → D2",
        "[myelin:init] vault created",
    ]
    assert porcelain(vault_root) == []


def test_draft_deleted_between_list_and_action(client: TestClient, vault_root: Path) -> None:
    assert any(d["path"] == DRAFT for d in client.get("/api/review").json()["drafts"])
    (vault_root / DRAFT).unlink()
    before = tree_hash(vault_root)
    clean_error(client.post(f"/api/review/promote/{DRAFT}", headers=CLICK), 404)
    clean_error(client.post(f"/api/review/reject/{DRAFT}", headers=CLICK), 404)
    assert tree_hash(vault_root) == before and log(vault_root) == ["fixture"]
    assert not any(d["path"] == DRAFT for d in client.get("/api/review").json()["drafts"])


# =============================================================================== 4. review / patch
def test_double_click_promote_race(client: TestClient, vault_root: Path) -> None:
    results: list[int] = []

    def go() -> None:
        results.append(client.post(f"/api/review/promote/{DRAFT}", headers=CLICK).status_code)

    threads = [threading.Thread(target=go) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) in ([200, 404], [200, 409]), results
    assert porcelain(vault_root) == [] and len(log(vault_root)) == 2
    assert (vault_root / "10_Domains/D2/Lit - 양자화 서베이.md").exists()


def test_apply_patch_digest_and_moved_target(client: TestClient, vault_root: Path) -> None:
    shutil.copy(PATCH_SRC, vault_root / "_patches" / PATCH_NAME)
    pv = client.get(f"/api/patches/{PATCH_NAME}/preview").json()
    before = tree_hash(vault_root)
    clean_error(
        client.post(f"/api/patches/{PATCH_NAME}/apply", headers=CLICK, json={"digest": "zz"}), 409
    )
    clean_error(
        client.post(f"/api/patches/{PATCH_NAME}/apply", headers=CLICK, json={"digest": 123}), 422
    )
    assert tree_hash(vault_root) == before  # nothing applied so far
    r = client.post(
        f"/api/patches/{PATCH_NAME}/apply", headers=CLICK, json={"digest": None, "x": 1}
    )
    assert r.status_code == 200  # digest: null == "no digest" (CLI callers); extra fields ignored
    assert porcelain(vault_root) == []
    shutil.copy(PATCH_SRC, vault_root / "_patches" / PATCH_NAME)
    moc = vault_root / "10_Domains/D2/_MOC.md"
    moc.rename(vault_root / "10_Domains/D2/_MOC-moved.md")
    before = tree_hash(vault_root)
    r = client.post(
        f"/api/patches/{PATCH_NAME}/apply", headers=CLICK, json={"digest": pv["digest"]}
    )
    assert "target missing" in clean_error(r, 422) and tree_hash(vault_root) == before


@pytest.mark.parametrize(
    "name",
    [
        "a" * 300 + ".patch.md",
        "x%5c..%5c..%5cy.patch.md",
        "%00.patch.md",
        ".hidden.patch.md",
        "e%CC%81.patch.md",
        "..",
        "%2Fetc%2Fpasswd",
        "..%2F..%2Fx.patch.md",
    ],
)
def test_patch_name_fuzz_is_4xx(client: TestClient, vault_root: Path, name: str) -> None:
    before = tree_hash(vault_root)
    clean_error(client.get(f"/api/patches/{name}/preview"), 404, 422)
    clean_error(client.post(f"/api/patches/{name}/apply", headers=CLICK), 404, 422)
    clean_error(client.post(f"/api/patches/{name}/reject", headers=CLICK), 404, 422)
    assert tree_hash(vault_root) == before


def _write_patch(vault_root: Path, name: str, target: str) -> None:
    (vault_root / "_patches" / name).write_text(
        f"---\npatch: 1\ntarget: {target}\nkind: append\norigin: claude\nskill: link\n"
        "created: 2026-10-18\nrationale: r\nstatus: proposed\n---\n## append\n- x\n",
        encoding="utf-8",
    )


def test_patch_targets_outside_scope_are_blocked(client: TestClient, vault_root: Path) -> None:
    _write_patch(vault_root, "ip.patch.md", CONFIDENTIAL)
    _write_patch(vault_root, "abs.patch.md", "/etc/passwd")
    _write_patch(vault_root, "dots.patch.md", "../outside.md")
    _write_patch(vault_root, "patches.patch.md", "_patches/x.md")
    conf = vault_root / CONFIDENTIAL
    conf_text = conf.read_bytes()
    before = tree_hash(vault_root)
    assert "40_IP" in clean_error(client.post("/api/patches/ip.patch.md/apply", headers=CLICK), 422)
    for n in ("abs", "dots", "patches"):
        clean_error(client.get(f"/api/patches/{n}.patch.md/preview"), 422)
        clean_error(client.post(f"/api/patches/{n}.patch.md/apply", headers=CLICK), 422)
    assert conf.read_bytes() == conf_text and tree_hash(vault_root) == before
    assert not Path("/etc/passwd").read_text().endswith("- x\n")


def test_malformed_patch_files_do_not_break_review(client: TestClient, vault_root: Path) -> None:
    pdir = vault_root / "_patches"
    (pdir / "badyaml.patch.md").write_text("---\npatch: [\n---\n## append\nx\n", encoding="utf-8")
    (pdir / "bin.patch.md").write_bytes(b"\xff\xfe\x00garbage")
    (pdir / "dupkey.patch.md").write_text(
        "---\npatch: 1\npatch: 1\n---\n## append\nx\n", encoding="utf-8"
    )
    (pdir / "deep.patch.md").write_text(
        "---\nx: " + "[" * 3000 + "]" * 3000 + "\n---\n## append\nx\n", encoding="utf-8"
    )
    q = client.get("/api/review")
    assert q.status_code == 200
    invalid = {p["file"] for p in q.json()["patches"] if p.get("status") == "invalid"}
    assert invalid == {"badyaml.patch.md", "bin.patch.md", "dupkey.patch.md", "deep.patch.md"}
    assert client.get("/api/patches").status_code == 200
    for n in invalid:
        clean_error(client.get(f"/api/patches/{n}/preview"), 422)
        clean_error(client.post(f"/api/patches/{n}/apply", headers=CLICK), 422)
    r = client.post("/api/patches/bin.patch.md/reject", headers=CLICK)  # junk can still be rejected
    assert r.status_code == 200 and (vault_root / "_patches/rejected/bin.patch.md").exists()


def test_applied_history_with_same_name_is_preserved(client: TestClient, vault_root: Path) -> None:
    (vault_root / "_patches/applied").mkdir()
    (vault_root / "_patches/applied" / PATCH_NAME).write_text("HISTORY", encoding="utf-8")
    shutil.copy(PATCH_SRC, vault_root / "_patches" / PATCH_NAME)
    r = client.post(f"/api/patches/{PATCH_NAME}/apply", headers=CLICK)
    assert r.status_code == 200, r.text
    assert (vault_root / "_patches/applied" / PATCH_NAME).read_text(encoding="utf-8") == "HISTORY"
    kept = sorted(p.name for p in (vault_root / "_patches/applied").iterdir())
    assert kept == [PATCH_NAME.replace(".patch.md", " (2).patch.md"), PATCH_NAME]
    assert porcelain(vault_root) == [f"?? _patches/applied/{PATCH_NAME}"]  # my untracked stub
    listed = {(p["file"], p["group"], p["status"]) for p in client.get("/api/patches").json()}
    assert (kept[0], "applied", "applied") in listed
    assert (PATCH_NAME, "applied", "invalid") in listed  # the HISTORY stub is not a patch


# =============================================================================== 5. path traversal
TRAVERSAL_REFS = [
    "%2e%2e/secret.md",
    "%2e%2e%2fsecret.md",
    "/etc/passwd",
    "%2fetc%2fpasswd",
    "a%00b",
    "..%5c..%5csecret.md",
    "30_Resources%5c..%5c..%5csecret.md",
    "a" * 300,
    "a/" * 200 + "x.md",
    "00_Inbox/ai-drafts/%2e%2e/%2e%2e/myelin.yaml",
]


@pytest.mark.parametrize("ref", TRAVERSAL_REFS)
def test_ref_traversal_on_every_ref_endpoint(
    client: TestClient, vault_root: Path, tmp_path: Path, ref: str
) -> None:
    (tmp_path / "secret.md").write_text(note("sec", body="SECRET\n"), encoding="utf-8")
    before = tree_hash(vault_root)
    r = client.get(f"/api/notes/{ref}")
    assert "SECRET" not in r.text and "root:" not in r.text
    clean_error(r, 400, 404)
    clean_error(client.post(f"/api/review/promote/{ref}", headers=CLICK), 400, 404)
    clean_error(client.post(f"/api/review/reject/{ref}", headers=CLICK), 400, 404)
    clean_error(
        client.post(f"/api/commons/publish/{ref}", headers=CLICK, json={"confirmed": True}),
        400,
        404,
        409,
    )
    assert tree_hash(vault_root) == before and (tmp_path / "secret.md").exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["basic", "secret.md"]


@pytest.mark.parametrize("name", ["%2e%2e", "a%00b", "a" * 300, "me.x%5c..%5c..", "me.%2e%2e"])
def test_pack_name_fuzz(client: TestClient, vault_root: Path, tmp_path: Path, name: str) -> None:
    yaml_ok = (
        "pack: me.x\nkind: personal\nmaintainer: m\nrequires: [myelin.core]\n"
        "domains: [{id: X, name: x}]\n"
    )
    before = tree_hash(vault_root)
    clean_error(client.get(f"/api/packs/{name}"), 404)
    clean_error(
        client.put(f"/api/packs/{name}", headers=CLICK, json={"pack_yaml": yaml_ok}), 403, 404, 422
    )
    assert tree_hash(vault_root) == before and sorted(p.name for p in tmp_path.iterdir()) == [
        "basic"
    ]


# =============================================================================== 6. headers / body
def test_intent_origin_host_and_preflight(client: TestClient, vault_root: Path) -> None:
    before = tree_hash(vault_root)
    assert client.post(f"/api/review/promote/{DRAFT}").status_code == 403
    assert (
        client.post(
            f"/api/review/promote/{DRAFT}", headers={INTENT_HEADER: "User-Click"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/review/promote/{DRAFT}", headers={INTENT_HEADER: "user-click "}
        ).status_code
        == 403
    )
    for hdr in (
        {"Origin": "https://evil.example"},
        {"Origin": "null"},
        {"Host": "evil.example"},
        {"Host": "localhost.evil.example"},
        {"Origin": "http://localhost.evil.example"},
    ):
        r = client.post(f"/api/review/promote/{DRAFT}", headers={**CLICK, **hdr})
        assert r.status_code == 403, hdr
    r = client.options(
        "/api/settings",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "PUT"},
    )
    assert r.status_code == 405  # no CORS by design: the UI is same-origin
    r = client.options(
        "/api/settings",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "PUT"},
    )
    assert r.status_code == 403
    assert tree_hash(vault_root) == before and log(vault_root) == ["fixture"]


def test_body_fuzz(client: TestClient, vault_root: Path) -> None:
    before = tree_hash(vault_root)
    t = time.perf_counter()
    clean_error(client.put("/api/settings", headers=CLICK, json={"x": "a" * 10_000_000}), 422)
    assert time.perf_counter() - t < 10
    clean_error(
        client.put(
            "/api/settings", headers={**CLICK, "content-type": "text/plain"}, content="level: 2"
        ),
        422,
    )
    clean_error(
        client.put(
            "/api/settings", headers={**CLICK, "content-type": "application/json"}, content="{bad"
        ),
        422,
    )
    clean_error(client.put("/api/settings", headers=CLICK, json=[1, 2]), 422)
    clean_error(client.put("/api/settings", headers=CLICK, json=None), 422)
    s = client.get("/api/settings").json()
    clean_error(client.put("/api/settings", headers=CLICK, json={**s, "level": "2.5"}), 422)
    clean_error(client.put("/api/settings", headers=CLICK, json={**s, "level": "x"}), 422)
    clean_error(client.put("/api/settings", headers=CLICK, json={**s, "unknown": 1}), 422)
    clean_error(
        client.post("/api/onboarding", headers=CLICK, json={"name": 123, "primary": 5}), 409, 422
    )
    for q in ('"""', "*%20OR%20NEAR(", "%20", "abc%00def", "a" * 5000):
        assert client.get(f"/api/search?q={q}").status_code in (200, 400), q
    clean_error(client.get("/api/search?q=WCET&limit=abc"), 422)
    assert client.get("/api/search?q=WCET&limit=-5").status_code == 200
    assert client.get("/api/notes?limit=99999999999999999999").status_code in (200, 422)
    assert client.get("/api/git/log?limit=-1").status_code == 200
    clean_error(client.get("/api/stats?today=2026-13-45"), 400)
    assert tree_hash(vault_root) == before and log(vault_root) == ["fixture"]
    # lax but harmless coercions are accepted: numbers as strings, extra fields ignored
    assert client.put("/api/settings", headers=CLICK, json={**s, "level": "2"}).status_code == 200
    r = client.post(
        f"/api/review/promote/{DRAFT}", headers=CLICK, json={"domain": None, "junk": [1, 2]}
    )
    assert r.status_code == 200


# =============================================================================== 7. concurrency
def test_search_under_concurrent_rebuild(client: TestClient) -> None:
    errors: list[tuple[int, str]] = []
    svc = client.app.state.service  # type: ignore[attr-defined]

    def search() -> None:
        for _ in range(5):
            r = client.get("/api/search?q=WCET")
            if r.status_code != 200:
                errors.append((r.status_code, r.text[:200]))

    def rebuild() -> None:
        for _ in range(3):
            svc.index.rebuild()

    threads = [threading.Thread(target=search) for _ in range(20)] + [
        threading.Thread(target=rebuild)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []


def test_concurrent_settings_saves_serialise(client: TestClient, vault_root: Path) -> None:
    errors: list[tuple[str, int, str]] = []
    base = client.get("/api/settings").json()

    def save(i: int) -> None:
        r = client.put("/api/settings", headers=CLICK, json={**base, "level": i % 4})
        if r.status_code != 200:
            errors.append(("settings", r.status_code, r.text[:200]))

    def read() -> None:
        for url in ("/api/search?q=WCET", "/api/vault", "/api/stats", "/api/domains"):
            r = client.get(url)
            if r.status_code != 200:
                errors.append((url, r.status_code, r.text[:200]))

    threads = [threading.Thread(target=save, args=(i,)) for i in range(5)]
    threads += [threading.Thread(target=read) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert (
        porcelain(vault_root) == []
        and log(vault_root).count("[myelin:settings] update myelin.yaml") == 5
    )
    assert client.get("/api/vault").json()["level"] in range(4)


# =============================================================================== 8. filesystem
@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file modes")
def test_read_only_vault_write_is_clean_error(client: TestClient, vault_root: Path) -> None:
    locked = [
        vault_root,
        vault_root / "00_Inbox/ai-drafts",
        vault_root / "10_Domains/D2",
        vault_root / ".git",
    ]
    before = tree_hash(vault_root)
    for p in locked:
        p.chmod(0o555)
    try:
        assert "filesystem error" in clean_error(
            client.post(f"/api/review/promote/{DRAFT}", headers=CLICK), 500
        )
        s = client.get("/api/settings").json()
        assert "filesystem error" in clean_error(
            client.put("/api/settings", headers=CLICK, json=s), 500
        )
        assert (
            client.get("/api/notes").status_code == 200
            and client.get("/api/review").status_code == 200
        )
    finally:
        for p in locked:
            p.chmod(0o755)
    assert tree_hash(vault_root) == before and porcelain(vault_root) == ["?? .myelin/"]


def test_vault_path_with_spaces_and_korean(tmp_path: Path) -> None:
    root = tmp_path / "내 볼트 (chaos) ünïcode"
    shutil.copytree(REPO_ROOT / "tests/fixtures/vaults/basic", root)
    with TestClient(create_app(root, serve_web=False)) as c:
        assert c.get("/api/notes").status_code == 200 and c.get("/api/doctor").json()["errors"] == 0
        r = c.post(f"/api/review/promote/{DRAFT}", headers=CLICK)
        assert r.status_code == 200 and (root / r.json()["path"]).exists()
        assert c.get("/api/git/status").json()["clean"]


def test_packs_dir_missing_or_malformed(
    vault_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MYELIN_PACKS", str(tmp_path / "nonexistent"))
    with TestClient(create_app(vault_root, serve_web=False)) as c:  # repo packs/ fallback
        assert c.get("/api/packs").status_code == 200 and c.get("/api/domains").status_code == 200
    monkeypatch.setenv("MYELIN_PACKS", str(REPO_ROOT / "packs"))
    bad = vault_root / "packs/me.bad"
    bad.mkdir(parents=True)
    (bad / "pack.yaml").write_text("pack: [", encoding="utf-8")
    (vault_root / "packs/me.tpl/templates").mkdir(parents=True)
    (vault_root / "packs/me.tpl/templates/x.md").write_text("not a note", encoding="utf-8")
    with TestClient(create_app(vault_root, serve_web=False)) as c:
        names = {p["name"] for p in c.get("/api/packs").json()}
        assert "me.bad" not in names and "brian.physical-ai" in names
        clean_error(c.get("/api/packs/me.bad"), 404)
        assert c.get("/api/doctor").json()["errors"] == 0  # pack templates are not notes
        for url in READS:
            assert c.get(url).status_code == 200, url
    # the same pack both in <Vault>/packs and the registry → reported, Hub stays up
    shutil.copytree(REPO_ROOT / "packs/brian.physical-ai", vault_root / "packs/brian.physical-ai")
    with TestClient(create_app(vault_root, serve_web=False)) as c:
        assert c.get("/api/health").json()["ready"] is True
        assert "already loaded" in clean_error(c.get("/api/packs"), 422)
        clean_error(c.get("/api/packs/brian.physical-ai"), 422)
        assert (
            c.get("/api/domains").status_code == 200 and c.get("/api/doctor").json()["errors"] == 0
        )


# =============================================================================== 9. onboarding fuzz
def _custom(n: int) -> list[dict[str, Any]]:
    return [{"id": f"A{i}", "name": f"n{i}"} for i in range(n)]


ONBOARD_CASES: list[tuple[str, dict[str, Any], tuple[int, ...]]] = [
    ("empty-name", {"name": "", "primary": "D1"}, (422,)),
    ("500-char-name", {"name": "n" * 500, "primary": "D1", "packs": ["brian.physical-ai"]}, (200,)),
    (
        "newline-name",
        {"name": "a\nb: c\n---\n", "primary": "D1", "packs": ["brian.physical-ai"]},
        (200,),
    ),
    ("dashes-name", {"name": "---", "primary": "D1", "packs": ["brian.physical-ai"]}, (200,)),
    (
        "primary==research",
        {"name": "x", "primary": "D1", "research": "D1", "packs": ["brian.physical-ai"]},
        (422,),
    ),
    (
        "custom-collides-with-pack",
        {
            "name": "x",
            "primary": "D1",
            "packs": ["brian.physical-ai"],
            "custom_domains": [{"id": "D1", "name": "dup"}],
        },
        (422,),
    ),
    (
        "custom-id-traversal",
        {"name": "x", "primary": "X", "custom_domains": [{"id": "../x", "name": "n"}]},
        (422,),
    ),
    ("primary-traversal", {"name": "x", "primary": "../x"}, (422,)),
    (
        "empty-sub-mocs",
        {
            "name": "x",
            "primary": "A0",
            "custom_domains": [{"id": "A0", "name": "n", "sub_mocs": []}],
        },
        (200,),
    ),
    ("50-customs", {"name": "x", "primary": "A0", "custom_domains": _custom(50)}, (422,)),
    ("4-customs", {"name": "x", "primary": "A0", "custom_domains": _custom(4)}, (200,)),
    ("unknown-pack", {"name": "x", "primary": "D1", "packs": ["zz.nope"]}, (422,)),
    ("pack-traversal", {"name": "x", "primary": "D1", "packs": ["../x"]}, (422,)),
    ("level-9", {"name": "x", "primary": "D1", "level": 9}, (422,)),
    ("level-neg", {"name": "x", "primary": "D1", "level": -1}, (422,)),
    (
        "bad-email",
        {"name": "x", "primary": "D1", "email": "@", "packs": ["brian.physical-ai"]},
        (422,),
    ),
]


@pytest.mark.parametrize(
    ("label", "body", "expected"), ONBOARD_CASES, ids=[c[0] for c in ONBOARD_CASES]
)
def test_onboarding_body_fuzz(
    empty_client: TestClient, label: str, body: dict[str, Any], expected: tuple[int, ...]
) -> None:
    c = empty_client
    root: Path = c.app.state.root  # type: ignore[attr-defined]
    r = c.post("/api/onboarding", headers=CLICK, json=body)
    assert r.status_code in expected, (label, r.text[:300])
    if r.status_code != 200:
        detail(r)
        assert list(root.iterdir()) == [], (
            f"{label}: a failed onboarding must leave the directory empty"
        )
        assert c.get("/api/health").json()["ready"] is False
        return
    assert c.get("/api/health").json()["ready"] is True
    assert c.get("/api/doctor").json()["errors"] == 0 and c.get("/api/settings").status_code == 200
    assert c.get("/api/settings").json()["owner"]["name"] == body["name"].strip()
    assert c.get("/api/git/status").json()["clean"]
    with TestClient(create_app(root, serve_web=False)) as again:  # the written myelin.yaml re-loads
        assert again.get("/api/health").json()["ready"] is True


# =============================================================================== 10. SPA static
@pytest.fixture
def spa_client(
    vault_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    import myelin_hub_api.app as app_module

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>index</html>", encoding="utf-8")
    (dist / "assets" / "a.js").write_text("js", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("SECRET", encoding="utf-8")
    monkeypatch.setattr(app_module, "WEB_DIST", dist)
    with TestClient(app_module.create_app(vault_root, serve_web=True)) as c:
        yield c


@pytest.mark.parametrize(
    "path",
    [
        "/assets/../../myelin.yaml",
        "/assets/..%2f..%2fmyelin.yaml",
        "/index.html/..",
        "/index.html/../../secret.txt",
        "/%00",
        "/a%00b",
        "/assets/%00",
        "/" + "a" * 5000,
        "/" + "a/" * 2000,
        "/assets/" + "a" * 300,
        "/..%5c..%5csecret.txt",
        "/%2e%2e/%2e%2e/secret.txt",
        "/assets/a.js/..%2f..%2fsecret.txt",
    ],
)
def test_spa_hostile_paths(spa_client: TestClient, path: str) -> None:
    r = spa_client.get(path)
    assert r.status_code in (200, 404), (path, r.status_code)
    assert "SECRET" not in r.text and "owner:" not in r.text
    if r.status_code == 200:
        assert r.text in ("<html>index</html>", "js")
