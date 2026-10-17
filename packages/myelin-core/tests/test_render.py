"""T5/T6 — template / MOC / taxonomy / CLAUDE.md renderers."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from myelin_core.config import MyelinConfig
from myelin_core.packs.loader import load_pack
from myelin_core.render import (
    PERSONAL_END,
    PERSONAL_START,
    make_note_id,
    render_claude_md,
    render_moc,
    render_taxonomy_md,
    render_template,
)
from myelin_core.vault import AI_WRITE_ALLOW

NOW = datetime(2026, 10, 18, 9, 0)


def _cfg(level: int = 1) -> MyelinConfig:
    return MyelinConfig.model_validate(
        {
            "owner": {"name": "Brian"},
            "packs": ["myelin.core", "brian.physical-ai"],
            "domains": {"primary": "D1", "research": "D3"},
            "level": level,
        }
    )


def test_make_note_id() -> None:
    assert make_note_id(NOW, "WCET Budget!") == "20261018-0900-wcet-budget"
    assert make_note_id(NOW, "***") == "20261018-0900-note"
    assert len(make_note_id(NOW, "x" * 200)) <= 14 + 64


def test_render_template_values() -> None:
    out = render_template(
        "id: {{id}}\ndomain: {{ domain }}\ncreated: {{date}}\nx: {{missing}}",
        {
            "id": "a",
            "domain": ["D1", "D2"],
            "date": date(2026, 10, 18),
        },
    )
    assert out == "id: a\ndomain: [D1, D2]\ncreated: 2026-10-18\nx: "


def test_render_moc_is_valid_note(packs_dir: Path) -> None:
    from myelin_core import parse_note

    lp = load_pack(packs_dir / "brian.physical-ai")
    d3 = next(d for d in lp.pack.domains if d.id == "D3")
    text = render_moc(d3, lp, _cfg(), NOW)
    note = parse_note(text)
    assert note.frontmatter.type.value == "moc" and note.frontmatter.domain == ["D3"]
    assert note.frontmatter.consistency_issues() == []
    assert "**research**" in text and "accent: `lime`" in text
    assert "[[D3 - Sim2Real|Sim2Real]]" in text
    assert len(note.links) == 6


def test_render_taxonomy_md(packs_dir: Path) -> None:
    from myelin_core import parse_note

    core = load_pack(packs_dir / "myelin.core")
    text = render_taxonomy_md([(core.name, core.taxonomies["taxonomy.yaml"])], NOW)
    assert "| MYELIN | myelin, 미엘린 |" in text
    assert PERSONAL_START in text and PERSONAL_END in text
    parse_note(text)


def test_render_claude_md_levels_and_personal(packs_dir: Path) -> None:
    packs = [load_pack(packs_dir / "myelin.core"), load_pack(packs_dir / "brian.physical-ai")]
    t0 = render_claude_md(_cfg(0), packs, NOW, None, ai_write_allow=AI_WRITE_ALLOW)
    assert "Level 0 — read-only" in t0 and "(없음" in t0
    t3 = render_claude_md(_cfg(3), packs, NOW, None, ai_write_allow=AI_WRITE_ALLOW)
    assert "/ip-scan" in t3
    for p in AI_WRITE_ALLOW:
        assert f"`{p}/`" in t3
    assert "**D1**" in t3 and "**D3**" in t3 and "**D4**" not in t3  # only configured domains
    # personal block survives regeneration
    edited = t3.replace(
        "- (여기에 나만의 규칙을 적는다. Pack 재생성 시 보존된다.)", "- 내 규칙 1\n- 내 규칙 2"
    )
    again = render_claude_md(_cfg(1), packs, NOW, edited, ai_write_allow=AI_WRITE_ALLOW)
    assert "- 내 규칙 1\n- 내 규칙 2" in again and "Level 1 — drafts" in again
    assert again.count(PERSONAL_START) == 1
