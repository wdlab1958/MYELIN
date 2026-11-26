"""MYELIN Hub API — FastAPI app factory (정본 §2.3 MYELIN Hub, §P6).

- Personal mode (default): binds to localhost only (see __main__), no auth (정본 §4.4).
- Team mode (optional, ADR-0016): `create_app(..., team=TeamAuth)` — bearer-token auth on every
  `/api/*` route, read/write roles on a fixed allow-list of routes, confidential notes never
  served, access audit log. See `myelin_hub_api.team`.
- Reads are GET and never write. Writes are POST/PUT and require the `X-Myelin-Intent: user-click`
  header, which only the Hub UI sets from a click handler (ADR-0009). Everything else is 403.
- Serves the built web UI from packages/myelin-hub/web/dist when present.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from myelin_core.product import PRODUCT_NAME
from myelin_core.schema.frontmatter import DOMAIN_ID_RE
from myelin_hub_api import __version__
from myelin_hub_api.assistant import Assistant
from myelin_hub_api.service import HubError, HubService
from myelin_hub_api.team import (
    AccessLog,
    FailureThrottle,
    LiveTeamAuth,
    TeamAuth,
    TeamConfigError,
    TeamUser,
    bearer,
    restricted,
    route_role,
)

INTENT_HEADER = "x-myelin-intent"
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1", "testserver"}


def _host_only(value: str) -> str:
    v = value.strip().lower()
    if v.startswith("["):  # [::1]:port
        return v.split("]")[0] + "]"
    return v.rsplit(":", 1)[0] if v.count(":") == 1 else v


class HostOriginGuard(BaseHTTPMiddleware):
    """Threat model T08: refuse requests whose Host is not loopback (DNS rebinding) and any
    browser request whose Origin is not loopback (cross-site). Non-browser clients send no
    Origin. Team mode adds the auth file's `allowed_hosts` to both checks — never a wildcard,
    and no CORS header is ever sent."""

    def __init__(self, app: Any, extra_hosts: Callable[[], frozenset[str]] | None = None) -> None:
        super().__init__(app)
        self.extra_hosts = extra_hosts

    @property
    def hosts(self) -> set[str]:
        if self.extra_hosts is None:
            return LOOPBACK_HOSTS
        try:
            return LOOPBACK_HOSTS | set(self.extra_hosts())
        except TeamConfigError:
            return LOOPBACK_HOSTS  # TeamGate answers 503 for the broken auth file

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        host = _host_only(request.headers.get("host", ""))
        if host not in self.hosts:
            return JSONResponse(
                {"detail": f"{PRODUCT_NAME} Hub does not serve this Host ({host!r})"},
                status_code=403,
            )
        origin = request.headers.get("origin")
        if origin:
            o = origin.lower()
            ohost = _host_only(o.split("://", 1)[-1]) if "://" in o else o
            if ohost not in self.hosts:
                return JSONResponse(
                    {"detail": "cross-origin requests are refused"}, status_code=403
                )
        return await call_next(request)


class TeamGate(BaseHTTPMiddleware):
    """Team mode (ADR-0016): authenticate, authorise and audit every `/api/*` request.

    Order: throttle → bearer token (401) → route allow-list (403) → role (403) → handler.
    `/api/health` stays open (a liveness probe) but says nothing about the Vault."""

    def __init__(self, app: Any, auth: Callable[[], TeamAuth], log: AccessLog) -> None:
        super().__init__(app)
        self.auth, self.log, self.throttle = auth, log, FailureThrottle()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path, method = request.url.path, request.method
        if not path.startswith("/api/") or path == "/api/health":
            return await call_next(request)
        client = request.client.host if request.client else "?"

        def deny(status: int, detail: str, user: TeamUser | None = None) -> Response:
            self.log.write(
                user=user.name if user else None,
                role=user.role if user else None,
                method=method,
                path=path,
                status=status,
                client=client,
            )
            headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
            return JSONResponse({"detail": detail}, status_code=status, headers=headers)

        if self.throttle.blocked(client):
            return deny(429, "too many failed authentication attempts — try again later")
        try:
            auth = self.auth()  # re-read when the file changed: revocation needs no restart
        except TeamConfigError:
            return deny(503, "team auth file is unreadable or invalid — refusing all requests")
        user = auth.authenticate(bearer(request.headers.get("authorization")))
        if user is None:
            self.throttle.record(client)
            return deny(401, "team mode: a valid `Authorization: Bearer <token>` is required")
        need = route_role(method, path)
        if need is None:
            return deny(403, "this operation is not available over the team channel", user)
        if not user.allows(need):
            return deny(403, f"role {user.role!r} may not perform this operation", user)
        request.state.team_user = user
        response = await call_next(request)
        self.log.write(
            user=user.name,
            role=user.role,
            method=method,
            path=path,
            status=response.status_code,
            client=client,
        )
        response.headers["Cache-Control"] = "no-store"
        return response


INTENT_VALUE = "user-click"
WEB_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"


class PromoteBody(BaseModel):
    domain: str | None = None
    # from GET /api/notes/{draft} ("내용 읽기"); the draft changed since → 409 (formal F4)
    digest: str | None = None
    # the reviewer saw the customer-information guard flags (code block / IP / internal URL)
    guard_ack: bool = False


class RejectBody(BaseModel):
    reason: str = ""


class ApplyBody(BaseModel):
    digest: str | None = None  # from GET /api/patches/{name}/preview; mismatch → 409


class PackBody(BaseModel):
    pack_yaml: str = Field(min_length=1)
    # registry pack whose sidecar files are copied along ("개인 Pack 으로 복사")
    copy_from: str | None = None


class PublishBody(BaseModel):
    confirmed: bool = False  # the UI's '비식별 확인' checkbox
    push: bool = False  # git push -u origin publish/<id> (origin added from commons.remote)
    pr: bool = False  # gh pr create (needs push; best effort — see service.commons_publish)


class CustomDomain(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=80)
    description: str = ""
    accent: str = "violet"
    sub_mocs: list[str] = Field(default_factory=list, max_length=12)


class AssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AssistantBody(BaseModel):
    """우측 하단 도움말 챗봇의 대화. 마지막 메시지는 user (service 가 검사)."""

    messages: list[AssistantMessage] = Field(min_length=1, max_length=40)


class AddDomainBody(BaseModel):
    """Domain Packs 화면의 'Domain 추가' 클릭 (ADR-0015). id 는 Pack 에 선언된 Domain."""

    id: str = Field(pattern=DOMAIN_ID_RE.pattern)
    pack: str | None = Field(default=None, max_length=120)


class OnboardBody(BaseModel):
    name: str = Field(min_length=1)
    team: str = ""
    email: str = ""
    primary: str
    research: str | None = None
    growth: str | None = None
    packs: list[str] = Field(default_factory=list)
    level: int = Field(default=1, ge=0, le=3)
    language: str = "ko"
    custom_domains: list[CustomDomain] = Field(default_factory=list, max_length=4)


def _etag_value(header: str | None) -> str | None:
    """`If-Match: "abc"` / `W/"abc"` → `abc`; absent or `*` → None (no precondition)."""
    if header is None:
        return None
    v = header.strip()
    if v.startswith("W/"):
        v = v[2:]
    v = v.strip('"')
    return None if v in ("", "*") else v


def require_user_click(x_myelin_intent: str | None = Header(default=None)) -> None:
    """Writes must come from an explicit user click in the Hub UI (ADR-0009)."""
    if x_myelin_intent != INTENT_VALUE:
        raise HTTPException(
            403, "write actions require the X-Myelin-Intent: user-click header (UI click only)"
        )


def create_app(
    vault_root: Path,
    *,
    serve_web: bool = True,
    team: TeamAuth | LiveTeamAuth | None = None,
) -> FastAPI:
    svc = HubService.open(Path(vault_root))
    app = FastAPI(
        title=f"{PRODUCT_NAME} Hub",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.service = svc
    assistant = Assistant(svc)
    app.state.assistant = assistant
    app.state.team = team
    if team is not None:
        # confidential notes never reach the assistant's context on the team channel either
        assistant.force_external = True
        current: Callable[[], TeamAuth] = (
            team.current if isinstance(team, LiveTeamAuth) else (lambda: team)
        )
        app.add_middleware(TeamGate, auth=current, log=AccessLog(svc.root))
        # added last = outermost: Host/Origin are checked before anything else
        app.add_middleware(HostOriginGuard, extra_hosts=lambda: current().allowed_hosts)
    else:
        app.add_middleware(HostOriginGuard)

    # ------------------------------------------------------------ team channel confidentiality
    def hidden(path: str, classification: str | None = None) -> bool:
        """Team mode only: must this note stay off the channel? (rule shared with MCP)"""
        if team is None:
            return False
        if classification is None and svc.index is not None:
            n = svc.index.get(path)
            classification = n.classification if n is not None else None
        return restricted(path, classification)

    def visible(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if team is None:
            return rows
        return [r for r in rows if not hidden(str(r.get("path", "")), r.get("classification"))]

    def gate_ref(ref: str) -> None:
        """404 — the same answer as for a note that does not exist."""
        if team is None:
            return
        idx = svc.index
        n = idx.get(ref) if idx is not None else None
        try:
            path = n.path if n is not None else svc._rel(ref)
        except HubError:
            raise HTTPException(404, f"note not found: {ref}") from None
        if hidden(path, n.classification if n is not None else None):
            raise HTTPException(404, f"note not found: {ref}")

    def gate_patch(name: str) -> None:
        if team is None:
            return
        try:
            target = str(svc.patch_preview(name).get("target") or "")
        except HubError:
            raise HTTPException(404, f"patch not found: {name}") from None
        if not target or hidden(target):
            raise HTTPException(404, f"patch not found: {name}")

    @app.exception_handler(HubError)
    async def _hub_error(_: Request, exc: HubError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=exc.status)

    @app.exception_handler(OSError)
    async def _os_error(_: Request, exc: OSError) -> JSONResponse:
        # read-only Vault, ENAMETOOLONG, disk errors … → a clean error with detail, never a bare 500
        return JSONResponse(
            {"detail": f"filesystem error: {type(exc).__name__}: {exc}"}, status_code=500
        )

    def s() -> HubService:
        svc.index and svc.index.refresh()
        return svc

    # ---------------------------------------------------------------- reads
    @app.get("/api/health")
    def health() -> dict[str, Any]:
        if team is not None:  # unauthenticated in team mode: liveness only
            return {"ok": True, "version": __version__, "mode": "team"}
        return {
            "ok": True,
            "version": __version__,
            "ready": svc.ready,
            "error": svc.config_error,
            "root": str(svc.root),
        }

    @app.get("/api/vault")
    def vault() -> dict[str, Any]:
        d = svc.summary()
        if team is not None:
            # no server paths, no file names of uncommitted notes, no owner e-mail
            d.pop("commons", None)
            if "git" in d:
                d["git"] = {k: d["git"].get(k) for k in ("repo", "clean")}
            if "owner" in d:
                d["owner"] = {
                    "name": d["owner"].get("name", ""),
                    "team": d["owner"].get("team", ""),
                }
            d["root"] = ""
            d["mode"] = "team"
        return d

    @app.get("/api/team/me")
    def team_me(request: Request) -> dict[str, Any]:
        u = getattr(request.state, "team_user", None)
        if team is None or u is None:
            raise HTTPException(404, "personal mode — no team channel")
        return {"name": u.name, "role": u.role}

    @app.get("/api/stats")
    def stats(today: str | None = None) -> dict[str, Any]:
        try:
            d = date.fromisoformat(today) if today else None
        except ValueError:
            raise HTTPException(400, "today must be YYYY-MM-DD") from None
        return s().stats(d)

    @app.get("/api/doctor")
    def doctor() -> dict[str, Any]:
        return s().doctor()

    @app.get("/api/domains")
    def domains() -> list[dict[str, Any]]:
        return s().domains()

    @app.get("/api/notes")
    def notes(
        status: str | None = None,
        origin: str | None = None,
        type_: str | None = Query(default=None, alias="type"),
        domain: str | None = None,
        tag: str | None = None,
        limit: int = 200,
        order: str = "created",
    ) -> list[dict[str, Any]]:
        return visible(
            s().notes(
                status=status,
                origin=origin,
                type_=type_,
                domain=domain,
                tag=tag,
                limit=limit,
                order=order,
            )
        )

    @app.get("/api/search")
    def search(q: str, limit: int = 20) -> list[dict[str, Any]]:
        return visible(s().search(q, limit=limit))

    @app.get("/api/notes/{ref:path}")
    def note(ref: str) -> dict[str, Any]:
        s()
        gate_ref(ref)
        d = svc.note(ref)
        if team is not None:
            if hidden(d["path"], d.get("classification")):  # re-check on the row actually served
                raise HTTPException(404, f"note not found: {ref}")
            d["backlinks"] = [b for b in d.get("backlinks", []) if not hidden(b)]
        return d

    @app.get("/api/review")
    def review() -> dict[str, Any]:
        q = s().review_queue()
        if team is not None:
            q = {
                "drafts": visible(q["drafts"]),
                "patches": [
                    p for p in q["patches"] if p.get("target") and not hidden(str(p["target"]))
                ],
            }
        return q

    @app.get("/api/guard")
    def guard(days: int = 7) -> list[dict[str, Any]]:
        return s().guard_events(days=days)

    @app.get("/api/git/log")
    def git_log(limit: int = 20) -> list[dict[str, str]]:
        return svc.git_log(limit)

    @app.get("/api/git/status")
    def git_status() -> dict[str, Any]:
        return svc.git_status()

    @app.get("/api/packs")
    def packs() -> list[dict[str, Any]]:
        return svc.packs()

    @app.get("/api/packs/{name}")
    def pack_source(name: str) -> dict[str, Any]:
        return svc.pack_source(name)

    @app.get("/api/settings")
    def settings(response: Response) -> dict[str, Any]:
        data, version = svc.settings_versioned()
        response.headers["ETag"] = f'"{version}"'  # echoed as If-Match by the Settings page (F2)
        response.headers["Cache-Control"] = "no-store"
        return data

    @app.get("/api/obsidian")
    def obsidian() -> dict[str, Any]:
        return s().obsidian()

    @app.post("/api/obsidian/setup", dependencies=[Depends(require_user_click)])
    def obsidian_setup() -> dict[str, Any]:
        return s().obsidian_setup()

    @app.get("/api/commons/candidates")
    def commons_candidates() -> list[dict[str, Any]]:
        return s().commons_candidates()

    @app.get("/api/metrics")
    def metrics() -> dict[str, Any]:
        return s().metrics()

    # ---------------------------------------------------------------- 도움말 챗봇 (ADR-0013)
    @app.get("/api/assistant/status")
    def assistant_status() -> dict[str, Any]:
        return assistant.status()

    @app.post("/api/assistant/chat")
    def assistant_chat(body: AssistantBody) -> dict[str, Any]:
        # Vault 를 바꾸지 않으므로 쓰기 헤더(ADR-0009)를 요구하지 않는다. 색인만 최신으로.
        s()
        try:
            return assistant.chat([m.model_dump() for m in body.messages])
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

    # ---------------------------------------------------------------- writes (user click only)
    @app.post("/api/review/promote/{ref:path}", dependencies=[Depends(require_user_click)])
    def promote(ref: str, body: PromoteBody | None = None) -> dict[str, Any]:
        b = body or PromoteBody()
        s()
        gate_ref(ref)
        return svc.promote(ref, b.domain, digest=b.digest, guard_ack=b.guard_ack)

    @app.post("/api/review/reject/{ref:path}", dependencies=[Depends(require_user_click)])
    def reject(ref: str, body: RejectBody | None = None) -> dict[str, Any]:
        s()
        gate_ref(ref)
        return svc.reject(ref, (body or RejectBody()).reason)

    @app.get("/api/patches")
    def patches() -> list[dict[str, Any]]:
        rows = s().patches()
        if team is not None:
            rows = [p for p in rows if p.get("target") and not hidden(str(p["target"]))]
        return rows

    @app.get("/api/patches/{name}/preview")
    def patch_preview(name: str) -> dict[str, Any]:
        s()
        gate_patch(name)
        return svc.patch_preview(name)

    @app.post("/api/patches/{name}/apply", dependencies=[Depends(require_user_click)])
    def apply_patch(name: str, body: ApplyBody | None = None) -> dict[str, Any]:
        s()
        gate_patch(name)
        return svc.apply_patch(name, (body or ApplyBody()).digest)

    @app.post("/api/patches/{name}/reject", dependencies=[Depends(require_user_click)])
    def reject_patch(name: str) -> dict[str, Any]:
        s()
        gate_patch(name)
        return svc.reject_patch(name)

    @app.put("/api/settings", dependencies=[Depends(require_user_click)])
    def save_settings(
        body: dict[str, Any], if_match: str | None = Header(default=None)
    ) -> dict[str, Any]:
        # If-Match = the ETag of the GET the form was built from; stale → 412 (formal F2)
        return svc.save_settings(body, base_version=_etag_value(if_match))

    @app.post("/api/packs/validate")
    def validate_pack(body: PackBody) -> dict[str, Any]:
        return svc.validate_pack_yaml(body.pack_yaml)  # pure validation, never writes

    @app.put("/api/packs/{name}", dependencies=[Depends(require_user_click)])
    def save_pack(name: str, body: PackBody) -> dict[str, Any]:
        return svc.save_pack(name, body.pack_yaml, copy_from=body.copy_from)

    @app.post("/api/domains", dependencies=[Depends(require_user_click)])
    def add_domain(body: AddDomainBody) -> dict[str, Any]:
        return svc.add_domain(body.id, body.pack)

    @app.post("/api/commons/publish/{ref:path}", dependencies=[Depends(require_user_click)])
    def commons_publish(ref: str, body: PublishBody | None = None) -> dict[str, Any]:
        b = body or PublishBody()
        return svc.commons_publish(ref, confirmed=b.confirmed, push=b.push, pr=b.pr)

    @app.post("/api/onboarding", dependencies=[Depends(require_user_click)])
    def onboarding(body: OnboardBody) -> dict[str, Any]:
        return svc.onboard(body.model_dump())

    # ---------------------------------------------------------------- web
    if serve_web and (WEB_DIST / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

        dist_root = WEB_DIST.resolve()

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str) -> FileResponse:
            # Threat model T09: only files resolving INSIDE dist are served; else SPA index.
            try:
                candidate = (dist_root / full_path).resolve(strict=False)
                if full_path and candidate.is_file() and candidate.is_relative_to(dist_root):
                    return FileResponse(candidate)
            except (OSError, ValueError):  # NUL byte, over-long path … → index
                pass
            return FileResponse(dist_root / "index.html")

    return app
