"""MYELIN Hub HTTP 계층 (FastAPI). localhost 전용 (ADR-0008).

방어 (브라우저가 열려 있는 동안 다른 웹사이트가 Hub를 조작하지 못하게):
1. Host 헤더가 loopback 이름이 아니면 403 — DNS rebinding 차단.
2. 쓰기는 POST만. POST는 `X-Myelin-Intent: user` 헤더 + 같은 출처의 `Origin` + JSON 본문이
   모두 있어야 한다.
   커스텀 헤더가 있으면 다른 출처의 요청은 CORS preflight에서 막히고, Hub는 CORS를 열지 않는다.
3. GET은 Vault에 아무것도 쓰지 않는다 (테스트·Gate가 Vault 해시로 확인).
4. 세션 토큰: 시작할 때 만든 임의 토큰을 터미널 링크(`/?token=…`)로만 받는다. 브라우저는 그것을
   HttpOnly·SameSite=Strict 쿠키로 바꿔 쓰고, `/api/*` 는 쿠키가 없으면 401 — 같은 컴퓨터의 다른
   OS 사용자·프로세스가 localhost 포트로 노트를 읽지 못하게 (STRIDE I5).
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from myelin_core.commons import CommonsError
from myelin_core.config import ConfigError
from myelin_core.errors import MyelinError, PackError
from myelin_core.gitops import GitError
from myelin_core.onboarding import InitRequest, OnboardingError
from myelin_core.patches import PatchError
from myelin_core.review import ReviewError
from myelin_hub_api import __version__
from myelin_hub_api.service import HubService, NotInitialized

LOOPBACK_NAMES = frozenset({"127.0.0.1", "localhost", "::1"})
INTENT_HEADER = "x-myelin-intent"
INTENT_VALUE = "user"
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
    "form-action 'none'"
)
STATUS: tuple[tuple[type[MyelinError], int], ...] = (
    (NotInitialized, 409),
    (ReviewError, 409),
    (GitError, 409),
    (OnboardingError, 400),
    (ConfigError, 422),
    (PackError, 404),
    (CommonsError, 409),
    (PatchError, 409),
)


# ── 요청 본문 ────────────────────────────────────────────────────────────
class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OnboardingBody(_Body):
    owner: Annotated[str, Field(max_length=80)]
    packs: Annotated[list[str], Field(max_length=8)] = []
    primary: Annotated[str, Field(max_length=32)]
    research: Annotated[str | None, Field(max_length=32)] = None
    growth: Annotated[str | None, Field(max_length=32)] = None
    extra: Annotated[str | None, Field(max_length=32)] = None
    level: Annotated[int, Field(ge=0, le=3)] = 1
    language: Annotated[str, Field(max_length=5)] = "ko"
    git: bool = True

    def request(self) -> InitRequest:
        return InitRequest(
            owner=self.owner,
            packs=tuple(self.packs),
            primary=self.primary,
            research=self.research or None,
            growth=self.growth or None,
            extra=self.extra or None,
            level=self.level,
            language=self.language,
        )


class ReviewBody(_Body):
    path: Annotated[str, Field(max_length=512)]
    id: Annotated[str, Field(max_length=128)]


class SettingsBody(_Body):
    level: Annotated[int | None, Field(ge=0, le=3)] = None
    mcp_write_drafts: bool | None = None
    metrics_opt_in: bool | None = None


class PatchBody(_Body):
    path: Annotated[str, Field(max_length=512)]
    digest: Annotated[str, Field(max_length=64)] = ""


class ProposeBody(_Body):
    path: Annotated[str, Field(max_length=512)]
    id: Annotated[str, Field(max_length=128)]
    confirmed: Annotated[list[str], Field(max_length=16)] = []


class PushBody(_Body):
    branch: Annotated[str, Field(max_length=200)]
    confirm: bool = False


class AddDomainBody(_Body):
    domain: Annotated[str, Field(max_length=32)]
    role: Annotated[str, Field(max_length=16)]
    pack: Annotated[str | None, Field(max_length=80)] = None


class PackTextBody(_Body):
    yaml: Annotated[str, Field(max_length=200_000)]


class Empty(_Body):
    pass


# ── 앱 ───────────────────────────────────────────────────────────────────
def _hostname(host_header: str) -> str:
    if host_header.startswith("["):
        return host_header[1 : host_header.find("]")]
    return host_header.rsplit(":", 1)[0] if host_header.count(":") == 1 else host_header


def _deny(status: int, msg: str) -> JSONResponse:
    return JSONResponse({"error": msg, "issues": []}, status_code=status)


def cookie_name(token: str) -> str:
    """Hub 인스턴스마다 다른 쿠키 이름 — 포트가 다른 Hub 둘이 서로의 쿠키를 덮지 않게."""
    return "myelin_" + hashlib.sha256(token.encode()).hexdigest()[:10]


def create_app(
    service: HubService,
    *,
    token: str,
    web_dir: Path | None = None,
    allowed_hosts: frozenset[str] = LOOPBACK_NAMES,
) -> FastAPI:
    if len(token) < 16:
        raise ValueError("session token too short")
    cookie = cookie_name(token)
    app = FastAPI(
        title="MYELIN Hub", version=__version__, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.service = service

    @app.middleware("http")
    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        host = request.headers.get("host", "")
        if _hostname(host) not in allowed_hosts:
            return _deny(403, "허용되지 않은 Host — Hub는 localhost 전용입니다")
        offered = request.query_params.get("token")
        if offered is not None:
            if not hmac.compare_digest(offered.encode(), token.encode()):
                return _deny(401, "토큰이 맞지 않습니다 — 터미널에 출력된 링크로 여세요")
            login = RedirectResponse(request.url.path or "/", status_code=303)
            login.set_cookie(cookie, token, httponly=True, samesite="strict", path="/")
            login.headers["Cache-Control"] = "no-store"
            login.headers["Referrer-Policy"] = "no-referrer"
            return login
        if request.url.path.startswith("/api/"):
            got = request.cookies.get(cookie, "")
            if not hmac.compare_digest(got.encode(), token.encode()):
                return _deny(401, "세션이 없습니다 — 터미널에 출력된 링크(?token=…)로 여세요")
        if request.method not in ("GET", "HEAD"):
            if request.method != "POST":
                return _deny(405, "허용되지 않은 메서드")
            if request.headers.get(INTENT_HEADER) != INTENT_VALUE:
                return _deny(403, "사용자 행위 표시가 없는 쓰기 요청")
            origin = request.headers.get("origin")
            if origin is None or urlsplit(origin).netloc != host:
                return _deny(403, "다른 출처의 쓰기 요청")
            if not request.headers.get("content-type", "").startswith("application/json"):
                return _deny(415, "JSON 본문만 받습니다")
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = CSP
        return response

    @app.exception_handler(MyelinError)
    async def _myelin_error(_: Request, exc: MyelinError) -> JSONResponse:
        status = next((code for cls, code in STATUS if isinstance(exc, cls)), 400)
        body = {"error": exc.message, "issues": [asdict(i) for i in exc.issues]}
        return JSONResponse(body, status_code=status)

    svc = service

    # 읽기
    @app.get("/api/state")
    def state() -> dict[str, Any]:
        return {**svc.state(), "version": __version__}

    @app.get("/api/dashboard")
    def dashboard() -> dict[str, Any]:
        return svc.dashboard()

    @app.get("/api/domains")
    def domains() -> dict[str, Any]:
        return svc.domains()

    @app.get("/api/review")
    def review() -> list[dict[str, Any]]:
        return svc.review()

    @app.get("/api/note")
    def note(path: Annotated[str, Query(max_length=512)]) -> dict[str, Any]:
        return svc.note(path)

    @app.get("/api/packs")
    def packs() -> list[dict[str, Any]]:
        return svc.packs()

    @app.get("/api/packs/{name}/source")
    def pack_source(name: str) -> dict[str, Any]:
        return svc.pack_source(name)

    @app.get("/api/settings")
    def settings() -> dict[str, Any]:
        return svc.settings()

    @app.get("/api/patches")
    def patch_list() -> list[dict[str, Any]]:
        return svc.patches()

    @app.get("/api/patches/preview")
    def patch_preview(path: Annotated[str, Query(max_length=512)]) -> dict[str, Any]:
        return svc.patch_preview(path)

    @app.get("/api/commons")
    def commons_state() -> dict[str, Any]:
        return svc.commons()

    @app.get("/api/commons/check")
    def commons_check(path: Annotated[str, Query(max_length=512)]) -> dict[str, Any]:
        return svc.commons_check(path)

    @app.get("/api/onboarding")
    def onboarding() -> dict[str, Any]:
        return svc.onboarding()

    # 계산만 하는 POST (본문이 필요해서 POST — 쓰지 않는다)
    @app.post("/api/onboarding/preview")
    def onboarding_preview(body: OnboardingBody) -> dict[str, Any]:
        return svc.onboarding_preview(body.request())

    @app.post("/api/packs/validate")
    def validate_pack(body: PackTextBody) -> dict[str, Any]:
        return HubService.validate_pack(body.yaml)

    # 쓰기 — 사람의 클릭
    @app.post("/api/onboarding/apply")
    def onboarding_apply(body: OnboardingBody) -> dict[str, Any]:
        return svc.do_onboarding(body.request(), start_git=body.git)

    @app.post("/api/review/promote")
    def promote(body: ReviewBody) -> dict[str, Any]:
        return svc.do_promote(body.path, body.id)

    @app.post("/api/review/reject")
    def reject(body: ReviewBody) -> dict[str, Any]:
        return svc.do_reject(body.path, body.id)

    @app.post("/api/settings")
    def update_settings(body: SettingsBody) -> dict[str, Any]:
        return svc.do_update_settings(
            level=body.level,
            write_drafts=body.mcp_write_drafts,
            metrics_opt_in=body.metrics_opt_in,
        )

    @app.post("/api/patches/apply")
    def patch_apply(body: PatchBody) -> dict[str, Any]:
        return svc.do_patch_apply(body.path, body.digest)

    @app.post("/api/patches/reject")
    def patch_reject(body: PatchBody) -> dict[str, Any]:
        return svc.do_patch_reject(body.path)

    @app.post("/api/commons/propose")
    def commons_propose(body: ProposeBody) -> dict[str, Any]:
        return svc.do_commons_propose(body.path, body.id, body.confirmed)

    @app.post("/api/commons/push")
    def commons_push(body: PushBody) -> Any:
        if not body.confirm:
            return _deny(400, "push 확인이 없습니다 — 노트가 조직 원격으로 나갑니다")
        return svc.do_commons_push(body.branch)

    @app.post("/api/git/init")
    def git_init(_: Empty) -> dict[str, Any]:
        return svc.do_git_init()

    @app.post("/api/domains/add")
    def add_domain(body: AddDomainBody) -> dict[str, Any]:
        return svc.do_add_domain(body.domain, body.role, body.pack)

    @app.get("/api/{rest:path}")
    def api_not_found(rest: str) -> JSONResponse:
        return _deny(404, f"없는 API: /api/{rest}")

    _mount_web(app, web_dir)
    return app


NO_WEB = """<!doctype html><html lang="ko"><meta charset="utf-8"><title>MYELIN Hub</title>
<body><h1>MYELIN Hub</h1><p>웹 화면이 빌드되지 않았습니다.
<code>cd packages/myelin-hub/web &amp;&amp; npm ci &amp;&amp; npm run build</code></p>
</body></html>"""


def _mount_web(app: FastAPI, web_dir: Path | None) -> None:
    index = web_dir / "index.html" if web_dir else None
    if web_dir is None or index is None or not index.is_file():

        @app.get("/{rest:path}", include_in_schema=False)
        def no_web(rest: str) -> HTMLResponse:
            return HTMLResponse(NO_WEB)

        return

    if (web_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=web_dir / "assets"), name="assets")

    @app.get("/{rest:path}", include_in_schema=False)
    def spa(rest: str) -> FileResponse:
        candidate = (web_dir / rest).resolve()
        if rest and candidate.is_file() and candidate.is_relative_to(web_dir.resolve()):
            return FileResponse(candidate)
        return FileResponse(index)
