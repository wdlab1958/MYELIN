"""`myelin-hub --vault <path> [--port 8787]` — web dashboard.

Personal mode (default): loopback only, no authentication — unchanged.
Team mode (ADR-0016): `--auth-file team-auth.yaml` turns on bearer-token auth, roles, the
confidentiality filter and the access log. A non-loopback `--host` is refused unless team mode is
configured *and* the channel is encrypted (`--tls-cert/--tls-key`, or `--behind-tls-proxy`).
`myelin-hub --new-token <name> [--role read|write]` prints a token and its auth-file entry.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from myelin_core.product import PRODUCT_NAME
from myelin_hub_api.team import (
    AUTH_ENV,
    ROLE_READ,
    ROLES,
    LiveTeamAuth,
    TeamAuth,
    TeamConfigError,
    check_bind,
    is_loopback_bind,
    new_token,
)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="myelin-hub", description=f"{PRODUCT_NAME} Hub (dashboard)")
    ap.add_argument(
        "--vault", type=Path, default=None, help="Vault path (default: $MYELIN_VAULT or cwd)"
    )
    ap.add_argument("--port", type=int, default=int(os.environ.get("MYELIN_HUB_PORT", "8787")))
    ap.add_argument(
        "--host",
        default="127.0.0.1",
        help="bind address. Anything but loopback needs --auth-file and TLS (team mode)",
    )
    ap.add_argument("--no-web", action="store_true", help="API only")
    ap.add_argument(
        "--auth-file",
        type=Path,
        default=None,
        help=f"team mode: YAML with users/token hashes/allowed_hosts (or ${AUTH_ENV})",
    )
    ap.add_argument("--tls-cert", type=Path, default=None, help="team mode: TLS certificate (PEM)")
    ap.add_argument("--tls-key", type=Path, default=None, help="team mode: TLS private key (PEM)")
    ap.add_argument(
        "--behind-tls-proxy",
        action="store_true",
        help="team mode: a TLS-terminating reverse proxy fronts this Hub (plain HTTP behind it)",
    )
    ap.add_argument(
        "--new-token", metavar="NAME", default=None, help="print a new team token and exit"
    )
    ap.add_argument("--role", choices=ROLES, default=ROLE_READ, help="role for --new-token")
    return ap


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    if ns.new_token is not None:
        try:
            TeamAuth.from_mapping(
                {"users": [{"name": ns.new_token, "role": ns.role, "token_sha256": "0" * 64}]}
            )
        except TeamConfigError as exc:
            print(f"myelin-hub: {exc}", file=sys.stderr)
            return 2
        token, digest = new_token()
        print(f"token (shown once — give it to {ns.new_token}; it is not stored anywhere):")
        print(f"  {token}")
        print("auth-file entry (only the SHA-256 is kept on the server):")
        print(f"  - {{ name: {ns.new_token}, role: {ns.role}, token_sha256: {digest} }}")
        return 0
    auth_path = ns.auth_file or (Path(os.environ[AUTH_ENV]) if os.environ.get(AUTH_ENV) else None)
    live: LiveTeamAuth | None = None
    team: TeamAuth | None = None
    if auth_path is not None:
        try:
            live = LiveTeamAuth.open(auth_path)  # re-read on change: revocation without restart
            team = live.current()
        except TeamConfigError as exc:
            print(f"myelin-hub: {exc}", file=sys.stderr)
            return 2
    if bool(ns.tls_cert) != bool(ns.tls_key):
        print("myelin-hub: --tls-cert and --tls-key go together", file=sys.stderr)
        return 2
    tls = bool(ns.tls_cert and ns.tls_key)
    refusal = check_bind(ns.host, team, tls=tls, behind_tls_proxy=ns.behind_tls_proxy)
    if refusal:
        print(f"myelin-hub: {refusal}", file=sys.stderr)
        return 2
    root = (ns.vault or Path(os.environ.get("MYELIN_VAULT") or Path.cwd())).resolve()
    import uvicorn

    from myelin_hub_api.app import create_app

    app = create_app(root, serve_web=not ns.no_web, team=live)
    if team is not None and not app.state.service.ready:
        print(
            "myelin-hub: team mode needs an initialised Vault — run onboarding in Personal mode "
            "first",
            file=sys.stderr,
        )
        return 2
    scheme = "https" if tls else "http"
    mode = (
        f"team mode: {len(team.users)} user(s), confidential notes withheld, access log on"
        if team is not None
        else "personal mode"
    )
    print(
        f"{PRODUCT_NAME} Hub → {scheme}://{ns.host}:{ns.port}  (vault: {root}"
        f"{'' if app.state.service.ready else ' — onboarding'} · {mode})"
    )
    if team is not None and is_loopback_bind(ns.host):
        print("  team mode on loopback: reachable only through a local proxy / SSH tunnel")
    uvicorn.run(
        app,
        host=ns.host,
        port=ns.port,
        log_level="warning",
        ssl_certfile=str(ns.tls_cert) if tls else None,
        ssl_keyfile=str(ns.tls_key) if tls else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
