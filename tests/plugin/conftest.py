"""Guard tests run the real hook scripts as subprocesses with a JSON event on stdin."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS = REPO_ROOT / "plugin" / "hooks"


@dataclass
class HookResult:
    code: int
    stderr: str
    stdout: str

    @property
    def blocked(self) -> bool:
        return self.code == 2

    @property
    def allowed(self) -> bool:
        return self.code == 0


def run_hook(
    script: str, event: object, env: dict[str, str] | None = None, cwd: Path | None = None
) -> HookResult:
    payload = event if isinstance(event, str) else json.dumps(event, ensure_ascii=False)
    full_env = {
        k: v for k, v in os.environ.items() if k not in ("MYELIN_VAULT", "CLAUDE_PROJECT_DIR")
    }
    full_env.update(env or {})
    proc = subprocess.run(
        [sys.executable, "-I", str(HOOKS / script)],
        input=payload,
        capture_output=True,
        text=True,
        env=full_env,
        cwd=cwd or REPO_ROOT,
    )
    return HookResult(proc.returncode, proc.stderr, proc.stdout)


def make_vault(root: Path, level: int = 1) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "myelin.yaml").write_text(
        f"owner: {{name: t}}\npacks: [myelin.core]\ndomains: {{primary: D1}}\n"
        f"level: {level}   # test\n",
        encoding="utf-8",
    )
    for d in [
        "00_Inbox/ai-drafts",
        "10_Domains/D1",
        "40_IP/candidates",
        "50_Journal",
        "80_Outputs/drafts",
        "_patches",
        "90_System",
        ".myelin",
    ]:
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / "10_Domains/D1/note.md").write_text(
        "---\nid: 20261001-0900-a\ntype: fleeting\ncreated: 2026-10-01\n---\n", encoding="utf-8"
    )
    return root


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    return make_vault(tmp_path / "vault", level=1)


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT
