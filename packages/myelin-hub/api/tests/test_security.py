"""Hub 보안 경계 — localhost 전용, 사용자 행위 없는 쓰기 0."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from myelin_core.errors import MyelinError
from myelin_hub_api import cli
from myelin_hub_api.app import _hostname, cookie_name, create_app
from myelin_hub_api.service import HubService

Snap = Callable[[Path], dict[str, str]]

# 사람의 클릭으로만 호출되는 쓰기 API. 새 POST 를 추가하면 여기에 등록해야 테스트가 통과한다.
WRITE_ROUTES = {
    "/api/onboarding/apply",
    "/api/review/promote",
    "/api/review/reject",
    "/api/settings",
    "/api/git/init",
    "/api/domains/add",
    "/api/commons/propose",
    "/api/commons/push",
    "/api/patches/apply",
    "/api/patches/reject",
}
PURE_POSTS = {"/api/onboarding/preview", "/api/packs/validate"}


def _get_paths(app_client: TestClient) -> list[str]:
    paths = []
    for route in app_client.app.routes:  # type: ignore[attr-defined]
        if isinstance(route, APIRoute) and "GET" in route.methods:
            paths.append(
                route.path.replace("{name}", "brian.physical-ai")
                .replace("{rest:path}", "anything")
                .replace("/api/note", "/api/note?path=00_Inbox/ai-drafts/x.md")
                .replace("/api/commons/check", "/api/commons/check?path=30_Resources/x.md")
                .replace("/api/patches/preview", "/api/patches/preview?path=_patches/p.patch.md")
            )
    return paths


def test_route_inventory(client: TestClient) -> None:
    posts = {
        r.path
        for r in client.app.routes  # type: ignore[attr-defined]
        if isinstance(r, APIRoute) and r.methods - {"GET", "HEAD"}
    }
    assert posts == WRITE_ROUTES | PURE_POSTS


@pytest.mark.parametrize(
    ("host", "status"),
    [
        ("127.0.0.1:8765", 200),
        ("localhost:8765", 200),
        ("[::1]:8765", 200),
        ("evil.example:8765", 403),
        ("127.0.0.1.nip.io", 403),
        ("", 403),
    ],
)
def test_host_header(client: TestClient, host: str, status: int) -> None:
    assert client.get("/api/state", headers={"host": host}).status_code == status


def test_write_needs_intent_origin_and_json(
    client: TestClient, act: dict[str, str], onboard_body: dict[str, object], target: Path
) -> None:
    url = "/api/onboarding/apply"
    no_intent = {"Origin": act["Origin"]}
    assert client.post(url, json=onboard_body, headers=no_intent).status_code == 403
    no_origin = {"X-Myelin-Intent": "user"}
    assert client.post(url, json=onboard_body, headers=no_origin).status_code == 403
    foreign = {**act, "Origin": "http://evil.example"}
    assert client.post(url, json=onboard_body, headers=foreign).status_code == 403
    other_port = {**act, "Origin": "http://127.0.0.1:9999"}
    assert client.post(url, json=onboard_body, headers=other_port).status_code == 403
    wrong_intent = {**act, "X-Myelin-Intent": "script"}
    assert client.post(url, json=onboard_body, headers=wrong_intent).status_code == 403
    form = client.post(url, content="owner=x", headers={**act, "content-type": "text/plain"})
    assert form.status_code == 415
    assert client.put(url, json=onboard_body, headers=act).status_code == 405
    assert client.delete(url, headers=act).status_code == 405
    assert not target.exists()  # 거부된 요청은 아무것도 쓰지 않았다


def test_security_headers(client: TestClient) -> None:
    res = client.get("/api/state")
    assert "frame-ancestors 'none'" in res.headers["content-security-policy"]
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["cache-control"] == "no-store"
    assert "access-control-allow-origin" not in res.headers
    assert client.get("/openapi.json").headers["content-type"].startswith("text/html")


def test_unknown_api(client: TestClient) -> None:
    res = client.get("/api/nope")
    assert res.status_code == 404 and "없는 API" in res.json()["error"]


def test_no_passive_writes_before_onboarding(
    client: TestClient, target: Path, snapshot: Snap
) -> None:
    for path in _get_paths(client):
        client.get(path)
    assert not target.exists()


def test_no_passive_writes_on_reads(
    client: TestClient,
    onboarded: Path,
    put: Callable[[str, str], str],
    make_draft: Callable[..., str],
    snapshot: Snap,
    act: dict[str, str],
    onboard_body: dict[str, object],
) -> None:
    put("00_Inbox/ai-drafts/x.md", make_draft())
    put("00_Inbox/raw.md", "frontmatter 없는 메모\n")
    put(
        "_patches/p.patch.md",
        "---\npatch: 1\ntarget: 10_Domains/AI-ML-AX/_MOC.md\nkind: append\norigin: claude\n"
        "skill: link\ncreated: 2026-10-18\nrationale: r\nstatus: proposed\n---\n## append\n- x\n",
    )
    before = snapshot(onboarded)
    for _ in range(2):
        for path in _get_paths(client):
            client.get(path)
    # 계산만 하는 POST 와 거부된 쓰기도 Vault를 바꾸지 않는다
    client.post("/api/onboarding/preview", json=onboard_body, headers=act)
    client.post("/api/packs/validate", json={"yaml": "pack: x\n"}, headers=act)
    client.post("/api/review/promote", json={"path": "00_Inbox/ai-drafts/x.md", "id": "w"})
    assert snapshot(onboarded) == before


# ── CLI ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.0.10", "::", "example.com", "10.0.0.1"])
def test_cli_refuses_public_bind(
    tmp_path: Path, host: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["--vault", str(tmp_path / "v"), "--host", host]) == 2
    assert "localhost 전용" in capsys.readouterr().err
    assert not (tmp_path / "v").exists()


def test_cli_runs_on_loopback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import uvicorn

    seen: dict[str, object] = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(kw))
    opened: list[str] = []
    monkeypatch.setattr(cli.webbrowser, "open", opened.append)
    assert cli.main(["--vault", str(tmp_path / "v"), "--port", "9001", "--open"]) == 0
    assert seen == {"host": "127.0.0.1", "port": 9001, "log_level": "warning"}
    assert len(opened) == 1 and opened[0].startswith("http://127.0.0.1:9001/?token=")
    assert not (tmp_path / "v").exists()  # 시작만으로는 쓰지 않는다
    assert cli._is_loopback("::1") and cli._is_loopback("localhost")


def test_cli_missing_packs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("MYELIN_PACKS", raising=False)

    def nowhere(*_: object, **__: object) -> Path:
        raise MyelinError("Domain Pack을 찾을 수 없습니다")

    monkeypatch.setattr(cli, "find_packs_dir", nowhere)
    assert cli.main(["--vault", str(tmp_path / "v")]) == 1
    assert "Pack" in capsys.readouterr().err


TOKEN = "test-session-token-0123456789"


def test_session_token(service: HubService) -> None:
    """같은 컴퓨터의 다른 사용자·프로세스는 토큰 없이 /api 를 읽지 못한다 (STRIDE I5)."""
    anon = TestClient(create_app(service, token=TOKEN), base_url="http://127.0.0.1:8765")
    res = anon.get("/api/state")
    assert res.status_code == 401 and "?token" in res.json()["error"]
    anon.cookies.set(cookie_name(TOKEN), "wrong-token-value")
    assert anon.get("/api/state").status_code == 401
    anon.cookies.clear()
    assert anon.get("/?token=nope", follow_redirects=False).status_code == 401
    login = anon.get("/review?token=" + TOKEN, follow_redirects=False)
    assert login.status_code == 303 and login.headers["location"] == "/review"
    set_cookie = login.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=strict" in set_cookie
    assert anon.get("/api/state").status_code == 200  # 쿠키로 계속
    assert anon.get("/").status_code == 200  # 정적 화면은 토큰 없이도 (데이터 없음)
    with pytest.raises(ValueError):
        create_app(service, token="short")
    assert cookie_name("a" * 20) != cookie_name("b" * 20)


def test_hostname_parsing() -> None:
    assert _hostname("127.0.0.1:8765") == "127.0.0.1"
    assert _hostname("[::1]:8765") == "::1"
    assert _hostname("localhost") == "localhost"


def test_web_serving(tmp_path: Path, service: HubService) -> None:
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    (web / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (web / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    c = TestClient(create_app(service, token=TOKEN, web_dir=web), base_url="http://127.0.0.1:8765")
    assert "id=root" in c.get("/review").text  # SPA fallback
    assert c.get("/assets/app.js").text == "console.log(1)"
    assert c.get("/favicon.svg").text == "<svg/>"
    assert "secret" not in c.get("/..%2Fsecret.txt").text
    bare = TestClient(
        create_app(service, token=TOKEN, web_dir=tmp_path / "none"), base_url="http://127.0.0.1"
    )
    assert "빌드되지 않았습니다" in bare.get("/").text
    assert cli.default_web_dir().name in ("dist", "web")


def test_web_has_no_html_sinks() -> None:
    """노트 본문 등 Vault 내용은 텍스트로만 렌더링한다 (저장형 XSS 차단, STRIDE I7)."""
    root = Path(__file__).resolve().parents[2] / "web" / "src"
    sinks = (
        "dangerouslySetInnerHTML",
        "innerHTML",
        "outerHTML",
        "eval(",
        "new Function",
        "style={",
    )
    found = [
        f"{p.name}: {s}"
        for p in root.rglob("*.ts*")
        for s in sinks
        if s in p.read_text(encoding="utf-8")
    ]
    assert found == []
