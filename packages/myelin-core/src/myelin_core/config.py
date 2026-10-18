"""`<Vault>/myelin.yaml` — 개인 설정 (정본 §5.3). See ADR-0004 for the few clarifications.

```yaml
owner: { name: 홍길동, team: 컨설팅2팀, email: gildong@a3sc.co.kr }
language: ko
packs: [myelin.core, a3.security-consulting, a3.cloud-security, me.llm-security]
domains:
  primary: SEC-CONSULT      # 업무 근간
  research: LLM-SEC         # 연구 관심
  growth: CLOUD-SEC         # 성장 목표
level: 1                    # 0 read-only | 1 drafts | 2 link-patch | 3 scheduled review
llm:
  default: claude
  route: { confidential: local, "40_IP/**": local }
commons: { enabled: true, remote: git@git.a3sc.internal:myelin/commons.git }
```
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from myelin_core.schema.frontmatter import DOMAIN_ID_RE
from myelin_core.schema.pack import PACK_NAME_RE, Requirement

CONFIG_FILE = "myelin.yaml"
DomainIdField = Annotated[str, Field(pattern=DOMAIN_ID_RE.pattern)]
Level = Annotated[
    int, Field(ge=0, le=3, description="0 read-only | 1 drafts | 2 link-patch | 3 scheduled review")
]

LEVEL_NAMES = {0: "read-only", 1: "drafts", 2: "link-patch", 3: "scheduled review"}


class ConfigError(ValueError):
    def __init__(self, path: Path, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Owner(_Strict):
    name: str = Field(min_length=1)
    team: str = ""
    email: str = ""

    @field_validator("email")
    @classmethod
    def _email_shape(cls, v: str) -> str:
        if v and ("@" not in v or v.startswith("@") or v.endswith("@")):
            raise ValueError(f"email {v!r} is not an address")
        return v


class Domains(_Strict):
    """3 + 1 규칙 (정본 §5.4): primary / research / growth, 선택적 extra (3개월 운영 후)."""

    primary: DomainIdField
    research: DomainIdField | None = None
    growth: DomainIdField | None = None
    extra: list[DomainIdField] = Field(default_factory=list)

    @model_validator(mode="after")
    def _distinct(self) -> Domains:
        ids = self.all_ids
        if len(set(ids)) != len(ids):
            raise ValueError(f"domains must be distinct: {ids}")
        return self

    @property
    def all_ids(self) -> list[str]:
        return [d for d in [self.primary, self.research, self.growth, *self.extra] if d]

    @property
    def roles(self) -> dict[str, str]:
        out: dict[str, str] = {self.primary: "primary"}
        if self.research:
            out[self.research] = "research"
        if self.growth:
            out[self.growth] = "growth"
        for e in self.extra:
            out[e] = "extra"
        return out


def _default_route() -> dict[str, Literal["claude", "local"]]:
    return {"confidential": "local", "40_IP/**": "local"}


class LLM(_Strict):
    default: Literal["claude", "local"] = "claude"
    route: dict[str, Literal["claude", "local"]] = Field(default_factory=_default_route)


class Commons(_Strict):
    enabled: bool = False
    remote: str | None = None
    local: str | None = None  # path of the local Commons clone used by publish
    metrics_opt_in: bool = False  # §11.2 anonymous metrics (ADR-0010)

    @model_validator(mode="after")
    def _remote_when_enabled(self) -> Commons:
        if self.enabled and not self.remote:
            raise ValueError("commons.enabled: true requires commons.remote")
        return self


class MCP(_Strict):
    """MYELIN MCP server policy (ADR-0007). Read-only by default."""

    write_draft: bool = False  # register the write_draft tool (also needs level >= 1)
    expose_confidential: bool = False  # return confidential bodies / include them in search


class MyelinConfig(_Strict):
    owner: Owner
    language: str = "ko"
    packs: list[str] = Field(min_length=1)
    domains: Domains
    level: Level = 1
    llm: LLM = Field(default_factory=LLM)
    commons: Commons = Field(default_factory=Commons)
    mcp: MCP = Field(default_factory=MCP)

    @field_validator("packs")
    @classmethod
    def _pack_names(cls, v: list[str]) -> list[str]:
        for name in v:
            if not PACK_NAME_RE.match(Requirement(name).name):
                raise ValueError(f"invalid pack name {name!r}")
        if "myelin.core" not in [Requirement(n).name for n in v]:
            raise ValueError("packs must include myelin.core")
        if len({Requirement(n).name for n in v}) != len(v):
            raise ValueError("packs lists the same pack more than once")
        return v

    @property
    def pack_names(self) -> list[str]:
        return [Requirement(n).name for n in self.packs]

    @property
    def level_name(self) -> str:
        return LEVEL_NAMES[self.level]


def _yaml() -> YAML:
    y = YAML(typ="rt")
    y.default_flow_style = None
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def load_config(vault: Path) -> MyelinConfig:
    path = Path(vault) / CONFIG_FILE
    if not path.is_file():
        raise ConfigError(
            path, "myelin.yaml not found — is this a MYELIN Vault? (run `myelin init`)"
        )
    try:
        data = YAML(typ="safe").load(io.StringIO(path.read_text(encoding="utf-8")))
    except YAMLError as exc:
        raise ConfigError(path, f"invalid YAML: {exc}") from None
    if not isinstance(data, dict):
        raise ConfigError(path, "top level must be a mapping")
    try:
        return MyelinConfig.model_validate(data)
    except ValidationError as exc:
        lines = [
            f"  - {'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}"
            for e in exc.errors()
        ]
        raise ConfigError(path, "schema violation:\n" + "\n".join(lines)) from None


def dump_config(cfg: MyelinConfig) -> str:
    data = cfg.model_dump(mode="json", exclude_none=True)
    buf = io.StringIO()
    buf.write(
        "# <Vault>/myelin.yaml — MYELIN 개인 설정 (정본 §5.3).\n"
        "# `myelin init` 이 생성, 사람이 편집한다.\n"
    )
    _yaml().dump(data, buf)
    return buf.getvalue()


def save_config(vault: Path, cfg: MyelinConfig) -> Path:
    path = Path(vault) / CONFIG_FILE
    path.write_text(dump_config(cfg), encoding="utf-8")
    return path
