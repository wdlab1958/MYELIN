"""Phase Gate runner: `make gate P=<n>` → `python scripts/gate.py <n>`.

Each Phase has a list of named checks. A check is a shell command (must exit 0) or a
Python predicate. All checks must pass; output is a table + exit code 0/1. Gates for
phases that have not started yet are declared with their spec criteria but fail
with "not implemented" (fail-closed) so nobody can tag a phase by accident.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMBOSS_ALL = " && ".join(f"python3 scripts/emboss.py {cmd}" for cmd in ("check", "a11y", "lint"))


@dataclass(frozen=True)
class Check:
    name: str
    run: Callable[[], tuple[bool, str]]


def sh(cmd: list[str], env: dict[str, str] | None = None) -> Callable[[], tuple[bool, str]]:
    def _run() -> tuple[bool, str]:
        full_env = {**os.environ, **(env or {})}
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=full_env)
        tail = (proc.stdout + proc.stderr).strip().splitlines()
        return proc.returncode == 0, (tail[-1] if tail else "")

    return _run


def not_implemented(spec: str) -> Callable[[], tuple[bool, str]]:
    return lambda: (False, f"NOT IMPLEMENTED — spec: {spec}")


def phase_state_lists_next_phase_tasks(n: int) -> Callable[[], tuple[bool, str]]:
    def _run() -> tuple[bool, str]:
        text = (ROOT / "PHASE_STATE.md").read_text(encoding="utf-8")
        nxt = n + 1
        if nxt > 8:
            return True, "P8 is the final phase"
        has_tasks = re.search(rf"^- \[ \] P{nxt}-T\d+", text, re.M) is not None
        return (
            has_tasks,
            f"P{nxt} task list {'present' if has_tasks else 'missing'} in PHASE_STATE.md",
        )

    return _run


def _threat_model_high_zero() -> tuple[bool, str]:
    text = (ROOT / "docs/security/threat-model.md").read_text(encoding="utf-8")
    rows = [ln for ln in text.splitlines() if ln.startswith("| T")]
    open_high = [ln.split("|")[1].strip() for ln in rows if "**High**" in ln and "조치" not in ln]
    return (not open_high, f"{len(rows)} threats, open High: {open_high or 0}")


def phase_docs_complete() -> tuple[bool, str]:
    missing = [n for n in range(9) if not (ROOT / f"docs/phases/P{n}.md").exists()]
    return not missing, f"missing docs/phases: {missing}" if missing else "P0~P8 present"


def adr_exists(num: str, slug_hint: str) -> Callable[[], tuple[bool, str]]:
    def _run() -> tuple[bool, str]:
        hits = list((ROOT / "docs/adr").glob(f"{num}-*.md"))
        return bool(hits), (hits[0].name if hits else f"ADR-{num} ({slug_hint}) missing")

    return _run


GATES: dict[int, list[Check]] = {
    0: [
        Check("ruff check", sh(["uv", "run", "ruff", "check", "."])),
        Check("ruff format --check", sh(["uv", "run", "ruff", "format", "--check", "."])),
        Check("mypy --strict", sh(["uv", "run", "mypy"])),
        Check("pytest (empty packages green)", sh(["uv", "run", "pytest", "-q"])),
        Check("docs/phases P0~P8", phase_docs_complete),
        Check("ADR-0001 tech stack", adr_exists("0001", "tech-stack")),
        Check("ADR-0002 plugin/hook spec", adr_exists("0002", "plugin-spec")),
        Check(
            "CI workflow present", lambda: ((ROOT / ".github/workflows/ci.yml").exists(), "ci.yml")
        ),
        Check("PHASE_STATE has P1 tasks", phase_state_lists_next_phase_tasks(0)),
    ],
    1: [
        Check("ruff check", sh(["uv", "run", "ruff", "check", "."])),
        Check("mypy --strict", sh(["uv", "run", "mypy"])),
        Check(
            "pytest + coverage ≥ 90% (myelin-core)",
            sh(
                [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "--cov=myelin_core",
                    "--cov-fail-under=90",
                    "--cov-report=term",
                ]
            ),
        ),
        Check(
            "3 packs validate + resolve", sh(["uv", "run", "python", "scripts/validate_packs.py"])
        ),
        Check(
            "invalid pack fixtures (≥10) → clear errors",
            sh(["uv", "run", "pytest", "-q", "packages/myelin-core/tests/test_invalid_packs.py"]),
        ),
        Check(
            "fixture vault 30+ notes parse clean",
            sh(["uv", "run", "pytest", "-q", "packages/myelin-core/tests/test_fixture_vault.py"]),
        ),
        Check(
            "JSON Schema export in sync",
            sh(["uv", "run", "python", "scripts/export_schemas.py", "--check"]),
        ),
        Check("ADR-0003 schema policy", adr_exists("0003", "schema-validation-policy")),
        Check("PHASE_STATE has P2 tasks", phase_state_lists_next_phase_tasks(1)),
    ],
    2: [
        Check("ruff check", sh(["uv", "run", "ruff", "check", "."])),
        Check("mypy --strict", sh(["uv", "run", "mypy"])),
        Check(
            "pytest + coverage ≥ 90% (core + cli)",
            sh(
                [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "--cov=myelin_core",
                    "--cov=myelin_cli",
                    "--cov-fail-under=90",
                    "--cov-report=term",
                ]
            ),
        ),
        Check(
            "init golden snapshot matches",
            sh(
                [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "packages/myelin-cli/tests/test_golden.py::test_init_matches_golden",
                ]
            ),
        ),
        Check(
            "doctor: seeded violations 100%, false positives 0",
            sh(["uv", "run", "pytest", "-q", "packages/myelin-core/tests/test_doctor.py"]),
        ),
        Check(
            "init < 10s",
            sh(
                [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "packages/myelin-cli/tests/test_golden.py::test_init_under_10_seconds",
                ]
            ),
        ),
        Check(
            "doctor clean on fixture basic",
            sh(["uv", "run", "myelin", "doctor", "--vault", "tests/fixtures/vaults/basic"]),
        ),
        Check("ADR-0004 myelin.yaml", adr_exists("0004", "myelin-yaml-schema")),
        Check("PHASE_STATE has P3 tasks", phase_state_lists_next_phase_tasks(2)),
    ],
    3: [
        Check("ruff check", sh(["uv", "run", "ruff", "check", "."])),
        Check("mypy --strict", sh(["uv", "run", "mypy"])),
        Check("pytest (all)", sh(["uv", "run", "pytest", "-q"])),
        Check(
            "guard: write paths (outside/symlink/../hidden/level) 100%",
            sh(["uv", "run", "pytest", "-q", "tests/plugin/test_guard_write.py"]),
        ),
        Check(
            "guard: bash bypasses (redirect/tee/sed -i/mv/rm/git/inline) 100%",
            sh(["uv", "run", "pytest", "-q", "tests/plugin/test_guard_bash.py"]),
        ),
        Check(
            "guard: LEVEL_ALLOW in sync, hooks stdlib-only",
            sh(["uv", "run", "pytest", "-q", "tests/plugin/test_guard_sync.py"]),
        ),
        Check(
            "skills: 7 SKILL.md, outputs pass doctor, Level 0 disabled",
            sh(
                [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "tests/plugin/test_skills.py",
                    "packages/myelin-cli/tests/test_cli_skills.py",
                ]
            ),
        ),
        Check(
            "claude plugin validate --strict",
            sh(["claude", "plugin", "validate", "./plugin", "--strict"]),
        ),
        Check(
            "init golden (now includes .claude/settings.json)",
            sh(
                [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "packages/myelin-cli/tests/test_golden.py::test_init_matches_golden",
                ]
            ),
        ),
        Check("ADR-0005 level-gated guard", adr_exists("0005", "level-gated-guard")),
        Check("ADR-0006 patches format", adr_exists("0006", "patches-format")),
        Check("PHASE_STATE has P4 tasks", phase_state_lists_next_phase_tasks(3)),
    ],
    4: [
        Check("ruff check", sh(["uv", "run", "ruff", "check", "."])),
        Check("mypy --strict", sh(["uv", "run", "mypy"])),
        Check("pytest (all)", sh(["uv", "run", "pytest", "-q"])),
        Check(
            "mcp: path escape (.., abs, ~, symlink) blocked",
            sh(
                [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "packages/myelin-mcp/tests/test_service.py",
                    "-k",
                    "escape",
                ]
            ),
        ),
        Check(
            "mcp: read-only by default, write_draft opt-in + level",
            sh(
                [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "packages/myelin-mcp/tests/test_server.py",
                    "-k",
                    "read_only or registered",
                ]
            ),
        ),
        Check(
            "mcp: confidential withheld unless exposed",
            sh(
                [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "packages/myelin-mcp/tests/test_service.py",
                    "-k",
                    "confidential",
                ]
            ),
        ),
        Check(
            "index: search p95 < 300ms @ 5,000 notes",
            sh(
                ["uv", "run", "pytest", "-q", "-s", "tests/test_perf_index.py"],
                env={"MYELIN_PERF": "1"},
            ),
        ),
        Check("ADR-0007 MCP policy", adr_exists("0007", "mcp-policy")),
        Check(
            "MCP setup guide",
            lambda: ((ROOT / "docs/guides/mcp-setup.md").exists(), "docs/guides/mcp-setup.md"),
        ),
        Check("PHASE_STATE has P5 tasks", phase_state_lists_next_phase_tasks(4)),
    ],
    5: [
        Check("ruff check", sh(["uv", "run", "ruff", "check", "."])),
        Check("mypy --strict", sh(["uv", "run", "mypy"])),
        Check("pytest (all)", sh(["uv", "run", "pytest", "-q"])),
        Check(
            "tokens → generated files in sync (single source)",
            sh(["python3", "scripts/emboss.py", "check"]),
        ),
        Check(
            "text contrast ≥ 4.5:1 + no neon-as-text", sh(["python3", "scripts/emboss.py", "a11y"])
        ),
        Check("no hardcoded colors in UI (lint)", sh(["python3", "scripts/emboss.py", "lint"])),
        Check(
            "gallery screenshot present (사람 승인 대상)",
            lambda: (
                (ROOT / "docs/reports/P5/gallery.png").exists(),
                "docs/reports/P5/gallery.png",
            ),
        ),
        Check("ADR-0008 contrast adjustments", adr_exists("0008", "emboss-contrast")),
        Check("PHASE_STATE has P6 tasks", phase_state_lists_next_phase_tasks(5)),
    ],
    6: [
        Check("ruff check", sh(["uv", "run", "ruff", "check", "."])),
        Check("mypy --strict", sh(["uv", "run", "mypy"])),
        Check("pytest (all)", sh(["uv", "run", "pytest", "-q"])),
        Check(
            "hub api: reads never write · writes need user click",
            sh(
                [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "packages/myelin-hub/api/tests/test_api.py",
                    "-k",
                    "reads_never_write or writes_require_user_click",
                ]
            ),
        ),
        Check(
            "hub api: promote → git commit",
            sh(
                [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "packages/myelin-hub/api/tests/test_api.py",
                    "-k",
                    "promote_creates or onboarding",
                ]
            ),
        ),
        Check(
            "web: typecheck + build",
            sh(["npm", "run", "--prefix", "packages/myelin-hub/web", "build"]),
        ),
        Check(
            "web: no hardcoded colors (emboss lint)", sh(["python3", "scripts/emboss.py", "lint"])
        ),
        Check(
            "playwright: onboarding → first promote, zero writes without click",
            sh(["npm", "run", "--prefix", "packages/myelin-hub/web", "e2e:screens"]),
        ),
        Check(
            "screenshots in docs/reports/P6",
            lambda: (
                len(list((ROOT / "docs/reports/P6").glob("*.png"))) >= 5,
                f"{len(list((ROOT / 'docs/reports/P6').glob('*.png')))} png",
            ),
        ),
        Check("ADR-0009 hub write policy", adr_exists("0009", "hub-write-policy")),
        Check("PHASE_STATE has P7 tasks", phase_state_lists_next_phase_tasks(6)),
    ],
    7: [
        Check("ruff check", sh(["uv", "run", "ruff", "check", "."])),
        Check("mypy --strict", sh(["uv", "run", "mypy"])),
        Check("pytest (all)", sh(["uv", "run", "pytest", "-q"])),
        Check(
            "commons: confidential / share:false publish blocked 100%",
            sh(
                [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "packages/myelin-core/tests/test_commons.py",
                    "-k",
                    "blocks or gates or requires",
                ]
            ),
        ),
        Check(
            "commons: every outbound path needs human confirmation",
            sh(
                [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "packages/myelin-cli/tests/test_cli_commons.py",
                    "packages/myelin-hub/api/tests/test_api.py",
                    "-k",
                    "publish or propose or commons",
                ]
            ),
        ),
        Check(
            "metrics: payload anonymous (no vault content)",
            sh(["uv", "run", "pytest", "-q", "packages/myelin-core/tests/test_metrics.py"]),
        ),
        Check(
            "org packs: 4 packs validate (incl. a3.incident-response)",
            sh(["uv", "run", "python", "scripts/validate_packs.py"]),
        ),
        Check(
            "pilot kit docs present",
            lambda: (
                all(
                    (ROOT / p).exists()
                    for p in (
                        "docs/guides/pilot-guide.md",
                        "docs/guides/workshop-60min.md",
                        "docs/guides/day1-checklist.md",
                        "docs/reports/P7/pilot-feedback.md",
                        "docs/spec/commons.md",
                    )
                ),
                "pilot-guide · workshop-60min · day1-checklist · pilot-feedback · commons spec",
            ),
        ),
        Check(
            "web: typecheck + build",
            sh(["npm", "run", "--prefix", "packages/myelin-hub/web", "build"]),
        ),
        Check(
            "HUMAN pilot: ≥5 onboarded ≤15 min (scripts/pilot.py check)",
            sh(["python3", "scripts/pilot.py", "check"]),
        ),
        Check(
            "HUMAN pilot: feedback report filled (no TBD)",
            lambda: (
                "TBD"
                not in (ROOT / "docs/reports/P7/pilot-feedback.md").read_text(encoding="utf-8"),
                "docs/reports/P7/pilot-feedback.md",
            ),
        ),
        Check("ADR-0010 commons policy", adr_exists("0010", "commons-policy")),
        Check("PHASE_STATE has P8 tasks", phase_state_lists_next_phase_tasks(7)),
    ],
    8: [
        Check("ruff check", sh(["uv", "run", "ruff", "check", "."])),
        Check("mypy --strict", sh(["uv", "run", "mypy"])),
        Check("pytest (all)", sh(["uv", "run", "pytest", "-q"])),
        Check("threat model: 0 High open", _threat_model_high_zero),
        Check(
            "threat model: High fixes have regression tests",
            sh(
                [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "packages/myelin-hub/api/tests/test_api.py",
                    "-k",
                    "host_and_origin or path_traversal",
                ]
            ),
        ),
        Check(
            "install.sh: idempotent, never clobbers",
            sh(["uv", "run", "pytest", "-q", "tests/test_install.py"]),
        ),
        Check(
            "plugin + local marketplace validate --strict",
            sh(["claude", "plugin", "validate", ".", "--strict"]),
        ),
        Check("supply chain: uv.lock up to date", sh(["uv", "lock", "--check"])),
        Check(
            "install → first verified note < 15 min (measured)",
            sh(["uv", "run", "python", "scripts/time_to_first_verified.py"]),
        ),
        Check(
            "naming check recorded (KIPRIS/USPTO/domain/GitHub)",
            lambda: (
                (ROOT / "docs/reports/P8/naming-check.md").exists(),
                "docs/reports/P8/naming-check.md",
            ),
        ),
        Check(
            "guides + release notes present",
            lambda: (
                all(
                    (ROOT / p).exists()
                    for p in (
                        "docs/guides/user-guide.md",
                        "docs/guides/admin-guide.md",
                        "docs/RELEASE_NOTES.md",
                        "CHANGELOG.md",
                    )
                ),
                "user-guide · admin-guide · RELEASE_NOTES · CHANGELOG",
            ),
        ),
        Check(
            "release notes list known limitations",
            lambda: (
                "다크 모드" in (ROOT / "docs/RELEASE_NOTES.md").read_text(encoding="utf-8"),
                "다크 모드 미지원 명시",
            ),
        ),
        Check(
            "web: typecheck + build",
            sh(["npm", "run", "--prefix", "packages/myelin-hub/web", "build"]),
        ),
        Check("emboss: tokens in sync · a11y · lint", sh(["bash", "-c", EMBOSS_ALL])),
    ],
}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not argv[1].isdigit() or int(argv[1]) not in GATES:
        print("usage: gate.py <phase 0-8>", file=sys.stderr)
        return 2
    n = int(argv[1])
    print(f"== MYELIN Gate P{n} ==")
    ok_all = True
    for c in GATES[n]:
        ok, msg = c.run()
        ok_all &= ok
        print(f"[{'PASS' if ok else 'FAIL'}] {c.name:<45} {msg}")
    print(f"== Gate P{n}: {'PASS' if ok_all else 'FAIL'} ==")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
