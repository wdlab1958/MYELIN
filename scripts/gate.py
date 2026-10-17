"""Phase Gate runner: `make gate P=<n>` → `python scripts/gate.py <n>`.

Each Phase has a list of named checks. A check is a shell command (must exit 0) or a
Python predicate. All checks must pass; output is a table + exit code 0/1. Gates for
phases that have not started yet are declared with their spec criteria but fail
with "not implemented" (fail-closed) so nobody can tag a phase by accident.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Check:
    name: str
    run: Callable[[], tuple[bool, str]]


def sh(cmd: list[str]) -> Callable[[], tuple[bool, str]]:
    def _run() -> tuple[bool, str]:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
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
        Check("init golden snapshot", not_implemented("golden snapshot 일치")),
        Check(
            "doctor: 100% seeded violations, 0 false positives", not_implemented("doctor 위반 검출")
        ),
        Check("init < 10s", not_implemented("신규 Vault 생성 < 10초")),
    ],
    3: [
        Check("guard blocks 100% (outside/symlink/..)", not_implemented("허용 외 쓰기 차단 100%")),
        Check("/ingest /distill output passes doctor", not_implemented("Skill e2e")),
        Check("Level 0 hides write skills", not_implemented("Level 0 비활성")),
    ],
    4: [
        Check("path escape blocked", not_implemented("경로 이탈 차단")),
        Check("read-only by default", not_implemented("기본 읽기 전용")),
        Check("search p95 < 300ms @5k notes", not_implemented("p95 < 300ms")),
    ],
    5: [
        Check("no hardcoded tokens (lint)", not_implemented("토큰 하드코딩 0")),
        Check("text contrast ≥ 4.5:1", not_implemented("대비 검사")),
        Check("gallery screenshot approved", not_implemented("갤러리 스크린샷 승인")),
    ],
    6: [
        Check("playwright: onboarding → first promote", not_implemented("온보딩·승격 e2e")),
        Check("promote creates git commit", not_implemented("승격 시 commit")),
        Check("zero writes without user action", not_implemented("사람 행위 없는 쓰기 0")),
    ],
    7: [
        Check("confidential/share:false publish blocked 100%", not_implemented("publish 차단")),
        Check("pilot ≥5 onboarded ≤15min", not_implemented("파일럿 온보딩")),
        Check("pilot feedback report", not_implemented("피드백 리포트")),
    ],
    8: [
        Check("threat model: 0 High open", not_implemented("위협모델 High 0")),
        Check("install → first verified < 15min", not_implemented("15분 온보딩")),
        Check("KIPRIS/domain/GitHub name check recorded", not_implemented("상표 확인")),
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
