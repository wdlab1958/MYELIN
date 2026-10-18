"""개인 설정 `myelin.yaml` (명세 §5.3, ADR-0005).

- 읽기: safe 로더 + Pydantic 검증 (알 수 없는 필드 거부).
- 새로 쓰기: `render_config` — 주석이 달린 결정론적 텍스트.
- 고쳐 쓰기: `update_config` — ruamel round-trip으로 사용자의 주석·순서를 보존한다.
"""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from ruamel.yaml import YAML

from myelin_core.errors import Issue, MyelinError, issues_from_validation
from myelin_core.frontmatter import DomainId
from myelin_core.pack import NonEmpty, PackName
from myelin_core.yamlio import load_yaml

CONFIG_FILE = "myelin.yaml"
CORE_PACK = "myelin.core"

LEVEL_DESCRIPTIONS = {
    0: "읽기 전용 — Claude는 Vault를 읽기만 한다",
    1: "초안 — ai-drafts에 초안을 쓸 수 있다",
    2: "링크 제안 — _patches에 링크·MOC 변경을 제안할 수 있다",
    3: "정기 리뷰 — 주간 리뷰·특허 후보 추출까지",
}

Route = Literal["claude", "local"]


class ConfigError(MyelinError):
    """myelin.yaml 을 읽거나 검증할 수 없음."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Owner(_Strict):
    name: NonEmpty
    team: str | None = None
    email: str | None = None


class Roles(_Strict):
    """3+1 규칙: 업무 근간·연구·성장 각 1개 + 추가 최대 1개 (명세 §5.4)."""

    primary: DomainId
    research: DomainId | None = None
    growth: DomainId | None = None
    extra: Annotated[list[DomainId], Field(max_length=1)] = Field(default_factory=list)

    @model_validator(mode="after")
    def _distinct(self) -> Roles:
        ids = self.all()
        if len(set(ids)) != len(ids):
            raise ValueError("a domain can hold only one role")
        return self

    def all(self) -> list[str]:
        ids = [self.primary, self.research, self.growth, *self.extra]
        return [i for i in ids if i is not None]

    def role_of(self, domain_id: str) -> str:
        for role in ("primary", "research", "growth"):
            if getattr(self, role) == domain_id:
                return role
        return "extra"


def _default_routes() -> dict[str, Route]:
    return {"confidential": "local", "40_IP/**": "local"}


class LlmRouting(_Strict):
    default: Route = "claude"
    route: dict[str, Route] = Field(default_factory=lambda: _default_routes())


class Commons(_Strict):
    enabled: bool = False
    remote: str | None = None


class McpSettings(_Strict):
    """MYELIN MCP 서버 (ADR-0006). 기본은 읽기 전용."""

    write_drafts: bool = False


class VaultConfig(_Strict):
    myelin: Literal[1] = 1
    owner: Owner
    language: Annotated[str, Field(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")] = "ko"
    packs: list[PackName] = Field(min_length=1)
    domains: Roles
    level: Annotated[int, Field(ge=0, le=3)] = 1
    llm: LlmRouting = Field(default_factory=LlmRouting)
    commons: Commons = Field(default_factory=Commons)
    mcp: McpSettings = Field(default_factory=McpSettings)

    @field_validator("packs")
    @classmethod
    def _core_and_unique(cls, value: list[str]) -> list[str]:
        if CORE_PACK not in value:
            raise ValueError(f"{CORE_PACK} must be listed")
        if len(set(value)) != len(value):
            raise ValueError("contains duplicates")
        return value

    def missing_domains(self, known: set[str]) -> list[Issue]:
        return [
            Issue(
                f"{CONFIG_FILE}.domains.{self.domains.role_of(d)}",
                f"unknown domain: {d}",
                "unknown_domain",
            )
            for d in self.domains.all()
            if d not in known
        ]


def parse_config(data: Any) -> VaultConfig:
    if not isinstance(data, dict):
        raise ConfigError(
            f"{CONFIG_FILE} 최상위는 mapping이어야 합니다",
            [Issue(CONFIG_FILE, "top-level must be a mapping", "not_mapping")],
        )
    try:
        return VaultConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(
            f"{CONFIG_FILE} 검증 실패", issues_from_validation(exc, prefix=CONFIG_FILE)
        ) from exc


def load_config(vault: Path) -> VaultConfig:
    path = vault / CONFIG_FILE
    if not path.is_file():
        raise ConfigError(
            f"{CONFIG_FILE} 가 없습니다: {vault}",
            [Issue(CONFIG_FILE, "file not found — MYELIN Vault가 아닙니다", "missing_file")],
        )
    return parse_config(load_yaml(path.read_text(encoding="utf-8"), CONFIG_FILE, ConfigError))


def _q(value: str) -> str:
    """YAML double-quoted 스칼라 (JSON 문자열은 유효한 YAML이다)."""
    return json.dumps(value, ensure_ascii=False)


def render_config(cfg: VaultConfig) -> str:
    d = cfg.domains
    lines = [
        "# MYELIN 개인 설정 — 이 Vault의 주인과 Domain을 정한다.",
        "# 수정 후 `myelin doctor` 로 확인하세요. Domain 추가는 `myelin add-domain` 을 권장합니다.",
        f"myelin: {cfg.myelin}",
        "owner:",
        f"  name: {_q(cfg.owner.name)}",
    ]
    if cfg.owner.team:
        lines.append(f"  team: {_q(cfg.owner.team)}")
    if cfg.owner.email:
        lines.append(f"  email: {_q(cfg.owner.email)}")
    lines += [
        f"language: {cfg.language}",
        "packs:",
        *(f"  - {p}" for p in cfg.packs),
        "# 3+1 규칙: primary(업무 근간) · research(연구) · growth(성장) + extra 최대 1개",
        "domains:",
        f"  primary: {d.primary}",
    ]
    if d.research:
        lines.append(f"  research: {d.research}")
    if d.growth:
        lines.append(f"  growth: {d.growth}")
    lines.append(f"  extra: [{', '.join(d.extra)}]")
    lines += [
        f"# Claude 권한 Level: {cfg.level} = {LEVEL_DESCRIPTIONS[cfg.level]}",
        f"level: {cfg.level}",
        "# confidential 노트와 40_IP 는 로컬 LLM으로만 처리한다.",
        "llm:",
        f"  default: {cfg.llm.default}",
        "  route:",
        *(f"    {_q(k)}: {v}" for k, v in cfg.llm.route.items()),
        "# 팀 공유(Commons)는 opt-in. 개인 Vault는 기본적으로 어디에도 공유되지 않는다.",
        "commons:",
        f"  enabled: {'true' if cfg.commons.enabled else 'false'}",
        f"  remote: {_q(cfg.commons.remote) if cfg.commons.remote else 'null'}",
        "# MCP 서버(Claude Desktop 등 연결)는 기본 읽기 전용. true면 ai-drafts 초안 쓰기 허용.",
        "mcp:",
        f"  write_drafts: {'true' if cfg.mcp.write_drafts else 'false'}",
    ]
    return "\n".join(lines) + "\n"


ROLE_ORDER = ("primary", "research", "growth", "extra")


def _rt_yaml() -> YAML:
    rt = YAML(typ="rt")
    rt.preserve_quotes = True
    rt.indent(mapping=2, sequence=4, offset=2)  # render_config 와 같은 "  - item" 형식
    rt.representer.add_representer(
        type(None), lambda r, _: r.represent_scalar("tag:yaml.org,2002:null", "null")
    )
    return rt


def _append_keep_comment(seq: Any, value: str) -> None:
    """목록 끝에 붙은 주석(다음 키 위의 주석)이 새 항목 위로 끌려가지 않게 옮겨 붙인다."""
    last = len(seq) - 1
    comment = seq.ca.items.pop(last, None) if last >= 0 else None
    seq.append(value)
    if comment is not None:
        seq.ca.items[len(seq) - 1] = comment


def add_domain_to_data(data: Any, role: str, domain_id: str, new_packs: list[str]) -> None:
    """round-trip 데이터에 Pack과 Domain 역할을 추가한다 (순서·주석 보존)."""
    for name in new_packs:
        _append_keep_comment(data["packs"], name)
    domains = data["domains"]
    if role == "extra":
        _append_keep_comment(domains["extra"], domain_id)
        return
    keys = list(domains.keys())
    later = [k for k in ROLE_ORDER[ROLE_ORDER.index(role) + 1 :] if k in keys]
    pos = keys.index(later[0]) if later else len(keys)
    domains.insert(pos, role, domain_id)


def update_config(vault: Path, mutate: Callable[[Any], None]) -> tuple[VaultConfig, str]:
    """round-trip으로 읽어 `mutate` 를 적용하고, 검증된 새 텍스트를 돌려준다 (쓰기는 호출자 몫)."""
    path = vault / CONFIG_FILE
    rt = _rt_yaml()
    data = rt.load(path.read_text(encoding="utf-8"))
    mutate(data)
    buf = io.StringIO()
    rt.dump(data, buf)
    text = buf.getvalue()
    cfg = parse_config(load_yaml(text, CONFIG_FILE, ConfigError))
    return cfg, text
