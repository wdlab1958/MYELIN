"""`myelin` CLI — init / add-domain / doctor / stats / packs.

CLI는 얇은 어댑터다. 모든 판단은 myelin_core가 한다.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer

from myelin_cli import __version__
from myelin_core.config import (
    CONFIG_FILE,
    ConfigError,
    add_domain_to_data,
    load_config,
    parse_config,
    update_config,
)
from myelin_core.doctor import run_doctor
from myelin_core.errors import Issue, MyelinError
from myelin_core.loader import CORE_PACK, LoadedPack, discover_packs, resolve
from myelin_core.lock import load_lock
from myelin_core.safety import init_target_issues
from myelin_core.scaffold import apply_plan, domain_index, plan_add_domain, plan_init
from myelin_core.stats import compute_stats

app = typer.Typer(
    name="myelin",
    help="MYELIN — Personal Knowledge OS. 쓸수록 빨라지는 나의 지식 신경망.",
    no_args_is_help=True,
    add_completion=False,
)

PacksOpt = Annotated[
    Path | None,
    typer.Option("--packs", help="Domain Pack 디렉터리 (기본: $MYELIN_PACKS 또는 내장 Pack)"),
]
TodayOpt = Annotated[
    str | None, typer.Option("--today", help="기준 날짜 YYYY-MM-DD (테스트용)", hidden=True)
]
VaultArg = Annotated[Path, typer.Argument(help="Vault 경로")]


# ── 공통 ─────────────────────────────────────────────────────────────────
def _fail(title: str, issues: list[Issue], code: int = 1) -> NoReturn:
    typer.secho(f"✗ {title}", fg=typer.colors.RED, err=True)
    for issue in issues:
        typer.echo(f"  - {issue}", err=True)
    raise typer.Exit(code)


def _today(value: str | None) -> date:
    if value is None:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail("--today 형식 오류", [Issue("--today", "YYYY-MM-DD 형식이어야 합니다")])


def default_packs_dir() -> Path:
    env = os.environ.get("MYELIN_PACKS")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for candidate in (here.parent / "_packs", here.parents[4] / "packs"):
        if (candidate / CORE_PACK / "pack.yaml").is_file():
            return candidate
    _fail(
        "Domain Pack을 찾을 수 없습니다",
        [Issue("--packs", "--packs 옵션이나 MYELIN_PACKS 환경변수로 Pack 폴더를 지정하세요")],
    )


def _load_packs(packs_dir: Path | None) -> dict[str, LoadedPack]:
    try:
        return discover_packs(packs_dir or default_packs_dir())
    except MyelinError as err:
        _fail(err.message, err.issues)


def _resolve(names: list[str], available: dict[str, LoadedPack]) -> list[LoadedPack]:
    try:
        return resolve([CORE_PACK, *names], available)
    except MyelinError as err:
        _fail(err.message, err.issues)


def _interactive(flag: bool) -> bool:
    return flag or sys.stdin.isatty()


def _need(value: str | None, label: str, interactive: bool, **prompt_kw: Any) -> str:
    if value:
        return value
    if not interactive:
        _fail("값이 필요합니다", [Issue(label, "비대화형 실행에서는 옵션으로 지정하세요")])
    return str(typer.prompt(label, **prompt_kw))


def _version(value: bool) -> None:
    if value:
        typer.echo(f"myelin {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=_version, is_eager=True, help="버전")
    ] = False,
) -> None:
    """MYELIN CLI."""


# ── packs ────────────────────────────────────────────────────────────────
@app.command("packs")
def packs_cmd(packs: PacksOpt = None) -> None:
    """설치 가능한 Domain Pack과 Domain 목록."""
    for pack in _load_packs(packs).values():
        m = pack.manifest
        typer.secho(f"{m.pack} {m.version}  [{m.kind.value}]", bold=True)
        for d in m.domains:
            typer.echo(f"  {d.id:<20} {d.label or '':<4} {d.name}")


# ── init ─────────────────────────────────────────────────────────────────
@app.command("init")
def init_cmd(
    target: VaultArg,
    name: Annotated[str | None, typer.Option(help="Vault 주인 이름")] = None,
    pack: Annotated[list[str] | None, typer.Option(help="사용할 Pack (여러 번 지정 가능)")] = None,
    primary: Annotated[str | None, typer.Option(help="업무 근간 Domain ID")] = None,
    research: Annotated[str | None, typer.Option(help="연구 Domain ID")] = None,
    growth: Annotated[str | None, typer.Option(help="성장 Domain ID")] = None,
    extra: Annotated[str | None, typer.Option(help="추가 Domain ID (최대 1개)")] = None,
    level: Annotated[int, typer.Option(min=0, max=3, help="Claude 권한 Level 0~3")] = 1,
    language: Annotated[str, typer.Option(help="노트 언어")] = "ko",
    yes: Annotated[bool, typer.Option("--yes", "-y", help="확인 없이 생성")] = False,
    interactive: Annotated[bool, typer.Option("--interactive", help="대화형 강제")] = False,
    packs: PacksOpt = None,
    today: TodayOpt = None,
) -> None:
    """새 Vault를 만든다. 비어 있지 않은 경로·git 저장소·MYELIN 소스 안에는 만들지 않는다."""
    issues = init_target_issues(target)
    if issues:
        _fail("이 경로에는 Vault를 만들 수 없습니다", issues)

    ask = _interactive(interactive)
    available = _load_packs(packs)
    if not pack and ask:
        choices = [p for p in available if p != CORE_PACK]
        typer.echo("사용할 Pack (쉼표로 구분):")
        for i, p in enumerate(choices, 1):
            typer.echo(f"  {i}. {p}")
        picked = typer.prompt("번호", default="1")
        pack = [choices[int(x) - 1] for x in picked.replace(" ", "").split(",") if x]
    resolved = _resolve(pack or [], available)

    index = domain_index(resolved)
    if ask and not primary:
        typer.echo("선택 가능한 Domain:")
        for d_id, ref in index.items():
            typer.echo(f"  {d_id:<20} {ref.domain.name}")
    owner = _need(name, "--name", ask)
    primary_id = _need(primary, "--primary", ask)
    if ask:
        research = research or typer.prompt("--research (없으면 Enter)", default="") or None
        growth = growth or typer.prompt("--growth (없으면 Enter)", default="") or None

    try:
        cfg = parse_config(
            {
                "owner": {"name": owner},
                "language": language,
                "packs": [p.name for p in resolved],
                "domains": {
                    "primary": primary_id,
                    "research": research,
                    "growth": growth,
                    "extra": [extra] if extra else [],
                },
                "level": level,
            }
        )
        plan = plan_init(cfg, resolved, _today(today))
    except MyelinError as err:
        _fail(err.message, err.issues)

    typer.echo(f"Vault: {target}  ·  Domains: {', '.join(cfg.domains.all())}  ·  Level {cfg.level}")
    typer.echo(f"파일 {len(plan.files)}개를 만듭니다.")
    if not yes and ask and not typer.confirm("진행할까요?", default=True):
        raise typer.Exit(1)
    try:
        apply_plan(target, plan)
    except MyelinError as err:
        _fail(err.message, err.issues)
    typer.secho("✓ Vault를 만들었습니다.", fg=typer.colors.GREEN)
    typer.echo("다음: Obsidian에서 이 폴더를 Vault로 열고, `myelin doctor` 로 상태를 확인하세요.")


# ── add-domain ───────────────────────────────────────────────────────────
@app.command("add-domain")
def add_domain_cmd(
    vault: VaultArg,
    domain: Annotated[str, typer.Option(help="추가할 Domain ID")],
    role: Annotated[str, typer.Option(help="research | growth | extra")] = "extra",
    pack: Annotated[str | None, typer.Option(help="Domain이 들어 있는 Pack (새 Pack일 때)")] = None,
    packs: PacksOpt = None,
    today: TodayOpt = None,
) -> None:
    """기존 Vault에 Domain을 추가한다. 노트는 건드리지 않는다."""
    if role not in ("research", "growth", "extra"):
        _fail("role 오류", [Issue("--role", "research | growth | extra 중 하나")])
    try:
        cfg = load_config(vault)
        load_lock(vault)
    except ConfigError as err:
        _fail(err.message, err.issues)
    if domain in cfg.domains.all():
        _fail("이미 있는 Domain입니다", [Issue("--domain", domain)])
    current = getattr(cfg.domains, role)
    if current:
        _fail(
            "3+1 규칙: 해당 자리가 이미 차 있습니다",
            [Issue(f"{CONFIG_FILE}.domains.{role}", f"현재 {current}")],
        )

    available = _load_packs(packs)
    wanted = [p for p in cfg.packs if p != CORE_PACK]
    added = {pack} if pack and pack not in cfg.packs else set()
    resolved = _resolve([*wanted, *added], available)
    added = {p.name for p in resolved} - set(cfg.packs)
    if domain not in domain_index(resolved):
        _fail(
            "Domain을 찾을 수 없습니다",
            [Issue("--domain", f"{domain} — --pack 으로 Pack을 지정하세요")],
        )

    try:
        new_cfg, text = update_config(
            vault, lambda data: add_domain_to_data(data, role, domain, sorted(added))
        )
        plan = plan_add_domain(vault, new_cfg, text, resolved, added, domain, _today(today))
        apply_plan(vault, plan)
    except MyelinError as err:
        _fail(err.message, err.issues)
    typer.secho(f"✓ {domain} 을(를) {role} 로 추가했습니다.", fg=typer.colors.GREEN)


# ── doctor ───────────────────────────────────────────────────────────────
@app.command("doctor")
def doctor_cmd(
    vault: VaultArg,
    strict: Annotated[bool, typer.Option(help="경고도 실패로 처리")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="JSON 출력")] = False,
    no_location: Annotated[bool, typer.Option("--no-location", help="위치 검사 생략")] = False,
    today: TodayOpt = None,
) -> None:
    """Vault 무결성을 점검한다."""
    findings = run_doctor(vault, today=_today(today), check_location=not no_location)
    errors = sum(1 for f in findings if f.severity == "error")
    warnings = len(findings) - errors
    if as_json:
        typer.echo(json.dumps([f.__dict__ for f in findings], ensure_ascii=False, indent=2))
    else:
        for f in findings:
            color = typer.colors.RED if f.severity == "error" else typer.colors.YELLOW
            typer.secho(str(f), fg=color)
        typer.echo(f"\n오류 {errors} · 경고 {warnings}")
    if errors or (strict and warnings):
        raise typer.Exit(1)


# ── stats ────────────────────────────────────────────────────────────────
@app.command("stats")
def stats_cmd(
    vault: VaultArg,
    as_json: Annotated[bool, typer.Option("--json", help="JSON 출력")] = False,
    today: TodayOpt = None,
) -> None:
    """개인 지표 (명세 §11.1)."""
    s = compute_stats(vault, _today(today)).as_dict()
    if as_json:
        typer.echo(json.dumps(s, ensure_ascii=False, indent=2))
        return
    for key, value in s.items():
        typer.echo(f"{key:<22} {value}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
