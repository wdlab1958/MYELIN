"""MYELIN Hub API — FastAPI app factory (정본 §2.3 MYELIN Hub, §P6).

- Binds to localhost only (see __main__); no auth in Personal mode (정본 §4.4).
- Reads are GET and never write. Writes are POST/PUT and require the `X-Myelin-Intent: user-click`
  header, which only the Hub UI sets from a click handler (ADR-0009). Everything else is 403.
- Serves the built web UI from packages/myelin-hub/web/dist when present.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from myelin_hub_api import __version__
from myelin_hub_api.service import HubError, HubService

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
    Origin."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        host = _host_only(request.headers.get("host", ""))
        if host not in LOOPBACK_HOSTS:
            return JSONResponse(
                {"detail": f"MYELIN Hub serves localhost only (Host={host!r})"}, status_code=403
            )
        origin = request.headers.get("origin")
        if origin:
            o = origin.lower()
            ohost = _host_only(o.split("://", 1)[-1]) if "://" in o else o
            if ohost not in LOOPBACK_HOSTS:
                return JSONResponse(
                    {"detail": "cross-origin requests are refused"}, status_code=403
                )
        return await call_next(request)


INTENT_VALUE = "user-click"
WEB_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"


class PromoteBody(BaseModel):
    domain: str | None = None


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


def require_user_click(x_myelin_intent: str | None = Header(default=None)) -> None:
    """Writes must come from an explicit user click in the Hub UI (ADR-0009)."""
    if x_myelin_intent != INTENT_VALUE:
        raise HTTPException(
            403, "write actions require the X-Myelin-Intent: user-click header (UI click only)"
        )


def create_app(vault_root: Path, *, serve_web: bool = True) -> FastAPI:
    svc = HubService.open(Path(vault_root))
    app = FastAPI(
        title="MYELIN Hub",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.service = svc
    app.add_middleware(HostOriginGuard)

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
        return {
            "ok": True,
            "version": __version__,
            "ready": svc.ready,
            "error": svc.config_error,
            "root": str(svc.root),
        }

    @app.get("/api/vault")
    def vault() -> dict[str, Any]:
        return svc.summary()

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
        return s().notes(
            status=status,
            origin=origin,
            type_=type_,
            domain=domain,
            tag=tag,
            limit=limit,
            order=order,
        )

    @app.get("/api/search")
    def search(q: str, limit: int = 20) -> list[dict[str, Any]]:
        return s().search(q, limit=limit)

    @app.get("/api/notes/{ref:path}")
    def note(ref: str) -> dict[str, Any]:
        return s().note(ref)

    @app.get("/api/review")
    def review() -> dict[str, Any]:
        return s().review_queue()

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
    def settings() -> dict[str, Any]:
        return svc.settings()

    @app.get("/api/commons/candidates")
    def commons_candidates() -> list[dict[str, Any]]:
        return s().commons_candidates()

    @app.get("/api/metrics")
    def metrics() -> dict[str, Any]:
        return s().metrics()

    # ---------------------------------------------------------------- writes (user click only)
    @app.post("/api/review/promote/{ref:path}", dependencies=[Depends(require_user_click)])
    def promote(ref: str, body: PromoteBody | None = None) -> dict[str, Any]:
        return svc.promote(ref, (body or PromoteBody()).domain)

    @app.post("/api/review/reject/{ref:path}", dependencies=[Depends(require_user_click)])
    def reject(ref: str, body: RejectBody | None = None) -> dict[str, Any]:
        return svc.reject(ref, (body or RejectBody()).reason)

    @app.get("/api/patches")
    def patches() -> list[dict[str, Any]]:
        return s().patches()

    @app.get("/api/patches/{name}/preview")
    def patch_preview(name: str) -> dict[str, Any]:
        return s().patch_preview(name)

    @app.post("/api/patches/{name}/apply", dependencies=[Depends(require_user_click)])
    def apply_patch(name: str, body: ApplyBody | None = None) -> dict[str, Any]:
        return svc.apply_patch(name, (body or ApplyBody()).digest)

    @app.post("/api/patches/{name}/reject", dependencies=[Depends(require_user_click)])
    def reject_patch(name: str) -> dict[str, Any]:
        return svc.reject_patch(name)

    @app.put("/api/settings", dependencies=[Depends(require_user_click)])
    def save_settings(body: dict[str, Any]) -> dict[str, Any]:
        return svc.save_settings(body)

    @app.post("/api/packs/validate")
    def validate_pack(body: PackBody) -> dict[str, Any]:
        return svc.validate_pack_yaml(body.pack_yaml)  # pure validation, never writes

    @app.put("/api/packs/{name}", dependencies=[Depends(require_user_click)])
    def save_pack(name: str, body: PackBody) -> dict[str, Any]:
        return svc.save_pack(name, body.pack_yaml, copy_from=body.copy_from)

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
