"""Team mode (ADR-0016): auth, roles, confidentiality, audit log, bind policy.
Personal (loopback) mode must stay exactly as it was."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from myelin_hub_api.__main__ import main
from myelin_hub_api.app import create_app
from myelin_hub_api.team import (
    ACCESS_LOG,
    FailureThrottle,
    LiveTeamAuth,
    TeamAuth,
    TeamConfigError,
    check_bind,
    new_token,
    restricted,
    route_role,
    token_hash,
)

from .conftest import CLICK, REPO_ROOT, tree_hash

READ_TOKEN, READ_HASH = new_token()
WRITE_TOKEN, WRITE_HASH = new_token()
AUTH = TeamAuth.from_mapping(
    {
        "allowed_hosts": ["hub.team.example"],
        "users": [
            {"name": "reader", "role": "read", "token_sha256": READ_HASH},
            {"name": "writer", "role": "write", "token_sha256": WRITE_HASH},
        ],
    }
)
R = {"Authorization": f"Bearer {READ_TOKEN}"}
W = {"Authorization": f"Bearer {WRITE_TOKEN}"}
CONF_IP = "40_IP/candidates/Agentic CAD 검증 루프.md"
CONF_NOTE = "10_Domains/D2/기밀 설계 메모.md"
CONF_DRAFT = "00_Inbox/ai-drafts/기밀 초안.md"
PUBLIC_DRAFT = "00_Inbox/ai-drafts/Lit - 양자화 서베이.md"
SECRET_WORD = "ZXQ기밀본문표식"


def _note(nid: str, classification: str, body: str, status: str = "verified") -> str:
    extra = "reviewed: 2026-10-18\n" if status == "verified" else ""
    return (
        f"---\nid: {nid}\ntype: evergreen\ndomain: [D2]\nstatus: {status}\norigin: claude\n"
        f"classification: {classification}\ncreated: 2026-10-18\n{extra}---\n# 제목\n\n{body}\n"
    )


@pytest.fixture
def team_vault(vault_root: Path) -> Path:
    (vault_root / CONF_NOTE).write_text(
        _note("20261018-1000-conf-note", "confidential", SECRET_WORD + " [[공개 노트]]"),
        encoding="utf-8",
    )
    (vault_root / CONF_DRAFT).write_text(
        _note("20261018-1001-conf-draft", "confidential", SECRET_WORD, "draft"), encoding="utf-8"
    )
    # the confidential note links to this public one: the backlink must not leak its title
    (vault_root / "10_Domains/D2/공개 노트.md").write_text(
        _note("20261018-1002-public-note", "internal", "공개 본문"), encoding="utf-8"
    )
    (vault_root / "10_Domains/D2/기밀을 가리키는 공개.md").write_text(
        _note("20261018-1003-public-two", "internal", "공개 본문 WCET"), encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=vault_root, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "team fixture", "--no-verify"],
        cwd=vault_root,
        check=True,
        env={**os.environ},
    )
    return vault_root


@pytest.fixture
def team(team_vault: Path) -> Iterator[TestClient]:
    with TestClient(create_app(team_vault, serve_web=False, team=AUTH)) as c:
        yield c


# ------------------------------------------------------------------ authentication
ALL_GETS = [
    "/api/vault",
    "/api/stats",
    "/api/doctor",
    "/api/domains",
    "/api/notes",
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
    "/api/commons/candidates",
    "/api/metrics",
    "/api/patches",
    "/api/assistant/status",
    "/api/team/me",
    "/api/docs",
    "/api/openapi.json",
]


@pytest.mark.parametrize("url", ALL_GETS)
def test_unauthenticated_requests_are_rejected(team: TestClient, url: str) -> None:
    r = team.get(url)
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
    for bad in ("Bearer wrong", "Bearer " + "x" * 47, f"Basic {READ_TOKEN}", READ_TOKEN, "Bearer"):
        assert team.get(url, headers={"Authorization": bad}).status_code == 401


def test_unauthenticated_writes_are_rejected_and_change_nothing(
    team: TestClient, team_vault: Path
) -> None:
    before = tree_hash(team_vault)
    for method, url in (
        ("post", f"/api/review/promote/{PUBLIC_DRAFT}"),
        ("post", f"/api/review/reject/{PUBLIC_DRAFT}"),
        ("put", "/api/settings"),
        ("put", "/api/packs/me.x"),
        ("post", "/api/domains"),
        ("post", "/api/onboarding"),
        ("post", "/api/assistant/chat"),
        ("post", "/api/obsidian/setup"),
    ):
        r = getattr(team, method)(url, headers=CLICK, json={})
        assert r.status_code == 401, url
    assert tree_hash(team_vault) == before


def test_health_is_open_but_says_nothing_about_the_vault(
    team: TestClient, team_vault: Path
) -> None:
    d = team.get("/api/health").json()
    assert d == {"ok": True, "version": d["version"], "mode": "team"}
    assert str(team_vault) not in json.dumps(d)


def test_token_comparison_and_config_validation(tmp_path: Path) -> None:
    assert AUTH.authenticate(READ_TOKEN).name == "reader"  # type: ignore[union-attr]
    assert AUTH.authenticate(WRITE_TOKEN).role == "write"  # type: ignore[union-attr]
    for bad in (None, "", "short", READ_TOKEN[:-1], READ_TOKEN + "x", READ_HASH, "x" * 600):
        assert AUTH.authenticate(bad) is None
    # the hash of the empty string must never authenticate, even if someone puts it in the file
    weak = TeamAuth.from_mapping(
        {"users": [{"name": "a", "role": "read", "token_sha256": token_hash("")}]}
    )
    assert weak.authenticate("") is None and weak.authenticate(None) is None
    ok = {"name": "a", "role": "read", "token_sha256": READ_HASH}
    for bad_cfg in (
        None,
        [],
        {},
        {"users": []},
        {"users": [ok], "cors": "*"},
        {"users": [{**ok, "role": "admin"}]},
        {"users": [{**ok, "token_sha256": READ_TOKEN}]},  # a raw token instead of its hash
        {"users": [{**ok, "name": "a b"}]},
        {"users": [{**ok, "password": "x"}]},
        {"users": [ok, ok]},
        {"users": [ok, {**ok, "name": "b"}]},  # shared token
        {"users": [ok], "allowed_hosts": ["*"]},
        {"users": [ok], "allowed_hosts": "hub"},
    ):
        with pytest.raises(TeamConfigError):
            TeamAuth.from_mapping(bad_cfg)
    f = tmp_path / "auth.yaml"
    f.write_text(f"users:\n  - {{ name: a, role: read, token_sha256: {READ_HASH} }}\n", "utf-8")
    f.chmod(0o644)
    with pytest.raises(TeamConfigError, match="chmod 600"):
        TeamAuth.load(f)
    f.chmod(0o600)
    assert TeamAuth.load(f).users[0].name == "a"
    with pytest.raises(TeamConfigError):
        TeamAuth.load(tmp_path / "missing.yaml")
    f.write_text("users: [unclosed\n", "utf-8")
    with pytest.raises(TeamConfigError):
        TeamAuth.load(f)


def test_revoked_token_stops_working_without_restart(team_vault: Path, tmp_path: Path) -> None:
    """Same defect class as formal/mcp-config-revocation-stale: the auth file is the owner of
    the permission, so a request that starts after a revocation is on disk must be refused."""
    f = tmp_path / "auth.yaml"

    def write(*users: tuple[str, str, str]) -> None:
        lines = "".join(f"  - {{ name: {n}, role: {r}, token_sha256: {h} }}\n" for n, r, h in users)
        f.write_text("allowed_hosts: [hub.team.example]\nusers:\n" + lines, "utf-8")
        f.chmod(0o600)

    write(("reader", "read", READ_HASH), ("writer", "write", WRITE_HASH))
    with TestClient(create_app(team_vault, serve_web=False, team=LiveTeamAuth.open(f))) as c:
        assert c.get("/api/notes", headers=R).status_code == 200
        assert c.get("/api/notes", headers=W).status_code == 200
        write(("writer", "read", WRITE_HASH))  # reader revoked, writer demoted
        assert c.get("/api/notes", headers=R).status_code == 401
        url = f"/api/review/promote/{PUBLIC_DRAFT}"
        assert c.post(url, headers={**W, **CLICK}).status_code == 403
        assert (team_vault / PUBLIC_DRAFT).is_file()
        # a broken or exposed file refuses everyone (fail-closed) until it is fixed
        f.write_text("users: [oops\n", "utf-8")
        assert c.get("/api/notes", headers=W).status_code == 503
        write(("writer", "read", WRITE_HASH))
        f.chmod(0o644)
        assert c.get("/api/notes", headers=W).status_code == 503
        f.unlink()
        assert c.get("/api/notes", headers=W).status_code == 503
        write(("writer", "read", WRITE_HASH))
        assert c.get("/api/notes", headers=W).status_code == 200
    with pytest.raises(TeamConfigError):
        LiveTeamAuth.open(tmp_path / "missing.yaml")


def test_failed_logins_are_throttled() -> None:
    t = FailureThrottle(limit=3, window=10.0)
    for i in range(3):
        assert not t.blocked("c", now=float(i))
        t.record("c", now=float(i))
    assert t.blocked("c", now=3.0) and not t.blocked("other", now=3.0)
    assert not t.blocked("c", now=20.0)  # the window passed


# ------------------------------------------------------------------ roles and the allow-list
def test_owner_operations_are_not_on_the_team_channel(team: TestClient, team_vault: Path) -> None:
    before = tree_hash(team_vault)
    for url in (
        "/api/doctor",
        "/api/guard",
        "/api/git/log",
        "/api/git/status",
        "/api/settings",
        "/api/obsidian",
        "/api/commons/candidates",
        "/api/metrics",
        "/api/docs",
        "/api/openapi.json",
    ):
        assert team.get(url, headers=W).status_code == 403, url
    for method, url, body in (
        ("put", "/api/settings", {"level": 3, "mcp": {"expose_confidential": True}}),
        ("put", "/api/packs/me.x", {"pack_yaml": "x"}),
        ("post", "/api/domains", {"id": "IR"}),
        ("post", "/api/onboarding", {"name": "x", "primary": "D1"}),
        ("post", "/api/obsidian/setup", {}),
        ("post", "/api/commons/publish/x.md", {"confirmed": True}),
    ):
        r = getattr(team, method)(url, headers={**W, **CLICK}, json=body)
        assert r.status_code == 403, url
    assert tree_hash(team_vault) == before
    assert route_role("DELETE", "/api/notes/x") is None and route_role("GET", "/api/x") is None


def test_read_role_cannot_write_and_write_role_can_review(
    team: TestClient, team_vault: Path
) -> None:
    assert team.get("/api/team/me", headers=R).json() == {"name": "reader", "role": "read"}
    before = tree_hash(team_vault)
    url = f"/api/review/promote/{PUBLIC_DRAFT}"
    assert team.post(url, headers={**R, **CLICK}).status_code == 403
    assert team.post("/api/patches/x.patch.md/apply", headers={**R, **CLICK}).status_code == 403
    assert tree_hash(team_vault) == before
    assert team.post(url, headers=W).status_code == 403  # still needs the click header (ADR-0009)
    n = team.get(f"/api/notes/{PUBLIC_DRAFT}", headers=W).json()
    r = team.post(url, headers={**W, **CLICK}, json={"digest": n["digest"]})
    assert r.status_code == 200, r.text
    assert (team_vault / r.json()["path"]).is_file()


# ------------------------------------------------------------------ confidentiality
def _all_text(team: TestClient, headers: dict[str, str]) -> str:
    out = []
    for url in (
        "/api/vault",
        "/api/stats",
        "/api/domains",
        "/api/notes?limit=500",
        "/api/notes?status=verified",
        "/api/search?q=WCET",
        f"/api/search?q={SECRET_WORD}",
        "/api/search?q=CAD",
        "/api/review",
        "/api/patches",
        "/api/packs",
        "/api/notes/10_Domains/D2/공개 노트.md",
    ):
        r = team.get(url, headers=headers)
        assert r.status_code == 200, (url, r.text)
        out.append(r.text)
    return "\n".join(out)


def test_confidential_notes_are_never_served(team: TestClient, team_vault: Path) -> None:
    for headers in (R, W):
        text = _all_text(team, headers)
        # (pack data such as the compose target "Agentic CAD PoC" is not a note and may appear)
        for needle in (
            SECRET_WORD,
            "기밀 설계 메모",
            "기밀 초안",
            "40_IP/candidates/",
            "Agentic CAD 검증",
            "인젝션 다층 가드",
        ):
            at = text.find(needle)
            assert at < 0, f"{needle!r} leaked: …{text[max(0, at - 120) : at + 60]}…"
        assert str(team_vault) not in text and "brian@example.org" not in text
        for ref in (CONF_IP, CONF_NOTE, CONF_DRAFT, "20261018-1000-conf-note"):
            r = team.get(f"/api/notes/{ref}", headers=headers)
            assert r.status_code == 404 and SECRET_WORD not in r.text
            # indistinguishable from a note that does not exist
            assert r.json()["detail"].startswith("note not found")
    # sanity: the same notes ARE in the Vault and visible to the owner in Personal mode
    with TestClient(create_app(team_vault, serve_web=False)) as personal:
        back = personal.get("/api/notes/10_Domains/D2/공개 노트.md").json()["backlinks"]
        assert CONF_NOTE in back  # …so the empty backlink list above was the filter at work
        assert SECRET_WORD in personal.get(f"/api/notes/{CONF_NOTE}").json()["body"]
        assert any(n["path"] == CONF_NOTE for n in personal.get("/api/notes?limit=500").json())
        assert any(d["path"] == CONF_DRAFT for d in personal.get("/api/review").json()["drafts"])


def test_confidential_drafts_cannot_be_reviewed_over_the_channel(
    team: TestClient, team_vault: Path
) -> None:
    before = tree_hash(team_vault)
    for action in ("promote", "reject"):
        r = team.post(f"/api/review/{action}/{CONF_DRAFT}", headers={**W, **CLICK}, json={})
        assert r.status_code == 404, r.text
    assert tree_hash(team_vault) == before


def test_reclassified_note_disappears_without_restart(team: TestClient, team_vault: Path) -> None:
    """Stale-read check (formal C6 class): a note made confidential while the Hub runs."""
    path = "10_Domains/D2/기밀을 가리키는 공개.md"
    assert team.get(f"/api/notes/{path}", headers=R).status_code == 200
    p = team_vault / path
    p.write_text(
        p.read_text("utf-8").replace("classification: internal", "classification: confidential"),
        "utf-8",
    )
    assert team.get(f"/api/notes/{path}", headers=R).status_code == 404
    assert path not in team.get("/api/notes?limit=500", headers=R).text


def test_assistant_context_excludes_confidential(
    team: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = team.app.state.assistant  # type: ignore[attr-defined]
    hits = assistant._retrieve(f"{SECRET_WORD} CAD 검증 루프 아이디어")
    assert all(h["classification"] != "confidential" for h in hits)
    assert not any(h["path"].startswith("40_IP/") or "기밀" in h["path"] for h in hits)
    assert SECRET_WORD not in json.dumps(hits, ensure_ascii=False)


def test_restricted_rule_is_fail_closed() -> None:
    assert restricted("40_IP/candidates/x.md", "public")
    assert restricted("10_Domains/D1/x.md", "confidential")
    assert restricted("10_Domains/D1/x.md", None)  # unknown classification
    assert not restricted("10_Domains/D1/x.md", "internal")
    assert not restricted("10_Domains/D1/40_IP.md", "public")


# ------------------------------------------------------------------ audit log, CSRF / CORS
def test_access_is_audited_without_tokens(team: TestClient, team_vault: Path) -> None:
    team.get("/api/notes", headers=R)
    team.get(f"/api/notes/{CONF_NOTE}", headers=W)
    team.get("/api/settings", headers=W)
    team.get("/api/vault")
    log = (team_vault / ACCESS_LOG).read_text(encoding="utf-8")
    events = [json.loads(line) for line in log.splitlines()]
    got = [(e["user"], e["role"], e["method"], e["path"], e["status"]) for e in events]
    assert ("reader", "read", "GET", "/api/notes", 200) in got
    assert ("writer", "write", "GET", "/api/settings", 403) in got
    assert (None, None, "GET", "/api/vault", 401) in got
    assert any(e["status"] == 404 and e["user"] == "writer" for e in events)
    assert READ_TOKEN not in log and WRITE_TOKEN not in log and READ_HASH not in log
    assert all(e["ts"] > 0 and "client" in e for e in events)
    # the log is runtime state: git-ignored, never part of a Vault commit
    ignored = subprocess.run(["git", "check-ignore", "-q", ACCESS_LOG], cwd=team_vault)
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=team_vault, capture_output=True, text=True
    ).stdout
    assert ignored.returncode == 0 or "hub-access.log" not in status


def test_host_origin_and_cors_defaults(team: TestClient) -> None:
    ok = team.get("/api/notes", headers={**R, "Host": "hub.team.example:8787"})
    assert ok.status_code == 200
    assert "access-control-allow-origin" not in {k.lower() for k in ok.headers}
    assert ok.headers["cache-control"] == "no-store"
    assert team.get("/api/notes", headers={**R, "Host": "evil.example"}).status_code == 403
    cross = team.get("/api/notes", headers={**R, "Origin": "https://evil.example"})
    assert cross.status_code == 403
    same = team.get("/api/notes", headers={**R, "Origin": "https://hub.team.example"})
    assert same.status_code == 200
    pre = team.options(
        "/api/notes",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert pre.status_code == 403 and "access-control-allow-origin" not in pre.headers


# ------------------------------------------------------------------ bind policy
def test_non_loopback_bind_needs_auth_hosts_and_tls(
    tmp_path: Path,
    team_vault: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MYELIN_HUB_AUTH_FILE", raising=False)
    for host in ("127.0.0.1", "localhost", "::1"):
        assert check_bind(host, None, tls=False, behind_tls_proxy=False) is None
    no_hosts = TeamAuth(AUTH.users)
    assert "authentication" in (check_bind("0.0.0.0", None, tls=True, behind_tls_proxy=False) or "")
    assert "allowed_hosts" in (
        check_bind("0.0.0.0", no_hosts, tls=True, behind_tls_proxy=False) or ""
    )
    assert "clear text" in (check_bind("10.0.0.5", AUTH, tls=False, behind_tls_proxy=False) or "")
    assert check_bind("10.0.0.5", AUTH, tls=True, behind_tls_proxy=False) is None
    assert check_bind("10.0.0.5", AUTH, tls=False, behind_tls_proxy=True) is None

    def boom(*a: object, **k: object) -> None:
        raise AssertionError("the server must not start")

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", boom)
    assert main(["--vault", str(team_vault), "--host", "0.0.0.0"]) == 2
    assert "without authentication" in capsys.readouterr().err
    auth = tmp_path / "auth.yaml"
    auth.write_text(
        f"allowed_hosts: [hub.team.example]\nusers:\n"
        f"  - {{ name: a, role: read, token_sha256: {READ_HASH} }}\n",
        "utf-8",
    )
    auth.chmod(0o600)
    args = ["--vault", str(team_vault), "--host", "0.0.0.0", "--auth-file", str(auth)]
    assert main(args) == 2 and "clear text" in capsys.readouterr().err
    assert main([*args, "--tls-cert", "c.pem"]) == 2
    capsys.readouterr()
    auth.chmod(0o644)
    assert main([*args, "--behind-tls-proxy"]) == 2 and "chmod 600" in capsys.readouterr().err
    auth.chmod(0o600)
    empty = tmp_path / "empty"
    empty.mkdir()
    assert (
        main(
            [
                "--vault",
                str(empty),
                "--host",
                "0.0.0.0",
                "--auth-file",
                str(auth),
                "--behind-tls-proxy",
            ]
        )
        == 2
    )
    assert "initialised Vault" in capsys.readouterr().err
    # accepted configurations reach uvicorn.run
    started: list[dict[str, object]] = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: started.append(kw))
    assert main([*args, "--behind-tls-proxy"]) == 0
    assert started[-1]["host"] == "0.0.0.0" and "team mode" in capsys.readouterr().out
    assert main(["--vault", str(team_vault)]) == 0  # personal mode: no flags needed
    assert started[-1]["host"] == "127.0.0.1" and "personal mode" in capsys.readouterr().out


def test_new_token_prints_hash_entry(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--new-token", "alice", "--role", "write"]) == 0
    out = capsys.readouterr().out
    token = next(ln.strip() for ln in out.splitlines() if ln.strip().startswith("mxt_"))
    assert f"token_sha256: {token_hash(token)}" in out and "role: write" in out
    assert main(["--new-token", "bad name"]) == 2


# ------------------------------------------------------------------ personal mode unchanged
def test_loopback_personal_mode_is_unchanged(client: TestClient, vault_root: Path) -> None:
    assert client.app.state.team is None  # type: ignore[attr-defined]
    for url in ALL_GETS:
        if url == "/api/team/me":
            assert client.get(url).status_code == 404
            continue
        assert client.get(url).status_code == 200, url  # no token needed on loopback
    h = client.get("/api/health").json()
    assert h["root"] == str(vault_root) and "mode" not in h
    n = client.get(f"/api/notes/{CONF_IP}").json()
    assert n["classification"] == "confidential" and n["body"]  # the owner sees their own notes
    assert client.get("/api/vault").json()["root"] == str(vault_root)
    assert client.get("/api/notes", headers={"Host": "hub.team.example"}).status_code == 403
    assert not (vault_root / ACCESS_LOG).exists()  # no audit log in personal mode
    assert shutil.which("git") and REPO_ROOT.is_dir()
