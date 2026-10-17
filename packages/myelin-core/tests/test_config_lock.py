from pathlib import Path
from typing import Any

import pytest

from myelin_core.config import (
    CONFIG_FILE,
    ConfigError,
    add_domain_to_data,
    load_config,
    parse_config,
    render_config,
    update_config,
)
from myelin_core.errors import Issue
from myelin_core.loader import discover_packs, resolve
from myelin_core.lock import LOCK_FILE, load_lock, lock_from_packs, render_lock
from myelin_core.yamlio import load_yaml

ROOT = Path(__file__).resolve().parents[3]


def cfg_data(**over: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "owner": {"name": "홍길동", "team": "팀: A", "email": "a@example.com"},
        "packs": ["myelin.core", "brian.physical-ai"],
        "domains": {"primary": "AI-ML-AX", "extra": ["EMBEDDED-SW"]},
    }
    data.update(over)
    return data


def test_render_then_parse_roundtrip() -> None:
    cfg = parse_config(cfg_data(level=3))
    text = render_config(cfg)
    again = parse_config(load_yaml(text, CONFIG_FILE, ConfigError))
    assert again == cfg
    assert '"팀: A"' in text and "remote: null" in text


@pytest.mark.parametrize(
    ("over", "loc"),
    [
        ({"packs": ["brian.physical-ai"]}, "myelin.yaml.packs"),
        ({"packs": ["myelin.core", "myelin.core"]}, "myelin.yaml.packs"),
        ({"domains": {"primary": "A", "research": "A"}}, "myelin.yaml.domains"),
        ({"domains": {"primary": "A", "extra": ["B", "C"]}}, "myelin.yaml.domains.extra"),
        ({"level": 4}, "myelin.yaml.level"),
        ({"language": "korean"}, "myelin.yaml.language"),
        ({"surprise": 1}, "myelin.yaml.surprise"),
        ({"llm": {"default": "gpt"}}, "myelin.yaml.llm.default"),
    ],
)
def test_invalid_config(over: dict[str, Any], loc: str) -> None:
    with pytest.raises(ConfigError) as info:
        parse_config(cfg_data(**over))
    assert loc in {i.loc for i in info.value.issues}


def test_not_mapping_and_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        parse_config(["a"])
    with pytest.raises(ConfigError) as info:
        load_config(tmp_path)
    assert info.value.issues[0].code == "missing_file"


def test_missing_domains_and_roles() -> None:
    cfg = parse_config(cfg_data(domains={"primary": "A", "growth": "B", "extra": ["C"]}))
    assert cfg.domains.all() == ["A", "B", "C"]
    assert cfg.domains.role_of("B") == "growth" and cfg.domains.role_of("C") == "extra"
    assert cfg.missing_domains({"A"}) == [
        Issue("myelin.yaml.domains.growth", "unknown domain: B", "unknown_domain"),
        Issue("myelin.yaml.domains.extra", "unknown domain: C", "unknown_domain"),
    ]


def test_round_trip_update_preserves_comments_and_order(tmp_path: Path) -> None:
    cfg = parse_config(cfg_data(domains={"primary": "AI-ML-AX", "growth": "AUTO-DESIGN"}))
    text = "# 내 메모\n" + render_config(cfg)
    (tmp_path / CONFIG_FILE).write_text(text, encoding="utf-8")
    new_cfg, new_text = update_config(
        tmp_path, lambda d: add_domain_to_data(d, "research", "X", ["org.x"])
    )
    assert new_cfg.domains.research == "X"
    assert new_text.startswith("# 내 메모\n")
    lines = new_text.splitlines()
    assert lines.index("  research: X") < lines.index("  growth: AUTO-DESIGN")
    assert lines.index("  - org.x") < lines.index("domains:")
    # 다음 키 위의 주석은 새 항목에 끌려가지 않는다
    assert lines[lines.index("  - org.x") + 1].startswith("# 3+1")
    _, extra_text = update_config(tmp_path, lambda d: add_domain_to_data(d, "extra", "Y", []))
    assert "    - Y" in extra_text


def test_role_appended_at_end_when_no_later_keys(tmp_path: Path) -> None:
    (tmp_path / CONFIG_FILE).write_text(
        "myelin: 1\nowner: {name: a}\npacks: [myelin.core]\ndomains:\n  primary: A\n",
        encoding="utf-8",
    )
    cfg, _ = update_config(tmp_path, lambda d: add_domain_to_data(d, "growth", "B", []))
    assert cfg.domains.growth == "B"


def test_update_rejects_invalid_result(tmp_path: Path) -> None:
    (tmp_path / CONFIG_FILE).write_text(render_config(parse_config(cfg_data())), encoding="utf-8")
    with pytest.raises(ConfigError):
        update_config(tmp_path, lambda d: d.__setitem__("level", 9))


def test_lock_roundtrip(tmp_path: Path) -> None:
    packs = resolve(["brian.physical-ai"], discover_packs(ROOT / "packs"))
    lock = lock_from_packs(packs)
    (tmp_path / "90_System").mkdir()
    (tmp_path / LOCK_FILE).write_text(render_lock(lock), encoding="utf-8")
    loaded = load_lock(tmp_path)
    assert loaded == lock
    assert "EMBEDDED-SW" in loaded.domain_ids()
    found = loaded.domain("EMBEDDED-SW")
    assert found is not None and found.label == "D2"
    assert loaded.domain("NOPE") is None


def test_lock_errors(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_lock(tmp_path)
    (tmp_path / "90_System").mkdir()
    (tmp_path / LOCK_FILE).write_text("myelin_lock: 2\npacks: []\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_lock(tmp_path)
