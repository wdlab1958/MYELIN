"""Vault 만들기·Domain 추가 — CLI `init`/`add-domain` 과 Hub 온보딩 마법사가 공유하는 단일 로직.

둘 다 plan → apply 2단계다. `prepare_*` 는 파일을 쓰지 않는다 (Hub의 미리보기가 이것을 쓴다).
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from myelin_core.config import (
    CONFIG_FILE,
    VaultConfig,
    add_domain_to_data,
    load_config,
    parse_config,
    update_config,
)
from myelin_core.errors import Issue, MyelinError
from myelin_core.loader import CORE_PACK, LoadedPack, discover_packs, resolve
from myelin_core.lock import load_lock
from myelin_core.safety import init_target_issues
from myelin_core.scaffold import Plan, domain_index, plan_add_domain, plan_init

ROLES_ADDABLE = ("research", "growth", "extra")


class OnboardingError(MyelinError):
    """Vault를 만들거나 Domain을 추가할 수 없음."""


def find_packs_dir(explicit: Path | None = None, extra: Sequence[Path] = ()) -> Path:
    """`explicit` → `$MYELIN_PACKS` → `extra`(패키지 내장) → 소스 트리 `packs/`."""
    env = os.environ.get("MYELIN_PACKS")
    if explicit is not None:
        return explicit
    if env:
        return Path(env)
    source_tree = Path(__file__).resolve().parents[4] / "packs"
    for candidate in (*extra, source_tree):
        if (candidate / CORE_PACK / "pack.yaml").is_file():
            return candidate
    raise OnboardingError(
        "Domain Pack을 찾을 수 없습니다",
        [Issue("--packs", "--packs 옵션이나 MYELIN_PACKS 환경변수로 Pack 폴더를 지정하세요")],
    )


def load_packs(packs_dir: Path) -> dict[str, LoadedPack]:
    return discover_packs(packs_dir)


@dataclass(frozen=True)
class InitRequest:
    owner: str
    packs: tuple[str, ...] = ()
    primary: str = ""
    research: str | None = None
    growth: str | None = None
    extra: str | None = None
    level: int = 1
    language: str = "ko"


@dataclass(frozen=True)
class Prepared:
    config: VaultConfig
    packs: list[LoadedPack]
    plan: Plan


def prepare_init(
    target: Path, req: InitRequest, available: dict[str, LoadedPack], today: date
) -> Prepared:
    """새 Vault 계획. 위치가 안전하지 않거나 입력이 틀리면 OnboardingError/MyelinError."""
    issues = init_target_issues(target)
    if issues:
        raise OnboardingError("이 경로에는 Vault를 만들 수 없습니다", issues)
    if not req.owner.strip():
        raise OnboardingError("값이 필요합니다", [Issue("owner.name", "이름을 입력하세요")])
    if not req.primary:
        raise OnboardingError("값이 필요합니다", [Issue("domains.primary", "업무 근간 Domain")])
    resolved = resolve([CORE_PACK, *req.packs], available)
    cfg = parse_config(
        {
            "owner": {"name": req.owner},
            "language": req.language,
            "packs": [p.name for p in resolved],
            "domains": {
                "primary": req.primary,
                "research": req.research or None,
                "growth": req.growth or None,
                "extra": [req.extra] if req.extra else [],
            },
            "level": req.level,
        }
    )
    return Prepared(cfg, resolved, plan_init(cfg, resolved, today))


def prepare_add_domain(
    vault: Path,
    domain: str,
    role: str,
    pack: str | None,
    available: dict[str, LoadedPack],
    today: date,
) -> Prepared:
    """기존 Vault에 Domain 추가 계획. 노트는 건드리지 않는다."""
    if role not in ROLES_ADDABLE:
        raise OnboardingError("role 오류", [Issue("--role", "research | growth | extra 중 하나")])
    cfg = load_config(vault)
    load_lock(vault)
    if domain in cfg.domains.all():
        raise OnboardingError("이미 있는 Domain입니다", [Issue("--domain", domain)])
    current = getattr(cfg.domains, role)
    if current:
        raise OnboardingError(
            "3+1 규칙: 해당 자리가 이미 차 있습니다",
            [Issue(f"{CONFIG_FILE}.domains.{role}", f"현재 {current}")],
        )
    wanted = [p for p in cfg.packs if p != CORE_PACK]
    added = {pack} if pack and pack not in cfg.packs else set()
    resolved = resolve([*wanted, *added], available)
    new_packs = {p.name for p in resolved} - set(cfg.packs)
    if domain not in domain_index(resolved):
        raise OnboardingError(
            "Domain을 찾을 수 없습니다",
            [Issue("--domain", f"{domain} — --pack 으로 Pack을 지정하세요")],
        )
    new_cfg, text = update_config(
        vault, lambda data: add_domain_to_data(data, role, domain, sorted(new_packs))
    )
    plan = plan_add_domain(vault, new_cfg, text, resolved, new_packs, domain, today)
    return Prepared(new_cfg, resolved, plan)
