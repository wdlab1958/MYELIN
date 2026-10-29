#!/usr/bin/env python3
"""F3 (side finding, NOT fixed) — `myelin add-domain` commits the whole working tree (`git add -A`).

Property (ADR-0009 §4, docs/adr/0009-hub-write-policy.md:11): "스테이징은 변경된 경로만 … 무관한
사용자 변경은 커밋에 섞이지 않는다". The CLI's `_git_commit_vault` (packages/myelin-cli/src/
myelin_cli/app.py:105) stages everything, so an unfinished user note is recorded under the AI
commit `[myelin:add-domain] …` (PHASE_STATE.md:136, 2026-10-23 myelin-demo incident).

Run:  .venv/bin/python formal/hub-config-stale-cache/repro/repro_F3_add_domain_commit_scope.py
Exit 1 = property violated (expected on current code), 0 = holds.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PY = sys.executable


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, env={**os.environ})


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp) / "v"
        init = run(
            PY, "-m", "myelin_cli", "init", "--non-interactive", "--vault", str(vault),
            "--packs-dir", str(REPO / "packs"), "--name", "Brian", "--primary", "D1",
            "--research", "D3", "--growth", "D4", "--level", "2", cwd=REPO,
        )
        assert init.returncode == 0, init.stdout + init.stderr
        # Case A — the user's unrelated, uncommitted but *valid* file (not a note: doctor ignores .txt)
        scratch = vault / "30_Resources" / "wip-notes.txt"
        scratch.parent.mkdir(exist_ok=True)
        scratch.write_text("private scratch — not meant for the add-domain commit\n", encoding="utf-8")
        add = run(
            PY, "-m", "myelin_cli", "add-domain", "D2", "--vault", str(vault),
            "--packs-dir", str(REPO / "packs"), cwd=REPO,
        )
        assert add.returncode == 0, add.stdout + add.stderr
        print(add.stdout.rstrip())
        touched = [ln.split("변경: ", 1)[1] for ln in add.stdout.splitlines() if "변경: " in ln][0]
        head = run("git", "log", "-1", "--format=%s", cwd=vault).stdout.strip()
        committed = run("git", "show", "--pretty=format:", "--name-only", "HEAD", cwd=vault)
        files = sorted(f for f in committed.stdout.splitlines() if f)
        print("HEAD               :", head)
        print("add-domain touched :", touched)
        print("commit contains    :", files)
        violated = False
        if head == "[myelin:add-domain] D2" and "30_Resources/wip-notes.txt" in files:
            print("F3-A VIOLATED — unrelated user file committed under [myelin:add-domain]")
            violated = True
        # Case B — an unfinished user note (no frontmatter) is swept in and the Vault pre-commit
        # device (doctor --staged) then refuses the *add-domain* commit as a whole
        wip = vault / "20_Projects" / "wip-not-ready.md"
        wip.write_text("# WIP — not ready\n", encoding="utf-8")
        add2 = run(
            PY, "-m", "myelin_cli", "add-domain", "SEC-CONSULT", "--vault", str(vault),
            "--packs-dir", str(REPO / "packs"), cwd=REPO,
        )
        print(add2.stdout.rstrip(), add2.stderr.rstrip())
        head2 = run("git", "log", "-1", "--format=%s", cwd=vault).stdout.strip()
        status = run("git", "status", "--porcelain", cwd=vault).stdout.rstrip()
        print("HEAD after 2nd add :", head2)
        print("git status         :", status.replace("\n", " | "))
        if add2.returncode == 0 and head2 != "[myelin:add-domain] SEC-CONSULT":
            print("F3-B VIOLATED — add-domain's own commit was refused because `git add -A` staged the user's WIP note")
            violated = True
        if violated:
            return 1
        print("F3 holds — commit limited to add-domain's own paths")
        return 0


if __name__ == "__main__":
    sys.exit(main())
