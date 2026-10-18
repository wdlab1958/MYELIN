"""P8-T6 — measure "install → first verified note" end to end (정본 P8 Gate: < 15 min).

Runs, in a temp HOME/vault, with wall-clock timing:
  1. scripts/install.sh --no-web --no-plugin --no-mcp (uv sync + launchers + theme)
  2. myelin init (non-interactive, same wizard inputs as the Hub)
  3. an ai-draft is created the way /ingest would (fixture output) and promoted through HubService
Prints a JSON summary and exits 1 when total > 900 s.
Records docs/reports/P8/time-to-first-verified.json.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/reports/P8/time-to-first-verified.json"
BUDGET_S = 15 * 60


def main() -> int:
    sys.path.insert(0, str(ROOT / "packages/myelin-core/src"))
    sys.path.insert(0, str(ROOT / "packages/myelin-hub/api/src"))
    tmp = Path(tempfile.mkdtemp(prefix="myelin-ttfv-"))
    home, vault = tmp / "home", tmp / "vault"
    home.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "MYELIN_PACKS": str(ROOT / "packs"),
        "UV_PYTHON": sys.executable,
    }
    steps: dict[str, float] = {}
    t_all = time.perf_counter()
    try:
        t = time.perf_counter()
        r = subprocess.run(
            [
                "bash",
                str(ROOT / "scripts/install.sh"),
                "--no-web",
                "--no-plugin",
                "--no-mcp",
                "--vault",
                str(vault),
                "--bin",
                str(home / "bin"),
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            print(r.stdout, r.stderr, file=sys.stderr)
            return 1
        steps["install_s"] = time.perf_counter() - t

        t = time.perf_counter()
        r = subprocess.run(
            [
                str(home / "bin" / "myelin"),
                "init",
                "-y",
                "--vault",
                str(vault),
                "--name",
                "New User",
                "--primary",
                "D1",
                "--research",
                "D3",
                "--level",
                "1",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            print(r.stdout, r.stderr, file=sys.stderr)
            return 1
        steps["init_s"] = time.perf_counter() - t

        t = time.perf_counter()
        from myelin_hub_api.service import HubService

        src = ROOT / "tests/fixtures/skill-outputs/ingest"
        draft = next(src.glob("*.md"))
        text = draft.read_text(encoding="utf-8").replace("domain: [D2, D3]", "domain: [D1]")
        (vault / "00_Inbox/ai-drafts" / draft.name).write_text(text, encoding="utf-8")
        svc = HubService.open(vault)
        res = svc.promote(f"00_Inbox/ai-drafts/{draft.name}", today=date.today())
        steps["draft_and_promote_s"] = time.perf_counter() - t
        assert res["status"] == "verified" and (vault / res["path"]).exists()
        from myelin_core.metrics import onboarding_minutes

        steps["onboarding_minutes_recorded"] = onboarding_minutes(vault) or 0.0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    total = time.perf_counter() - t_all
    summary = {
        "date": date.today().isoformat(),
        "total_s": round(total, 1),
        "budget_s": BUDGET_S,
        "pass": total < BUDGET_S,
        **{k: round(v, 2) for k, v in steps.items()},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
