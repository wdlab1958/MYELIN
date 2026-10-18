"""`myelin` CLI — init / add-domain / doctor / stats / packs.

CLI는 얇은 어댑터다. 모든 판단은 myelin_core가 한다.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer

from myelin_cli import __version__
from myelin_core.commons import check_note, commons_dir, init_commons
from myelin_core.config import CONFIG_FILE, update_config
from myelin_core.doctor import run_doctor
from myelin_core.errors import Issue, MyelinError
from myelin_core.gitops import Author
from myelin_core.loader import CORE_PACK, LoadedPack, discover_packs, resolve
from myelin_core.metrics import anonymous_metrics
from myelin_core.onboarding import InitRequest, find_packs_dir, prepare_add_domain, prepare_init
from myelin_core.safety import init_target_issues
from myelin_core.scaffold import apply_plan, domain_index
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
    try:
        return find_packs_dir(extra=[Path(__file__).resolve().parent / "_packs"])
    except MyelinError as err:
        _fail(err.message, err.issues)


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

    req = InitRequest(
        owner=owner,
        packs=tuple(p.name for p in resolved if p.name != CORE_PACK),
        primary=primary_id,
        research=research,
        growth=growth,
        extra=extra,
        level=level,
        language=language,
    )
    try:
        prepared = prepare_init(target, req, available, _today(today))
    except MyelinError as err:
        _fail(err.message, err.issues)
    cfg, plan = prepared.config, prepared.plan

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
    available = _load_packs(packs) if Path(vault / CONFIG_FILE).is_file() else {}
    try:
        prepared = prepare_add_domain(vault, domain, role, pack, available, _today(today))
        apply_plan(vault, prepared.plan)
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


# ── commons ──────────────────────────────────────────────────────────────
commons_app = typer.Typer(help="Team Commons — 조직 내부 공유 (opt-in)", no_args_is_help=True)
app.add_typer(commons_app, name="commons")


@commons_app.command("init")
def commons_init_cmd(
    target: Annotated[Path, typer.Argument(help="새 Commons 저장소 폴더 (Vault 밖)")],
    org: Annotated[str, typer.Option(help="조직 이름")],
    name: Annotated[str, typer.Option(help="첫 commit 작성자")] = "MYELIN",
    email: Annotated[str, typer.Option(help="작성자 이메일")] = "myelin@localhost",
) -> None:
    """Commons 저장소 골격(notes · registry · 비식별 정책 · PR 템플릿)을 만든다."""
    try:
        sha = init_commons(target, org, Author(name, email))
    except MyelinError as err:
        _fail(err.message, err.issues)
    typer.secho(f"✓ Commons를 만들었습니다 ({sha[:7]}).", fg=typer.colors.GREEN)
    typer.echo(
        "조직 내부 git 서버에 비공개 저장소로 올리고, 구성원은 clone 후 `myelin commons link`."
    )


@commons_app.command("link")
def commons_link_cmd(
    vault: VaultArg,
    path: Annotated[Path, typer.Argument(help="Commons 저장소의 로컬 clone")],
) -> None:
    """이 Vault에서 Commons 공개를 켠다 (myelin.yaml commons.enabled/path)."""
    target = str(path.expanduser().absolute())

    def mutate(data: Any) -> None:
        if data.get("commons") is None:
            data["commons"] = {}
        data["commons"]["enabled"] = True
        data["commons"]["path"] = target

    try:
        cfg, text = update_config(vault, mutate)
        commons_dir(vault, cfg)
    except MyelinError as err:
        _fail(err.message, err.issues)
    (vault / CONFIG_FILE).write_text(text, encoding="utf-8")
    typer.secho(f"✓ Commons 연결: {target}", fg=typer.colors.GREEN)


@commons_app.command("check")
def commons_check_cmd(
    vault: VaultArg,
    note: Annotated[str, typer.Argument(help="Vault 기준 노트 경로")],
    today: TodayOpt = None,
) -> None:
    """공개 자격과 비식별 검사 결과를 보여 준다 (아무것도 쓰지 않는다)."""
    try:
        chk = check_note(vault, note, _today(today))
    except MyelinError as err:
        _fail(err.message, err.issues)
    for issue in chk.blocks:
        typer.secho(f"✗ {issue}", fg=typer.colors.RED)
    for f in chk.deid.findings:
        typer.secho(f"✗ 비식별 {f.issue()}", fg=typer.colors.RED)
    if not chk.ok:
        raise typer.Exit(1)
    typer.secho(
        f"✓ 공개 가능 → {chk.target} (Hub의 'Commons 제안'에서 확인 후 제안)", fg=typer.colors.GREEN
    )


# ── metrics ──────────────────────────────────────────────────────────────
@app.command("metrics")
def metrics_cmd(
    vault: VaultArg,
    out: Annotated[Path | None, typer.Option("--out", help="저장할 파일 (기본: 화면 출력)")] = None,
    today: TodayOpt = None,
) -> None:
    """opt-in 익명 지표 (네트워크 전송 없음 — 파일을 직접 제출)."""
    try:
        data = anonymous_metrics(vault, _today(today))
    except MyelinError as err:
        _fail(err.message, err.issues)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if out is None:
        typer.echo(text, nl=False)
        return
    out.write_text(text, encoding="utf-8")
    typer.secho(f"✓ {out} — 내용을 확인한 뒤 직접 제출하세요.", fg=typer.colors.GREEN)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
