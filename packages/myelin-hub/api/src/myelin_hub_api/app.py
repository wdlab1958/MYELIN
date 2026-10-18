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

from myelin_hub_api import __version__
from myelin_hub_api.service import HubError, HubService

INTENT_HEADER = "x-myelin-intent"
INTENT_VALUE = "user-click"
WEB_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"


class PromoteBody(BaseModel):
    domain: str | None = None


class RejectBody(BaseModel):
    reason: str = ""


class PackBody(BaseModel):
    pack_yaml: str = Field(min_length=1)


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

    @app.exception_handler(HubError)
    async def _hub_error(_: Request, exc: HubError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=exc.status)

    def s() -> HubService:
        svc.index and svc.index.refresh()
        return svc

    # ---------------------------------------------------------------- reads
    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "version": __version__, "ready": svc.ready, "root": str(svc.root)}

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

    # ---------------------------------------------------------------- writes (user click only)
    @app.post("/api/review/promote/{ref:path}", dependencies=[Depends(require_user_click)])
    def promote(ref: str, body: PromoteBody | None = None) -> dict[str, Any]:
        return svc.promote(ref, (body or PromoteBody()).domain)

    @app.post("/api/review/reject/{ref:path}", dependencies=[Depends(require_user_click)])
    def reject(ref: str, body: RejectBody | None = None) -> dict[str, Any]:
        return svc.reject(ref, (body or RejectBody()).reason)

    @app.post("/api/patches/{name}/apply", dependencies=[Depends(require_user_click)])
    def apply_patch(name: str) -> dict[str, Any]:
        return svc.apply_patch(name)

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
        return svc.save_pack(name, body.pack_yaml)

    @app.post("/api/onboarding", dependencies=[Depends(require_user_click)])
    def onboarding(body: OnboardBody) -> dict[str, Any]:
        return svc.onboard(body.model_dump())

    # ---------------------------------------------------------------- web
    if serve_web and (WEB_DIST / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str) -> FileResponse:
            candidate = WEB_DIST / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(WEB_DIST / "index.html")

    return app
