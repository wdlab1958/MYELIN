"""Phase Gate 판정기.

사용법:  python scripts/gate.py <n | Pn | current>

- `make gate` 는 먼저 `make check`(lint·type·test)를 통과해야 이 스크립트에 도달한다.
- 이 스크립트는 Phase별 구조·산출물 조건을 결정론적으로 검사한다.
- 아직 Gate가 정의되지 않은 Phase는 실패로 처리한다 (fail-closed).
  각 Phase는 착수 시 자기 Gate 검사를 이 파일에 먼저 추가한다.
"""

from __future__ import annotations

import os
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
        # 다음 Phase 작업이 등록되어 있거나([ ]/[x]), 그 Phase가 이미 끝나 보고서가 있으면 통과
        # — 과거 Gate를 언제든 재실행할 수 있게 상태 파일 서식에 의존하지 않는다.
        listed = re.search(rf"^- \[[ x]\] P{phase_num}-T\d+", text, re.MULTILINE) is not None
        return listed or (ROOT / "docs" / "reports" / f"P{phase_num}.md").exists()

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


GOLDEN_ARGS = [
    "--name",
    "Brian",
    "--pack",
    "brian.physical-ai",
    "--primary",
    "AI-ML-AX",
    "--research",
    "ROBOTICS-LEARNING",
    "--growth",
    "AUTO-DESIGN",
    "--extra",
    "EMBEDDED-SW",
    "--level",
    "1",
    "--today",
    "2026-10-18",
    "--yes",
]


def _run_cli(args: list[str]) -> tuple[int, str]:
    from typer.testing import CliRunner

    from myelin_cli.main import app

    result = CliRunner().invoke(app, [*args, "--packs", str(ROOT / "packs")])
    return result.exit_code, result.output


def _tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def p2_golden_and_speed() -> bool:
    import tempfile
    import time

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "vault"
        start = time.perf_counter()
        code, out = _run_cli(["init", str(target), *GOLDEN_ARGS])
        elapsed = time.perf_counter() - start
        if code != 0:
            print(out)
            return False
        golden = ROOT / "tests/fixtures/vaults/golden/brian"
        return elapsed < 10 and _tree(target) == _tree(golden)


def p2_init_refuses_unsafe_targets() -> bool:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        occupied = Path(tmp) / "occupied"
        occupied.mkdir()
        (occupied / "note.md").write_text("mine", encoding="utf-8")
        in_git = Path(tmp) / "repo"
        (in_git / ".git").mkdir(parents=True)
        cases = [occupied, in_git / "vault", ROOT / "my-vault"]
        results = [_run_cli(["init", str(c), *GOLDEN_ARGS])[0] != 0 for c in cases]
        untouched = (occupied / "note.md").read_text(encoding="utf-8") == "mine"
        return all(results) and untouched and not (ROOT / "my-vault").exists()


def p2_doctor_golden_clean() -> bool:
    from myelin_core.doctor import run_doctor

    findings = run_doctor(
        ROOT / "tests/fixtures/vaults/golden/brian", today=_golden_today(), check_location=False
    )
    for f in findings:
        print(f"    ! unexpected: {f}")
    return not findings


def p2_doctor_violations_exact() -> bool:
    from myelin_core.doctor import run_doctor
    from myelin_core.errors import MyelinError
    from myelin_core.yamlio import load_yaml

    vault = ROOT / "tests/fixtures/vaults/violations"
    expected_doc = load_yaml(
        (vault.parent / "violations.expected.yaml").read_text(encoding="utf-8"),
        "violations.expected.yaml",
        MyelinError,
    )
    expected = {(e["rule"], e["path"]) for e in expected_doc["findings"]}
    found = {
        (f.rule, f.path) for f in run_doctor(vault, today=_golden_today(), check_location=False)
    }
    for miss in sorted(expected - found):
        print(f"    ! missed: {miss}")
    for extra in sorted(found - expected):
        print(f"    ! false positive: {extra}")
    rules = {r for r, _ in expected}
    return found == expected and len(rules) >= 8


def _golden_today() -> object:
    from datetime import date

    return date(2026, 10, 18)


def p2_readme_privacy() -> bool:
    return "## Privacy model" in (ROOT / "README.md").read_text(encoding="utf-8")


