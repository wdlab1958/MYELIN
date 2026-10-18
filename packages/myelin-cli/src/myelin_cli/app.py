"""MYELIN CLI — `myelin init | add-domain | doctor | stats` (정본 §2.3 MYELIN CLI, P2).

Design rules
- Fail-closed: `init` never overwrites; unknown input aborts with a clear message (exit 2).
- Every command takes `--vault PATH` (default: cwd) and `--packs-dir` (repeatable).
- Interactive prompts only when a TTY is present and a value is missing; `--non-interactive`
  turns missing values into errors so scripts behave deterministically.
- Test hook: `MYELIN_NOW=YYYY-MM-DDTHH:MM` fixes "now" for reproducible scaffolds (golden).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

import typer
from typer._click import exceptions as click_exc  # typer's vendored click

from myelin_cli import __version__
from myelin_core.config import ConfigError, Domains, MyelinConfig, Owner
from myelin_core.doctor import run_doctor
from myelin_core.levels import LEVEL_NAMES, skill_table
from myelin_core.packs.loader import PackError, discover_packs
from myelin_core.scaffold import ScaffoldError, VaultExistsError, add_domain, init_vault
from myelin_core.stats import compute_stats
from myelin_core.vault import Vault, default_pack_roots

app = typer.Typer(
    name="myelin",
    help=(
        "MYELIN — Personal Knowledge OS. "
        "Vault 생성(init) · Domain 추가 · 무결성 점검(doctor) · 지표(stats)."
    ),
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
)

VaultOpt = Annotated[Path, typer.Option("--vault", "-v", help="Vault 경로 (기본: 현재 디렉터리)")]
PacksOpt = Annotated[
    list[Path] | None,
    typer.Option(
        "--packs-dir",
        help="Pack 검색 디렉터리 (반복 가능). 기본: $MYELIN_PACKS · <Vault>/packs · 저장소 packs/",
    ),
]
JsonOpt = Annotated[bool, typer.Option("--json", help="JSON 출력")]

EXIT_OK, EXIT_FINDINGS, EXIT_USAGE = 0, 1, 2


def _now() -> datetime:
    raw = os.environ.get("MYELIN_NOW")
    if raw:
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            _die(f"MYELIN_NOW={raw!r} 는 ISO 날짜/시각이 아닙니다")
    return datetime.now()


def _is_tty() -> bool:
    """Interactive prompts only on a real terminal (patched in tests)."""
    return sys.stdin.isatty()


def _die(msg: str, code: int = EXIT_USAGE) -> None:
    typer.echo(f"myelin: {msg}", err=True)
    raise typer.Exit(code)


def _roots(vault: Path, packs_dir: list[Path] | None) -> list[Path]:
    return [p.resolve() for p in packs_dir] if packs_dir else default_pack_roots(vault)


def _open_vault(path: Path) -> Vault:
    try:
        return Vault.open(path)
    except ConfigError as exc:
        _die(str(exc))
    raise AssertionError("unreachable")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"myelin {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option(
            "--version", "-V", callback=_version_callback, is_eager=True, help="버전 출력"
        ),
    ] = False,
) -> None:
    """MYELIN CLI."""


# ------------------------------------------------------------------------------------- init


def _ask(
    label: str, default: str | None, *, interactive: bool, required: bool = False
) -> str | None:
    if not interactive:
        if required and not default:
            _die(f"--{label} 값이 필요합니다 (비대화형 모드)")
        return default
    answer = typer.prompt(label, default=default or "", show_default=bool(default))
    answer = answer.strip()
    if required and not answer:
        _die(f"{label} 은(는) 비워둘 수 없습니다")
    return answer or None


@app.command()
def init(
    vault: VaultOpt = Path(),
    name: Annotated[str | None, typer.Option(help="소유자 이름")] = None,
    team: Annotated[str, typer.Option(help="팀")] = "",
    email: Annotated[str, typer.Option(help="이메일")] = "",
    primary: Annotated[str | None, typer.Option(help="Primary Domain ID (업무 근간)")] = None,
    research: Annotated[str | None, typer.Option(help="Research Domain ID (연구 관심)")] = None,
    growth: Annotated[str | None, typer.Option(help="Growth Domain ID (성장 목표)")] = None,
    pack: Annotated[
        list[str] | None,
        typer.Option("--pack", help="설치할 Pack (반복). myelin.core 는 자동 포함"),
    ] = None,
    level: Annotated[
        int, typer.Option(min=0, max=3, help="0 read-only | 1 drafts | 2 link-patch | 3 scheduled")
    ] = 1,
    language: Annotated[str, typer.Option(help="언어")] = "ko",
    packs_dir: PacksOpt = None,
    non_interactive: Annotated[
        bool, typer.Option("--non-interactive", "-y", help="질문 없이 플래그만 사용")
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="만들 파일 목록만 출력")] = False,
) -> None:
    """새 Vault 를 만든다 (3+1 Domain 마법사). 기존 파일이 있으면 중단한다 — 덮어쓰지 않는다."""
    interactive = not non_interactive and _is_tty()
    roots = _roots(vault, packs_dir)
    try:
        registry = discover_packs(roots)
    except PackError as exc:
        _die(str(exc))
    if not registry:
        _die(
            f"Pack 을 찾을 수 없습니다. 검색 경로: {[str(r) for r in roots]} "
            "— --packs-dir 를 지정하세요"
        )

    available_domains = {
        d.id: (lp.name, d.name) for lp in registry.values() for d in lp.pack.domains
    }
    if interactive:
        typer.echo(
            "MYELIN init — 3+1 규칙: Primary(업무 근간) · Research(연구) · Growth(성장). "
            "+1 은 3개월 후."
        )
        typer.echo("사용 가능한 Domain:")
        for did, (pn, dn) in sorted(available_domains.items()):
            typer.echo(f"  {did:<14} {dn}  [{pn}]")

    name = _ask("name", name, interactive=interactive, required=True)
    team = _ask("team", team, interactive=interactive) or ""
    email = _ask("email", email, interactive=interactive) or ""
    primary = _ask("primary", primary, interactive=interactive, required=True)
    research = _ask("research", research, interactive=interactive)
    growth = _ask("growth", growth, interactive=interactive)
    assert name and primary

    chosen = [d for d in (primary, research, growth) if d]
    unknown = [d for d in chosen if d not in available_domains]
    if unknown:
        _die(f"알 수 없는 Domain {unknown}. 사용 가능: {sorted(available_domains)}")
    packs = ["myelin.core"]
    for d in chosen:
        pn = available_domains[d][0]
        if pn not in packs:
            packs.append(pn)
    for p in pack or []:
        if p not in packs:
            if p not in registry:
                _die(f"Pack {p!r} 을 찾을 수 없습니다. 사용 가능: {sorted(registry)}")
            packs.append(p)

    try:
        cfg = MyelinConfig(
            owner=Owner(name=name, team=team, email=email),
            language=language,
            packs=packs,
            domains=Domains(primary=primary, research=research, growth=growth),
            level=level,
        )
    except ValueError as exc:
        _die(f"설정 오류: {exc}")

    now = _now()
    if dry_run:
        from myelin_core.scaffold import plan_init, resolve_config_packs

        try:
            plan = plan_init(cfg, resolve_config_packs(cfg, roots), now)
        except (ScaffoldError, PackError) as exc:
            _die(str(exc))
        for p in plan.paths():
            typer.echo(p)
        return
    try:
        plan = init_vault(vault, cfg, now, pack_roots=roots)
    except VaultExistsError as exc:
        _die(str(exc))
    except (ScaffoldError, PackError) as exc:
        _die(str(exc))
    typer.echo(f"✔ Vault 생성: {vault.resolve()}  ({len(plan.files)} files, {len(plan.dirs)} dirs)")
    typer.echo(
        f"  Domains: {', '.join(cfg.domains.all_ids)} · Packs: {', '.join(cfg.pack_names)} "
        f"· Level {cfg.level}"
    )
    typer.echo(
        "  다음: Obsidian 에서 Vault 열기 → Claude Code 를 Vault 폴더에서 실행 → `myelin doctor`"
    )


# ------------------------------------------------------------------------------- add-domain


@app.command("add-domain")
def add_domain_cmd(
    domain_id: Annotated[
        str, typer.Argument(help="Pack 에 선언된 Domain ID (예: D3, SEC-CONSULT)")
    ],
    vault: VaultOpt = Path(),
    pack: Annotated[
        str | None, typer.Option("--pack", help="여러 Pack 이 같은 ID 를 선언할 때 선택")
    ] = None,
    packs_dir: PacksOpt = None,
) -> None:
    """Pack 에서 Domain 을 추가한다 (+1). 기존 노트는 건드리지 않는다."""
    v = _open_vault(vault)
    try:
        touched = add_domain(
            v, domain_id, _now(), pack_name=pack, pack_roots=_roots(v.root, packs_dir)
        )
    except (ScaffoldError, PackError, ValueError) as exc:
        _die(str(exc))
    typer.echo(f"✔ Domain {domain_id} 추가 (extra). 변경: {', '.join(touched)}")


# ----------------------------------------------------------------------------------- doctor


@app.command()
def doctor(
    vault: VaultOpt = Path(),
    as_json: JsonOpt = False,
    strict: Annotated[bool, typer.Option("--strict", help="warning 도 실패로 취급")] = False,
    packs_dir: PacksOpt = None,
) -> None:
    """Vault 무결성 점검 — 규칙 8종. 오류가 있으면 exit 1."""
    v = _open_vault(vault)
    report = run_doctor(v, pack_roots=_roots(v.root, packs_dir))
    if as_json:
        typer.echo(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        for f in report.findings:
            typer.echo(f"{f.severity.upper():<7} {f.rule:<18} {f.path}: {f.message}")
        summary = ", ".join(f"{k}={n}" for k, n in report.by_rule().items()) or "no findings"
        typer.echo(
            f"doctor: {report.notes_scanned} notes · {len(report.errors)} errors · "
            f"{len(report.warnings)} warnings · {summary}"
        )
    failed = bool(report.errors) or (strict and bool(report.warnings))
    raise typer.Exit(EXIT_FINDINGS if failed else EXIT_OK)


# ------------------------------------------------------------------------------------ stats


@app.command()
def stats(
    vault: VaultOpt = Path(),
    as_json: JsonOpt = False,
    today: Annotated[
        str | None, typer.Option(help="기준일 YYYY-MM-DD (기본: 오늘 / $MYELIN_NOW)")
    ] = None,
) -> None:
    """개인 지표 (정본 §11.1) 를 산출한다."""
    v = _open_vault(vault)
    try:
        day = date.fromisoformat(today) if today else _now().date()
    except ValueError:
        _die(f"--today {today!r} 는 YYYY-MM-DD 가 아닙니다")
        raise AssertionError from None
    st = compute_stats(v, day)
    if as_json:
        typer.echo(json.dumps(st.to_dict(), ensure_ascii=False, indent=2))
        return
    typer.echo(f"MYELIN stats — {v.root.name} · as of {st.as_of} · {st.notes} notes")
    typer.echo(f"{'KPI':<22}{'value':>10}   target")
    for k, val, target in st.kpi_rows():
        typer.echo(f"{k:<22}{val:>10}   {target}")
    typer.echo(f"by_status: {st.by_status}")
    typer.echo(f"by_origin: {st.by_origin}")
    typer.echo(f"by_domain: {st.by_domain}")
    if st.parse_errors:
        typer.echo(f"⚠ {st.parse_errors} notes could not be parsed — run `myelin doctor`")


# ----------------------------------------------------------------------------------- skills


@app.command()
def skills(vault: VaultOpt = Path(), as_json: JsonOpt = False) -> None:
    """현재 Level 에서 사용 가능한 Skill 과 쓰기 범위를 보인다 (정본 §7.1)."""
    v = _open_vault(vault)
    rows = skill_table(v.config.level)
    if as_json:
        typer.echo(
            json.dumps({"level": v.config.level, "skills": rows}, ensure_ascii=False, indent=2)
        )
        return
    typer.echo(f"Level {v.config.level} — {LEVEL_NAMES[v.config.level]}")
    typer.echo(f"{'skill':<12}{'min':>4}  {'enabled':<8} {'write scope':<22} summary")
    for r in rows:
        flag = "yes" if r["enabled"] else "no"
        typer.echo(
            f"{r['skill']:<12}{r['min_level']:>4}  {flag:<8} {r['write_scope']!s:<22} "
            f"{r['summary']}"
        )


# ---------------------------------------------------------------------------- interview-bank


@app.command("interview-bank")
def interview_bank(
    vault: VaultOpt = Path(),
    domain: Annotated[str | None, typer.Option("--domain", "-d", help="Domain ID 로 필터")] = None,
    as_json: JsonOpt = False,
    packs_dir: PacksOpt = None,
) -> None:
    """설정된 Pack 의 /interview 질문 은행을 출력한다 (Skill 이 Bash 로 호출)."""
    v = _open_vault(vault)
    if domain is not None and domain not in v.config.domains.all_ids:
        _die(f"domain {domain!r} 은 이 Vault 에 설정되지 않았습니다: {v.config.domains.all_ids}")
    try:
        packs = v.packs(_roots(v.root, packs_dir))
    except PackError as exc:
        _die(str(exc))
    rows: list[dict[str, object]] = []
    for lp in packs:
        for d in lp.pack.domains:
            if d.id not in v.config.domains.all_ids or (domain and d.id != domain):
                continue
            bank = lp.interview_bank_for(d.id)
            if bank is None:
                continue
            for q in bank.questions:
                if q.domain not in (None, d.id):
                    continue
                rows.append(
                    {
                        "id": q.id,
                        "domain": d.id,
                        "domain_name": d.name,
                        "sub_moc": q.sub_moc,
                        "prompt": q.prompt,
                        "follow_ups": list(q.follow_ups),
                        "yields": q.yields.value,
                        "pack": lp.name,
                    }
                )
    if as_json:
        typer.echo(json.dumps({"questions": rows}, ensure_ascii=False, indent=2))
        return
    if not rows:
        typer.echo("질문 은행이 없습니다 (Pack 에 interview_bank 미설정).")
        return
    for r in rows:
        typer.echo(f"[{r['domain']}] {r['id']} ({r['sub_moc'] or '-'}) → {r['yields']}")
        typer.echo(f"    {r['prompt']}")
        follow_ups = r["follow_ups"]
        assert isinstance(follow_ups, list)
        for fu in follow_ups:
            typer.echo(f"      ↳ {fu}")


def run(argv: list[str]) -> int:
    """Run the CLI with `argv` and return the exit code (used by tests and __main__)."""
    if not argv:
        argv = ["--help"]  # help on stdout, exit 0 (not a usage error)
    try:
        rc = app(args=argv, prog_name="myelin", standalone_mode=False)
    except click_exc.NoArgsIsHelpError as exc:
        exc.show()
        return EXIT_OK
    except click_exc.UsageError as exc:
        exc.show()
        return EXIT_USAGE
    except typer.Exit as exc:
        return int(exc.exit_code)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1
    # click in non-standalone mode returns the exit code of a `typer.Exit`/`click.Exit`
    return int(rc) if isinstance(rc, int) else EXIT_OK
