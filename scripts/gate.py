"""Phase Gate 판정기.

사용법:  python scripts/gate.py <n | Pn | current>

- `make gate` 는 먼저 `make check`(lint·type·test)를 통과해야 이 스크립트에 도달한다.
- 이 스크립트는 Phase별 구조·산출물 조건을 결정론적으로 검사한다.
- 아직 Gate가 정의되지 않은 Phase는 실패로 처리한다 (fail-closed).
  각 Phase는 착수 시 자기 Gate 검사를 이 파일에 먼저 추가한다.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
Check = tuple[str, Callable[[], bool]]


def exists(rel: str) -> Callable[[], bool]:
    return lambda: (ROOT / rel).exists()


def current_phase() -> str:
    text = (ROOT / "PHASE_STATE.md").read_text(encoding="utf-8")
    m = re.search(r"^current_phase:\s*(P\d)\s*$", text, re.MULTILINE)
    if not m:
        raise SystemExit("gate: PHASE_STATE.md에서 current_phase를 찾을 수 없습니다.")
    return m.group(1)


def next_phase_tasks_listed(phase_num: int) -> Callable[[], bool]:
    def _check() -> bool:
        text = (ROOT / "PHASE_STATE.md").read_text(encoding="utf-8")
        # 완료([x]) 여부와 무관하게 다음 Phase 작업이 등록되어 있으면 통과 — 과거 Gate도 재실행 가능
        return re.search(rf"^- \[[ x]\] P{phase_num}-T\d+", text, re.MULTILINE) is not None

    return _check


def p0_checks() -> list[Check]:
    required = [
        "CLAUDE.md",
        "PHASE_STATE.md",
        "README.md",
        "Makefile",
        "pyproject.toml",
        ".github/workflows/ci.yml",
        "docs/spec/MYELIN_Rev2.0.md",
        "docs/adr/0001-tech-stack.md",
        "docs/adr/0002-claude-code-plugin-spec.md",
        "packages/myelin-core/src/myelin_core/__init__.py",
        "packages/myelin-cli/src/myelin_cli/__init__.py",
        "packages/myelin-mcp/src/myelin_mcp/__init__.py",
        "packages/myelin-hub/api/src/myelin_hub_api/__init__.py",
        "packages/myelin-hub/web/README.md",
        "plugin/README.md",
        "packs/README.md",
        "design/README.md",
        "theme/README.md",
        "tests/fixtures/vaults/README.md",
    ]
    checks: list[Check] = [(f"exists: {r}", exists(r)) for r in required]
    checks += [
        (f"phase doc: docs/phases/P{i}.md", exists(f"docs/phases/P{i}.md")) for i in range(9)
    ]
    checks.append(("PHASE_STATE lists P1 tasks", next_phase_tasks_listed(1)))
    return checks


def p1_reference_packs_valid() -> bool:
    from myelin_core.loader import discover_packs, resolve

    found = discover_packs(ROOT / "packs")
    wanted = ["myelin.core", "brian.physical-ai", "org.security-consulting"]
    if not set(wanted) <= set(found):
        return False
    resolve(wanted, found)  # 실패 시 PackError
    return True


def p1_invalid_packs_rejected() -> bool:
    from myelin_core.errors import PackError
    from myelin_core.loader import load_pack

    cases = sorted(p for p in (ROOT / "tests/fixtures/packs/invalid").iterdir() if p.is_dir())
    if len(cases) < 10:
        return False
    for case in cases:
        try:
            load_pack(case)
        except PackError as err:
            if not err.issues or not all(i.loc for i in err.issues):
                return False
            continue
        return False  # 통과해 버린 잘못된 Pack
    return True


def p1_minimal_vault_parses() -> bool:
    from myelin_core.note import parse_note_file

    vault = ROOT / "tests/fixtures/vaults/minimal"
    notes = sorted(vault.rglob("*.md"))
    for path in notes:
        parse_note_file(path, root=vault)  # 실패 시 NoteParseError
    return len(notes) >= 30


def p1_schemas_up_to_date() -> bool:
    from myelin_core.schema_export import render_schemas

    for name, text in render_schemas().items():
        target = ROOT / "schemas" / name
        if not target.exists() or target.read_text(encoding="utf-8") != text:
            return False
    return True


def p1_core_coverage() -> bool:
    import subprocess

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "packages/myelin-core",
        "-q",
        "--cov=myelin_core",
        "--cov-fail-under=90",
        "--no-header",
        "-p",
        "no:cacheprovider",
    ]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True).returncode == 0


def guarded(fn: Callable[[], bool]) -> Callable[[], bool]:
    def _run() -> bool:
        try:
            return fn()
        except Exception as exc:  # 검사 중 예외 = FAIL (fail-closed)
            print(f"    ! {fn.__name__}: {type(exc).__name__}: {exc}")
            return False

    return _run


def p1_checks() -> list[Check]:
    return [
        ("exists: docs/adr/0003-yaml-library.md", exists("docs/adr/0003-yaml-library.md")),
        ("reference packs (3) validate & resolve", guarded(p1_reference_packs_valid)),
        ("invalid pack fixtures (>=10) rejected with locs", guarded(p1_invalid_packs_rejected)),
        ("minimal vault (>=30 notes) parses cleanly", guarded(p1_minimal_vault_parses)),
        ("schemas/*.json match models", guarded(p1_schemas_up_to_date)),
        ("myelin_core coverage >= 90%", guarded(p1_core_coverage)),
        ("PHASE_STATE lists P2 tasks", next_phase_tasks_listed(2)),
    ]


GATES: dict[str, Callable[[], list[Check]]] = {
    "P0": p0_checks,
    "P1": p1_checks,
}


def main(argv: list[str]) -> int:
    arg = argv[1] if len(argv) > 1 else "current"
    phase = current_phase() if arg == "current" else ("P" + arg.lstrip("Pp"))
    if phase not in GATES:
        print(f"gate {phase}: Gate 검사가 아직 정의되지 않았습니다 → FAIL (fail-closed)")
        print("  해당 Phase 착수 시 scripts/gate.py 에 검사를 먼저 추가하세요.")
        return 1

    results = [(name, fn()) for name, fn in GATES[phase]()]
    width = max(len(n) for n, _ in results)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name.ljust(width)}")
    failed = [n for n, ok in results if not ok]
    print(f"\ngate {phase}: {len(results) - len(failed)}/{len(results)} passed")
    if failed:
        print(f"gate {phase}: FAIL")
        return 1
    print(f"gate {phase}: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
