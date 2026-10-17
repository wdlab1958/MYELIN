"""노트 파서 — Markdown + YAML frontmatter + wikilink. 원본 파일은 읽기만 한다."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from myelin_core.errors import Issue, NoteParseError, issues_from_validation
from myelin_core.frontmatter import Frontmatter
from myelin_core.yamlio import load_yaml

_FENCE_RE = re.compile(r"^(```|~~~).*?^\1[ \t]*$", re.MULTILINE | re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_WIKILINK_RE = re.compile(r"(!?)\[\[([^\[\]\n]+?)\]\]")
_FM_CLOSE = ("---", "...")
_BOM = chr(0xFEFF)


@dataclass(frozen=True)
class WikiLink:
    target: str
    heading: str | None = None
    alias: str | None = None
    embed: bool = False

    @classmethod
    def parse(cls, inner: str, embed: bool = False) -> WikiLink:
        target, _, alias = inner.partition("|")
        target, _, heading = target.partition("#")
        return cls(
            target=target.strip(),
            heading=heading.strip() or None,
            alias=alias.strip() or None,
            embed=embed,
        )


@dataclass(frozen=True)
class Note:
    title: str
    frontmatter: Frontmatter
    body: str
    links: tuple[WikiLink, ...]
    path: str | None = None

    @property
    def frontmatter_links(self) -> tuple[WikiLink, ...]:
        """`source`·`projects` 필드 안의 wikilink."""
        found: list[WikiLink] = []
        for value in (*self.frontmatter.source, *self.frontmatter.projects):
            found.extend(extract_links(value))
        return tuple(found)

    @property
    def all_links(self) -> tuple[WikiLink, ...]:
        return self.links + self.frontmatter_links


def extract_links(text: str) -> tuple[WikiLink, ...]:
    """코드 블록·인라인 코드 안의 링크는 무시한다."""
    stripped = _INLINE_CODE_RE.sub("", _FENCE_RE.sub("", text))
    links = [
        WikiLink.parse(m.group(2), embed=m.group(1) == "!") for m in _WIKILINK_RE.finditer(stripped)
    ]
    return tuple(link for link in links if link.target)


def split_frontmatter(text: str, source: str) -> tuple[str, str]:
    """(frontmatter YAML, 본문)으로 나눈다.

    frontmatter가 없으면 오류다 (모든 노트는 frontmatter 필수).
    """
    text = text.removeprefix(_BOM).replace("\r\n", "\n")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise NoteParseError(
            f"frontmatter가 없습니다: {source}",
            [Issue(f"{source}:1", "첫 줄이 '---' 여야 합니다", "missing_frontmatter")],
        )
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() in _FM_CLOSE:
            return "\n".join(lines[1:idx]), "\n".join(lines[idx + 1 :])
    raise NoteParseError(
        f"frontmatter가 닫히지 않았습니다: {source}",
        [Issue(f"{source}:1", "닫는 '---' 가 없습니다", "unterminated_frontmatter")],
    )


def parse_note(text: str, source: str = "<string>", title: str | None = None) -> Note:
    fm_text, body = split_frontmatter(text, source)
    data = load_yaml(fm_text, source, NoteParseError)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise NoteParseError(
            f"frontmatter는 mapping이어야 합니다: {source}",
            [
                Issue(
                    f"{source}:frontmatter",
                    "key: value 형식이어야 합니다",
                    "frontmatter_not_mapping",
                )
            ],
        )
    try:
        fm = Frontmatter.model_validate(data)
    except ValidationError as exc:
        raise NoteParseError(
            f"frontmatter 검증 실패: {source}", issues_from_validation(exc, prefix=source)
        ) from exc
    if title is None:
        title = Path(source).stem if source != "<string>" else fm.id
    return Note(title=title, frontmatter=fm, body=body, links=extract_links(body), path=None)


def parse_note_file(path: Path, root: Path | None = None) -> Note:
    rel = path.relative_to(root).as_posix() if root is not None else path.as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise NoteParseError(
            f"UTF-8로 읽을 수 없습니다: {rel}", [Issue(rel, "UTF-8 디코딩 실패", "encoding")]
        ) from exc
    note = parse_note(text, source=rel, title=path.stem)
    return Note(
        title=note.title, frontmatter=note.frontmatter, body=note.body, links=note.links, path=rel
    )
