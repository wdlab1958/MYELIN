"""Hub e2e — 실제 uvicorn 서버 + 빌드된 웹 + Chromium (Playwright).

빌드(`packages/myelin-hub/web/dist`)나 브라우저가 없으면 skip 한다.
Gate는 MYELIN_E2E_REQUIRED=1 로 실행해 skip 대신 실패하게 한다.
스크린샷은 MYELIN_SHOTS=1(P6) 또는 MYELIN_SHOTS=P7 일 때 docs/reports/<Phase>/ 에 저장한다.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "packages/myelin-hub/web/dist"


def _unavailable(reason: str) -> None:
    if os.environ.get("MYELIN_E2E_REQUIRED") == "1":
        pytest.fail(f"e2e 필수 조건 없음: {reason}")
    pytest.skip(reason)


@dataclass
class Hub:
    url: str
    vault: Path
    shots: Path
    token: str


def tree(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        p.relative_to(root).as_posix(): (
            hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "<dir>"
        )
        for p in sorted(root.rglob("*"))
    }


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def hub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Hub]:
    if not (WEB / "index.html").is_file():
        _unavailable("웹 빌드 없음 — cd packages/myelin-hub/web && npm ci && npm run build")
    import uvicorn

    from myelin_core.onboarding import find_packs_dir
    from myelin_hub_api.app import create_app
    from myelin_hub_api.service import HubService

    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "no-global-gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    vault = tmp_path / "MyVault"
    port = _free_port()
    token = secrets.token_urlsafe(24)
    app = create_app(HubService(vault, find_packs_dir()), token=token, web_dir=WEB)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:
            pytest.fail("Hub 서버가 시작되지 않았습니다")
        time.sleep(0.05)
    flag = os.environ.get("MYELIN_SHOTS", "")
    phase = flag if flag.startswith("P") else "P6"
    shots = ROOT / "docs/reports" / phase if flag else tmp_path / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    try:
        yield Hub(f"http://127.0.0.1:{port}", vault, shots, token)
    finally:
        server.should_exit = True
        thread.join(timeout=10)


@pytest.fixture
def page(hub: Hub) -> Iterator[object]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        _unavailable("playwright 없음")
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as exc:  # 브라우저 미설치
            _unavailable(f"Chromium 실행 불가: {exc}")
        context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ko-KR")
        pg = context.new_page()
        pg.goto(f"{hub.url}/?token={hub.token}")  # 터미널 링크로 여는 것과 같은 로그인
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        yield pg
        browser.close()
        assert errors == [], f"브라우저 JS 오류: {errors}"


@pytest.fixture
def snapshot() -> object:
    return tree
