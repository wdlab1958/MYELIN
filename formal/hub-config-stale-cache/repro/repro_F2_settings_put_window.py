#!/usr/bin/env python3
"""F2 (CONFIRMED, NOT fixed — needs HITL) — PUT /api/settings has no version check.

TLC trace evidence/trace_partial_P2_F2.md (MC_partial.cfg: ReloadOnRequest=TRUE, IfMatch=FALSE):
  BrowserGet (Settings.tsx:17 fetch current) -> CliAddDomain(d1) -> BrowserPut (userPut next)
The PUT body is `{...current, level, mcp, commons}`, so a Domain added between the GET and the PUT
is written away. After F1 the window is one browser round-trip (was: the whole Hub lifetime).

Property P2 (frozen): a Settings save never removes a Domain from myelin.yaml.
Run:  .venv/bin/python formal/hub-config-stale-cache/repro/repro_F2_settings_put_window.py
Exit 1 = P2 violated (expected until F2 is fixed), 0 = holds.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / "packages/myelin-hub/api/src"), str(REPO / "packages/myelin-core/src")]
os.environ["MYELIN_PACKS"] = str(REPO / "packs")

from myelin_core.config import load_config  # noqa: E402
from myelin_core.scaffold import add_domain  # noqa: E402
from myelin_core.vault import Vault  # noqa: E402
from myelin_hub_api.service import HubService  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "basic"
        shutil.copytree(
            REPO / "tests/fixtures/vaults/basic", root, ignore=shutil.ignore_patterns(".myelin", ".obsidian")
        )
        for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "fixture"]):
            subprocess.run(["git", *args], cwd=root, check=True,
                           env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"})
        svc = HubService.open(root)
        current = svc.settings()                                   # BrowserGet  (Settings.tsx:17)
        add_domain(Vault.open(root), "SEC-CONSULT", datetime(2026, 10, 29, 9, 0))  # CliAddDomain (other process)
        assert "SEC-CONSULT" in load_config(root).domains.all_ids
        current["level"] = 3
        svc.save_settings(current)                                 # BrowserPut  (Settings.tsx:18-20)
        after = load_config(root).domains.all_ids
        print("myelin.yaml domains after save:", after)
        if "SEC-CONSULT" not in after:
            print("F2 VIOLATED (P2) — the save between GET and PUT dropped the Domain added by the CLI")
            print("  10_Domains/SEC-CONSULT/_MOC.md exists:", (root / "10_Domains/SEC-CONSULT/_MOC.md").is_file(),
                  "-> doctor: unregistered domain")
            return 1
        print("F2 holds")
        return 0


if __name__ == "__main__":
    sys.exit(main())