def p2_checks() -> list[Check]:
    return [
        (
            "exists: docs/adr/0005-vault-config-and-scaffold.md",
            exists("docs/adr/0005-vault-config-and-scaffold.md"),
        ),
        ("init == golden snapshot, < 10s", guarded(p2_golden_and_speed)),
        (
            "init refuses occupied / git / source-tree targets",
            guarded(p2_init_refuses_unsafe_targets),
        ),
        ("doctor: golden vault has 0 findings", guarded(p2_doctor_golden_clean)),
        ("doctor: violations found exactly (>=8 rules)", guarded(p2_doctor_violations_exact)),
        ("README has Privacy model section", guarded(p2_readme_privacy)),
        ("PHASE_STATE lists P3 tasks", next_phase_tasks_listed(3)),
    ]


SKILLS = ("ingest", "distill", "interview", "link", "compose", "review", "ip-scan")
GUARD_COPIES = (
    "packages/myelin-core/src/myelin_core/resources/myelin_guard.py",
    "plugin/scripts/myelin_guard.py",
    "tests/fixtures/vaults/golden/brian/.claude/hooks/myelin_guard.py",
)


def p3_adr_revised() -> bool:
    return "## Rev 2" in (ROOT / "docs/adr/0002-claude-code-plugin-spec.md").read_text(
        encoding="utf-8"
    )


def p3_claude_validate() -> bool:
    import shutil
    import subprocess

    claude = shutil.which("claude")
    if claude is None:
        print("    ! claude CLI not found — this check needs Claude Code installed")
        return False
    for target in ("plugin", "."):
        res = subprocess.run(
            [claude, "plugin", "validate", "--strict", target],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if res.returncode != 0:
            print(f"    ! validate {target}: {res.stdout[-400:]}{res.stderr[-400:]}")
            return False
    return True


def p3_guard_copies_identical() -> bool:
    blobs = {(ROOT / p).read_bytes() for p in GUARD_COPIES}
    return len(blobs) == 1


def p3_skill_frontmatter() -> bool:
    from myelin_core.errors import MyelinError
    from myelin_core.note import split_frontmatter
    from myelin_core.yamlio import load_yaml

    for name in SKILLS:
        text = (ROOT / f"plugin/skills/{name}/SKILL.md").read_text(encoding="utf-8")
        fm_text, body = split_frontmatter(text, name)
        fm = load_yaml(fm_text, name, MyelinError)
        if fm.get("name") != name or not fm.get("description"):
            return False
        if fm.get("disable-model-invocation") is not True:  # 모든 MYELIN Skill은 사람이 호출
            return False
        if "<!-- myelin:min-level" not in body or len(text.splitlines()) > 500:
            return False
    return True


def p3_pytest(path: str) -> Callable[[], bool]:
    def _run() -> bool:
        import subprocess

        cmd = [sys.executable, "-m", "pytest", path, "-q", "--no-header", "-p", "no:cacheprovider"]
        res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if res.returncode != 0:
            print("    ! " + res.stdout[-600:])
        return res.returncode == 0

    _run.__name__ = f"pytest {path}"
    return _run


CLAUDE_VALIDATE = "claude plugin validate --strict (plugin + marketplace)"
LOCAL_ONLY = {CLAUDE_VALIDATE}  # CI 러너에 Claude Code CLI가 없다 (ADR-0002 Rev 2)


def p3_checks() -> list[Check]:
    return [
        ("ADR-0002 Rev 2 (re-verified against docs)", guarded(p3_adr_revised)),
        (CLAUDE_VALIDATE, guarded(p3_claude_validate)),
        (
            "guard copies identical (core / plugin / golden vault)",
            guarded(p3_guard_copies_identical),
        ),
        (
            "guard tests (write gate, read block, escapes, malformed)",
            guarded(p3_pytest("tests/plugin/test_guard.py")),
        ),
        ("skills: 7 present, human-invoked, min-level, <=500 lines", guarded(p3_skill_frontmatter)),
        (
            "skill output contracts: guard-allowed + doctor-clean",
            guarded(p3_pytest("tests/plugin/test_skill_contracts.py")),
        ),
        ("exists: docs/manual/P3-e2e.md (real Claude checklist)", exists("docs/manual/P3-e2e.md")),
        ("PHASE_STATE lists P4 tasks", next_phase_tasks_listed(4)),
    ]


def p4_default_read_only() -> bool:
    import asyncio
    import tempfile

    from myelin_mcp.server import build_server

    async def tools(vault: Path) -> set[str]:
        return {t.name for t in await build_server(vault).list_tools()}

    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp) / "v"
        code, out = _run_cli(["init", str(vault), *GOLDEN_ARGS])
        if code != 0:
            print(out)
            return False
        names = asyncio.run(tools(vault))
        expected = {"search_notes", "get_note", "query_frontmatter", "list_domains", "vault_stats"}
        return names == expected


