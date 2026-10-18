"""`myelin-hub --vault <경로>` — Hub를 localhost에서 연다.

- 바인딩은 loopback만 허용한다. 다른 주소는 exit 2 (Team 모드 인증은 v1.0 이후, ADR-0008).
- 시작만으로는 Vault에 아무것도 쓰지 않는다. Vault가 없으면 온보딩 마법사가 뜬다.
"""

from __future__ import annotations

import argparse
import ipaddress
import sys
import webbrowser
from pathlib import Path

from myelin_core.errors import MyelinError
from myelin_core.onboarding import find_packs_dir

DEFAULT_PORT = 8765


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def default_web_dir() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parent / "web", here.parents[3] / "web" / "dist"):
        if (candidate / "index.html").is_file():
            return candidate
    return here.parents[3] / "web" / "dist"


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="myelin-hub", description="MYELIN Hub (localhost)")
    ap.add_argument("--vault", type=Path, required=True, help="Vault 경로 (없으면 온보딩)")
    ap.add_argument("--host", default="127.0.0.1", help="바인딩 주소 (loopback만)")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--packs", type=Path, default=None, help="Domain Pack 폴더")
    ap.add_argument("--web", type=Path, default=None, help="빌드된 웹 폴더")
    ap.add_argument("--open", action="store_true", help="브라우저 열기")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not _is_loopback(args.host):
        print(
            f"✗ --host {args.host}: Hub는 localhost 전용입니다 (127.0.0.1 · ::1 · localhost).\n"
            "  개인 지식이 네트워크로 노출되지 않도록 다른 주소는 거부합니다.",
            file=sys.stderr,
        )
        return 2
    try:
        packs_dir = find_packs_dir(args.packs)
    except MyelinError as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    import uvicorn

    from myelin_hub_api.app import create_app
    from myelin_hub_api.service import HubService

    vault = args.vault.expanduser().absolute()
    app = create_app(HubService(vault, packs_dir), web_dir=args.web or default_web_dir())
    url = f"http://{'[::1]' if args.host == '::1' else args.host}:{args.port}/"
    print(f"MYELIN Hub → {url}  (Vault: {vault})")
    if args.open:
        webbrowser.open(url)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0
