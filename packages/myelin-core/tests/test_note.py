from pathlib import Path

import pytest

from myelin_core.errors import NoteParseError
from myelin_core.note import WikiLink, extract_links, parse_note, parse_note_file

FM = """---
id: 20261018-0712-wcet-budget
type: evergreen
domain: [D2, D3]
status: verified
origin: mixed
source: ["[[Lit - ROS2 Executor]]"]
projects: "[[Dogbot]]"
created: 2026-10-18
---
"""


def test_parse_basic() -> None:
    note = parse_note(FM + "# 제목\n\n[[A]] 와 [[B#설계|비]] 그리고 ![[diagram.png]]\n")
    assert note.frontmatter.domain == ["D2", "D3"]
    assert note.title == "20261018-0712-wcet-budget"
    assert note.links == (
        WikiLink("A"),
        WikiLink("B", heading="설계", alias="비"),
        WikiLink("diagram.png", embed=True),
    )
    assert [link.target for link in note.frontmatter_links] == ["Lit - ROS2 Executor", "Dogbot"]
    assert len(note.all_links) == 5


def test_links_in_code_are_ignored() -> None:
    body = "```python\nx = '[[NotALink]]'\n```\n`[[Inline]]` 그리고 [[Real]]\n~~~\n[[Also]]\n~~~\n"
    assert [link.target for link in extract_links(body)] == ["Real"]


def test_empty_link_dropped() -> None:
    assert extract_links("[[|alias]] [[#heading]]") == ()


def test_crlf_and_bom() -> None:
    text = "﻿" + (FM + "body [[X]]\n").replace("\n", "\r\n")
    note = parse_note(text, source="a.md")
    assert note.title == "a" and note.links == (WikiLink("X"),)


def test_dots_close_frontmatter() -> None:
    text = FM.replace("created: 2026-10-18\n---", "created: 2026-10-18\n...")
    assert parse_note(text).frontmatter.origin.value == "mixed"


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("# no frontmatter\n", "missing_frontmatter"),
        ("", "missing_frontmatter"),
        ("---\nid: x\n", "unterminated_frontmatter"),
        ("---\n- a\n- b\n---\n", "frontmatter_not_mapping"),
        ("---\nid: [unclosed\n---\n", "yaml_syntax"),
        ("---\nid: a\nid: b\n---\n", "yaml_syntax"),
    ],
)
def test_structural_errors(text: str, code: str) -> None:
    with pytest.raises(NoteParseError) as info:
        parse_note(text, source="n.md")
    assert info.value.issues[0].code == code
    assert info.value.issues[0].loc.startswith("n.md")


def test_empty_frontmatter_reports_missing_fields() -> None:
    with pytest.raises(NoteParseError) as info:
        parse_note("---\n---\nbody\n", source="n.md")
    locs = {issue.loc for issue in info.value.issues}
    assert {"n.md.id", "n.md.type", "n.md.status", "n.md.origin", "n.md.created"} <= locs


def test_validation_error_has_field_path() -> None:
    with pytest.raises(NoteParseError) as info:
        parse_note(FM.replace("domain: [D2, D3]", "domain: [D2, bad]"), source="n.md")
    assert info.value.issues[0].loc == "n.md.domain[1]"
    assert "n.md.domain[1]" in str(info.value)


def test_parse_file_relative_path(tmp_path: Path) -> None:
    f = tmp_path / "10_Domains" / "WCET 예산.md"
    f.parent.mkdir()
    f.write_text(FM + "x\n", encoding="utf-8")
    note = parse_note_file(f, root=tmp_path)
    assert note.path == "10_Domains/WCET 예산.md"
    assert note.title == "WCET 예산"
    assert parse_note_file(f).path == f.as_posix()


def test_parse_file_bad_encoding(tmp_path: Path) -> None:
    f = tmp_path / "bad.md"
    f.write_bytes(b"---\nid: \xff\xfe\n---\n")
    with pytest.raises(NoteParseError) as info:
        parse_note_file(f, root=tmp_path)
    assert info.value.issues[0].code == "encoding"
