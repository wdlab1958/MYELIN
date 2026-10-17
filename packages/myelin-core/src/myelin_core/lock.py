"""`90_System/myelin.lock.yaml` — Vault에 설치된 Pack·Domain의 스냅샷 (ADR-0005).

doctor·stats가 Pack 소스 없이도 Domain 목록을 알 수 있게 한다.
init·add-domain이 생성하는 시스템 파일이며 사용자가 고치지 않는다.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from myelin_core.config import ConfigError
from myelin_core.errors import Issue, issues_from_validation
from myelin_core.loader import LoadedPack
from myelin_core.pack import Accent, PackKind
from myelin_core.yamlio import load_yaml

LOCK_FILE = "90_System/myelin.lock.yaml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LockedDomain(_Strict):
    id: str
    label: str | None = None
    name: str
    accent: Accent


class LockedPack(_Strict):
    name: str
    version: str
    kind: PackKind
    domains: list[LockedDomain]


class VaultLock(_Strict):
    myelin_lock: Literal[1] = 1
    packs: list[LockedPack]

    def domain_ids(self) -> set[str]:
        return {d.id for p in self.packs for d in p.domains}

    def domain(self, domain_id: str) -> LockedDomain | None:
        for p in self.packs:
            for d in p.domains:
                if d.id == domain_id:
                    return d
        return None


def lock_from_packs(packs: Sequence[LoadedPack]) -> VaultLock:
    return VaultLock(
        packs=[
            LockedPack(
                name=p.name,
                version=p.manifest.version,
                kind=p.manifest.kind,
                domains=[
                    LockedDomain(id=d.id, label=d.label, name=d.name, accent=d.accent)
                    for d in p.domains
                ],
            )
            for p in packs
        ]
    )


def _q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_lock(lock: VaultLock) -> str:
    lines = [
        "# 자동 생성 파일 — 직접 고치지 마세요 (myelin init / add-domain 이 관리).",
        f"myelin_lock: {lock.myelin_lock}",
        "packs:",
    ]
    for p in lock.packs:
        lines += [f"  - name: {p.name}", f"    version: {p.version}", f"    kind: {p.kind.value}"]
        if not p.domains:
            lines.append("    domains: []")
            continue
        lines.append("    domains:")
        for d in p.domains:
            lines += [
                f"      - id: {d.id}",
                f"        label: {_q(d.label) if d.label else 'null'}",
                f"        name: {_q(d.name)}",
                f"        accent: {d.accent.value}",
            ]
    return "\n".join(lines) + "\n"


def load_lock(vault: Path) -> VaultLock:
    path = vault / LOCK_FILE
    if not path.is_file():
        raise ConfigError(
            f"{LOCK_FILE} 가 없습니다", [Issue(LOCK_FILE, "file not found", "missing_file")]
        )
    data = load_yaml(path.read_text(encoding="utf-8"), LOCK_FILE, ConfigError)
    try:
        return VaultLock.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(
            f"{LOCK_FILE} 검증 실패", issues_from_validation(exc, prefix=LOCK_FILE)
        ) from exc