def p4_search_perf() -> bool:
    import subprocess

    res = subprocess.run(
        [sys.executable, "scripts/bench_mcp.py", "--notes", "5000", "--p95-ms", "300"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    print("    " + res.stdout.strip().splitlines()[-1] if res.stdout.strip() else "")
    return res.returncode == 0


def p4_checks() -> list[Check]:
    return [
        ("exists: docs/adr/0006-mcp-server.md", exists("docs/adr/0006-mcp-server.md")),
        (
            "mcp tests (tools, privacy, escapes, stdio e2e)",
            guarded(p3_pytest("packages/myelin-mcp")),
        ),
        ("default server is read-only (5 tools, no write_draft)", guarded(p4_default_read_only)),
        ("search p95 < 300ms on 5,000 notes", guarded(p4_search_perf)),
        ("exists: docs/guides/mcp.md", exists("docs/guides/mcp.md")),
        ("PHASE_STATE lists P5 tasks", next_phase_tasks_listed(5)),
    ]


def _design_cmd(*args: str) -> Callable[[], bool]:
    def _run() -> bool:
        import subprocess

        res = subprocess.run(
            [sys.executable, "design/build.py", *args], cwd=ROOT, capture_output=True, text=True
        )
        out = (res.stdout + res.stderr).strip()
        if res.returncode != 0 and out:
            print("    ! " + out[-800:].replace("\n", "\n    ! "))
        return res.returncode == 0

    _run.__name__ = "design/build.py " + " ".join(args)
    return _run


def p5_screenshot_current() -> bool:
    """갤러리 스크린샷이 현재 디자인(갤러리 HTML + CSS)으로 찍힌 것인지."""
    import hashlib

    shot = ROOT / "docs/reports/P5/gallery.png"
    stamp = ROOT / "docs/reports/P5/gallery.sha256"
    if not shot.exists() or not stamp.exists():
        return False
    h = hashlib.sha256()
    for rel in ("design/gallery/index.html", "design/dist/tokens.css", "design/src/components.css"):
        h.update((ROOT / rel).read_bytes())
    return stamp.read_text(encoding="utf-8").strip() == h.hexdigest()


def p5_checks() -> list[Check]:
    return [
        ("exists: design/tokens.json (single source)", exists("design/tokens.json")),
        ("generated files up to date (css, tailwind, obsidian)", guarded(_design_cmd("--check"))),
        ("contrast: text pairs >= 4.5:1, neon never text", guarded(_design_cmd("--contrast"))),
        ("lint: no hard-coded colors/shadows outside tokens", guarded(_design_cmd("--lint"))),
        ("tokens tests", guarded(p3_pytest("tests/design"))),
        (
            "obsidian theme manifest + theme.css",
            exists("theme/obsidian-myelin-emboss/manifest.json"),
        ),
        ("gallery screenshot matches current design", guarded(p5_screenshot_current)),
        ("PHASE_STATE lists P6 tasks", next_phase_tasks_listed(6)),
    ]


GATES: dict[str, Callable[[], list[Check]]] = {
    "P5": p5_checks,
    "P4": p4_checks,
    "P0": p0_checks,
    "P1": p1_checks,
    "P2": p2_checks,
    "P3": p3_checks,
}


def main(argv: list[str]) -> int:
    arg = argv[1] if len(argv) > 1 else "current"
    phase = current_phase() if arg == "current" else ("P" + arg.lstrip("Pp"))
    if phase not in GATES:
        print(f"gate {phase}: Gate 검사가 아직 정의되지 않았습니다 → FAIL (fail-closed)")
        print("  해당 Phase 착수 시 scripts/gate.py 에 검사를 먼저 추가하세요.")
        return 1

    in_ci = os.environ.get("CI") == "true"
    checks = GATES[phase]()
    width = max(len(n) for n, _ in checks)
    results: list[tuple[str, bool]] = []
    skipped: list[str] = []
    for name, fn in checks:
        if in_ci and name in LOCAL_ONLY:
            print(f"  SKIP  {name.ljust(width)}  (CI에 도구 없음 — 로컬 Gate에서 확인)")
            skipped.append(name)
            continue
        ok = fn()
        results.append((name, ok))
        print(f"  {'PASS' if ok else 'FAIL'}  {name.ljust(width)}")
    failed = [n for n, ok in results if not ok]
    print(f"\ngate {phase}: {len(results) - len(failed)}/{len(results)} passed")
    if failed:
        print(f"gate {phase}: FAIL")
        return 1
    if skipped:
        print(f"gate {phase}: PASS (CI: local-only {len(skipped)}건 제외, 완료 판정은 로컬)")
        return 0
    print(f"gate {phase}: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
