"""설치 → 첫 verified 노트 자동 측정 (P8 Gate).

새 임시 폴더에서 신규 사용자가 하는 일을 그대로 실행하고 시간을 잰다:
  1) scripts/install.sh 로 설치 (이 저장소의 커밋된 HEAD 를 clone — 작업 트리 아님)
  2) 설치된 `myelin-hub` 실행 → 터미널 링크의 토큰으로 로그인
  3) 온보딩 마법사 API (CLI init 과 같은 로직, 로컬 git 켬)
  4) Claude 초안 1건 (ai-drafts) → Review Gate 승격 → git commit 확인

사람이 화면을 읽고 고르는 시간은 들어 있지 않다 — 사람 측정은 파일럿(docs/pilot)에서 한다.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DRAFT = (
    "---\nid: 20261018-0900-first-note\ntype: evergreen\ndomain: [AI-ML-AX]\nstatus: draft\n"
    "origin: claude\ncreated: 2000-01-01\n---\n# 첫 노트\n\n설치 후 첫 verified 노트.\n"
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class Client:
    def __init__(self, base: str) -> None:
        self.base = base
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def get(self, path: str) -> Any:
        with self.opener.open(self.base + path, timeout=60) as res:
            body = res.read()
        return json.loads(body) if body[:1] in (b"{", b"[") else body

    def act(self, path: str, body: dict[str, Any]) -> Any:
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Origin": self.base,
                "X-Myelin-Intent": "user",
            },
        )
        with self.opener.open(req, timeout=120) as res:
            return json.loads(res.read())


def run(out: Path, keep: bool = False) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="myelin-first-run-"))
    env = {
        **os.environ,
        "MYELIN_HOME": str(tmp / "install"),
        "MYELIN_BIN": str(tmp / "bin"),
        "GIT_CONFIG_GLOBAL": str(tmp / "gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    env.pop("MYELIN_PACKS", None)
    env.pop("VIRTUAL_ENV", None)
    ref = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    result: dict[str, Any] = {"ref": ref, "verified": False, "commit": None}
    t0 = time.monotonic()

    # 1) 설치
    subprocess.run(
        ["bash", str(ROOT / "scripts/install.sh"), "--source", str(ROOT), "--ref", ref],
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=900,
    )
    result["install_s"] = round(time.monotonic() - t0, 1)

    # 2) Hub 실행 (설치된 shim)
    port = _free_port()
    vault = tmp / "MyVault"
    hub = subprocess.Popen(
        [str(tmp / "bin/myelin-hub"), "--vault", str(vault), "--port", str(port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        assert hub.stdout is not None
        line = hub.stdout.readline()
        match = re.search(r"\?token=([\w-]+)", line)
        if not match:
            raise RuntimeError(f"Hub 링크를 읽지 못했습니다: {line!r}")
        base = f"http://127.0.0.1:{port}"
        client = Client(base)
        for _ in range(150):
            try:
                client.get(f"/?token={match.group(1)}")
                break
            except OSError:
                time.sleep(0.1)
        state = client.get("/api/state")
        assert state["initialized"] is False

        # 3) 온보딩 (Hub 마법사와 같은 API)
        client.act(
            "/api/onboarding/apply",
            {
                "owner": "First User",
                "packs": ["brian.physical-ai"],
                "primary": "AI-ML-AX",
                "level": 1,
                "git": True,
            },
        )

        # 4) Claude 초안 → Review Gate 승격
        draft = vault / "00_Inbox/ai-drafts/첫 노트.md"
        draft.write_text(DRAFT, encoding="utf-8")
        queue = client.get("/api/review")
        item = queue[0]
        client.get(f"/api/note?path={urllib.request.quote(item['path'])}")
        promoted = client.act("/api/review/promote", {"path": item["path"], "id": item["id"]})
        note = (vault / promoted["path"]).read_text(encoding="utf-8")
        log = subprocess.run(
            ["git", "-C", str(vault), "log", "-1", "--format=%H %s"],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        ).stdout.strip()
        result["verified"] = "status: verified" in note
        result["commit"] = promoted["commit"] if log.startswith(promoted["commit"]) else None
    finally:
        hub.terminate()
        hub.wait(timeout=10)
    result["total_s"] = round(time.monotonic() - t0, 1)
    result["tmp"] = str(tmp) if keep else "(deleted)"
    out.parent.mkdir(parents=True, exist_ok=True)
    public = {k: v for k, v in result.items() if k != "tmp"}
    out.write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not keep:
        subprocess.run(["rm", "-rf", str(tmp)], check=False)
    return result


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="설치 → 첫 verified 노트 자동 측정")
    ap.add_argument("--out", type=Path, default=ROOT / "docs/reports/P8/first-run.json")
    ap.add_argument("--keep", action="store_true", help="임시 폴더를 남긴다")
    args = ap.parse_args(argv)
    try:
        result = run(args.out, keep=args.keep)
    except (subprocess.CalledProcessError, RuntimeError, AssertionError, OSError) as exc:
        detail = getattr(exc, "stderr", "") or getattr(exc, "stdout", "") or ""
        print(f"✗ {type(exc).__name__}: {exc}\n{str(detail)[-1500:]}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    ok = result["verified"] and result["commit"] and result["total_s"] < 15 * 60
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
