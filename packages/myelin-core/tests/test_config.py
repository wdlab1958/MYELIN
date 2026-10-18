"""T2 — myelin.yaml model/loader (정본 §5.3, ADR-0004)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from myelin_core.config import (
    ConfigError,
    Domains,
    MyelinConfig,
    dump_config,
    load_config,
    save_config,
)

SPEC = {
    "owner": {"name": "홍길동", "team": "컨설팅2팀", "email": "gildong@a3sc.co.kr"},
    "language": "ko",
    "packs": ["myelin.core", "a3.security-consulting", "a3.cloud-security", "me.llm-security"],
    "domains": {"primary": "SEC-CONSULT", "research": "LLM-SEC", "growth": "CLOUD-SEC"},
    "level": 1,
    "llm": {"default": "claude", "route": {"confidential": "local", "40_IP/**": "local"}},
    "commons": {"enabled": True, "remote": "git@git.a3sc.internal:myelin/commons.git"},
}


def test_spec_example() -> None:
    cfg = MyelinConfig.model_validate(SPEC)
    assert cfg.domains.all_ids == ["SEC-CONSULT", "LLM-SEC", "CLOUD-SEC"]
    assert cfg.domains.roles == {
        "SEC-CONSULT": "primary",
        "LLM-SEC": "research",
        "CLOUD-SEC": "growth",
    }
    assert cfg.level_name == "drafts"
    assert cfg.pack_names[0] == "myelin.core"


def test_minimal_defaults() -> None:
    cfg = MyelinConfig.model_validate(
        {"owner": {"name": "x"}, "packs": ["myelin.core"], "domains": {"primary": "D1"}}
    )
    assert cfg.level == 1 and cfg.language == "ko"
    assert cfg.llm.default == "claude" and cfg.llm.route["confidential"] == "local"
    assert cfg.commons.enabled is False
    assert cfg.domains.research is None and cfg.domains.extra == []


@pytest.mark.parametrize(
    "patch,needle",
    [
        ({"packs": ["a3.x"]}, "must include myelin.core"),
        ({"packs": ["myelin.core", "myelin.core>=1.0"]}, "more than once"),
        ({"packs": ["myelin.core", "Bad.Name"]}, "invalid"),
        ({"domains": {"primary": "D1", "research": "D1"}}, "distinct"),
        ({"domains": {"primary": "d1"}}, "pattern"),
        ({"level": 4}, "less than or equal to 3"),
        ({"llm": {"default": "gpt"}}, "Input should be"),
        ({"commons": {"enabled": True}}, "commons.remote"),
        ({"owner": {"name": "x", "email": "nope"}}, "not an address"),
        ({"unknown": 1}, "Extra inputs"),
    ],
)
def test_invalid(patch: dict[str, object], needle: str) -> None:
    with pytest.raises(ValidationError, match=needle):
        MyelinConfig.model_validate({**SPEC, **patch})


def test_requirement_syntax_in_packs() -> None:
    cfg = MyelinConfig.model_validate({**SPEC, "packs": ["myelin.core>=1.0", "a3.x~=1.2"]})
    assert cfg.pack_names == ["myelin.core", "a3.x"]


def test_domains_extra_roles() -> None:
    d = Domains(primary="A", extra=["B", "C"])
    assert d.all_ids == ["A", "B", "C"] and d.roles["C"] == "extra"


def test_dump_load_roundtrip(tmp_path: Path) -> None:
    cfg = MyelinConfig.model_validate(SPEC)
    text = dump_config(cfg)
    assert text.startswith("# <Vault>/myelin.yaml")
    save_config(tmp_path, cfg)
    assert load_config(tmp_path) == cfg


def test_load_errors(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"myelin\.yaml not found"):
        load_config(tmp_path)
    (tmp_path / "myelin.yaml").write_text("owner: [", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_config(tmp_path)
    (tmp_path / "myelin.yaml").write_text("- a\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping"):
        load_config(tmp_path)
    (tmp_path / "myelin.yaml").write_text(
        "owner: {name: x}\npacks: [myelin.core]\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="domains"):
        load_config(tmp_path)
