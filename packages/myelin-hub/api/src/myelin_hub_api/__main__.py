"""`myelin-hub --vault <path> [--port 8787]` — localhost-only web dashboard."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="myelin-hub", description="MYELIN Hub (localhost dashboard)")
    ap.add_argument(
        "--vault", type=Path, default=None, help="Vault path (default: $MYELIN_VAULT or cwd)"
    )
    ap.add_argument("--port", type=int, default=int(os.environ.get("MYELIN_HUB_PORT", "8787")))
    ap.add_argument(
        "--host", default="127.0.0.1", help="bind address (localhost only in Personal mode)"
    )
    ap.add_argument("--no-web", action="store_true", help="API only")
    ns = ap.parse_args(argv)
    if ns.host not in ("127.0.0.1", "localhost", "::1"):
        print(
            "myelin-hub: Personal mode binds to localhost only (Team mode auth arrives in P7)",
            file=sys.stderr,
        )
        return 2
    root = (ns.vault or Path(os.environ.get("MYELIN_VAULT") or Path.cwd())).resolve()
    import uvicorn

    from myelin_hub_api.app import create_app

    app = create_app(root, serve_web=not ns.no_web)
    print(
        f"MYELIN Hub → http://{ns.host}:{ns.port}  (vault: {root}"
        f"{'' if app.state.service.ready else ' — onboarding'})"
    )
    uvicorn.run(app, host=ns.host, port=ns.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
