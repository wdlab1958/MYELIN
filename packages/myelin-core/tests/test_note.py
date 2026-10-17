"""T2 — Note parser: frontmatter + body + wikilinks, round-trip."""

from __future__ import annotations

from pathlib import Path

import pytest

from myelin_core import Note, NoteParseError, dump_note, parse_note, read_note
from myelin_core.note import WikiLink, extract_wikilinks, split_frontmatter


def test_parse_good(good_note_text: str) -> None:
    note = parse_note(good_note_text)
    assert isinstance(note, Note)
    assert note.id == "20261018-0712-wcet-budget"
    assert note.title == "WCET budget"
    assert note.body.startswith("# WCET budget")
    assert note.link_targets == {"Lit - ROS2 Executor", "Control Loop"}


def test_roundtrip_identical(good_note_text: str) -> None:
    assert dump_note(parse_note(good_note_text)) == good_note_text


def test_roundtrip_preserves_comments_and_order() -> None:
    text = (
        "---\n"
        "id: 20261018-0712-a  # 자동 생성\n"
        "type: lesson\n"
        "created: 2026-10-18\n"
        "aliases:\n"
        "  - A\n"
        "zzz: keep-me\n"
        "---\n"
        "body\n"
    )
    assert dump_note(parse_note(text)) == text


def test_crlf_and_bom_tolerated() -> None:
    text = (
        "\ufeff---\r\nid: 20261018-0712-a\r\ntype: fleeting\r\ncreated: 2026-10-18\r\n---\r\nhi\r\n"
    )
    note = parse_note(text)
    assert note.id == "20261018-0712-a"


@pytest.mark.parametrize(
    "text,needle",
    [
        ("no frontmatter here\n", "not found"),
        ("---\nid: x\n", "not closed"),
        ("---\n---\nbody", "empty"),
        ("---\n- just\n- a list\n---\n", "mapping"),
        ("---\nid: [unclosed\n---\n", "not valid YAML"),
        ("---\nid: bad id\ntype: fleeting\ncreated: 2026-10-18\n---\n", "schema violation"),
    ],
)
def test_parse_errors(text: str, needle: str) -> None:
    with pytest.raises(NoteParseError) as ei:
        parse_note(text)
    assert needle in str(ei.value)


def test_split_frontmatter_body() -> None:
    y, b = split_frontmatter("---\na: 1\n---\nline1\n---\nnot-a-delimiter\n")
    assert y == "a: 1"
    assert b == "line1\n---\nnot-a-delimiter\n"


def test_wikilinks_variants() -> None:
    body = (
        "[[A]] [[B|alias]] [[C#Heading]] [[D#^blk|x]] ![[img.png]] [[A]] again\n"
        "`[[in-code]]`\n"
        "```\n[[fenced]]\n```\n"
        "\\[[escaped]]\n"
    )
    links = extract_wikilinks(body)
    assert links == (
        WikiLink("A"),
        WikiLink("B"),
        WikiLink("C"),
        WikiLink("D"),
        WikiLink("img.png", embed=True),
    )


def test_read_note_from_disk(tmp_path: Path, good_note_text: str) -> None:
    p = tmp_path / "n.md"
    p.write_text(good_note_text, encoding="utf-8")
    note = read_note(p)
    assert note.path == p
    assert note.title == "WCET budget"


def test_read_note_errors_carry_path(tmp_path: Path) -> None:
    p = tmp_path / "bad.md"
    p.write_text("nope", encoding="utf-8")
    with pytest.raises(NoteParseError) as ei:
        read_note(p)
    assert ei.value.path == p
    assert str(p) in str(ei.value)
    p.write_bytes(b"\xff\xfe---\n")
    with pytest.raises(NoteParseError, match="UTF-8"):
        read_note(p)


def test_title_fallbacks(tmp_path: Path) -> None:
    text = "---\nid: 20261018-0712-my-slug\ntype: fleeting\ncreated: 2026-10-18\n---\nno heading\n"
    assert parse_note(text).title == "my-slug"
    p = tmp_path / "File Name.md"
    p.write_text(text, encoding="utf-8")
    assert read_note(p).title == "File Name"
