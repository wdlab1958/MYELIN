"""Note = YAML frontmatter + Markdown body. Round-trip safe parsing (ruamel.yaml RT loader).

- `parse_note(text)` → `Note` (validated `Frontmatter` + body + wikilinks).
- `dump_note(note)` → text identical to the input for well-formed notes (comments/order kept).
- Unknown extra frontmatter keys are preserved (ADR-0003).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

from myelin_core.schema.frontmatter import Frontmatter

FM_DELIM = "---"
# [[Target]], [[Target|alias]], [[Target#heading]], [[Target#^block]], ![[embed]]
WIKILINK_RE = re.compile(
    r"(?<!\\)(?P<embed>!)?\[\[(?P<target>[^\[\]|#]+?)(?:#[^\[\]|]*)?(?:\|[^\[\]]*)?\]\]"
)
FENCE_RE = re.compile(r"^(```|~~~)", re.M)


class NoteParseError(ValueError):
    """Raised when a note has no/invalid frontmatter. `.path` is set when parsed from disk."""

    def __init__(self, message: str, path: Path | None = None) -> None:
        self.path = path
        super().__init__(f"{path}: {message}" if path else message)


@dataclass(frozen=True)
class WikiLink:
    target: str
    embed: bool = False


@dataclass
class Note:
    frontmatter: Frontmatter
    body: str
    raw_frontmatter: CommentedMap = field(repr=False)
    path: Path | None = None
    links: tuple[WikiLink, ...] = ()

    @property
    def id(self) -> str:
        return self.frontmatter.id

    @property
    def title(self) -> str:
        """First H1 in the body, else the file stem, else the id slug."""
        for line in self.body.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        if self.path is not None:
            return self.path.stem
        return self.frontmatter.id.split("-", 2)[-1]

    @property
    def link_targets(self) -> set[str]:
        return {link.target for link in self.links}

    @property
    def link_stems(self) -> set[str]:
        """Targets reduced to the note they name (see `link_stem`); what index/stats match on."""
        return {link_stem(link.target) for link in self.links}


def link_stem(target: str) -> str:
    """Obsidian basename of a wikilink target: `10_Domains/D1/_MOC` → `_MOC`, `_MOC` → `_MOC`.

    Path-qualified links are how Obsidian disambiguates same-named notes (every Domain has a
    `_MOC.md`). Index/stats key notes by file stem, so a path-qualified link must count as a link
    to that stem; the doctor keeps full path resolution (`doctor._resolve_targets`).
    """
    return target.strip().rsplit("/", 1)[-1]


def _yaml() -> YAML:
    y = YAML(typ="rt")
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def split_frontmatter(text: str) -> tuple[str, str]:
    """Return (yaml_text, body). Raises NoteParseError when the leading `---` block is missing."""
    if text.startswith("﻿"):
        text = text[1:]
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != FM_DELIM:
        raise NoteParseError("frontmatter block (`---`) not found at start of file")
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r") == FM_DELIM:
            yaml_text = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1 :])
            return yaml_text, body
    raise NoteParseError("frontmatter block is not closed (missing second `---`)")


def extract_wikilinks(body: str) -> tuple[WikiLink, ...]:
    """Wikilinks outside fenced code blocks, in order of appearance, de-duplicated."""
    out: list[WikiLink] = []
    seen: set[tuple[str, bool]] = set()
    in_fence = False
    for line in body.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        # strip inline code spans
        line = re.sub(r"`[^`]*`", "", line)
        for m in WIKILINK_RE.finditer(line):
            key = (m.group("target").strip(), bool(m.group("embed")))
            if key not in seen:
                seen.add(key)
                out.append(WikiLink(target=key[0], embed=key[1]))
    return tuple(out)


def _to_plain(obj: Any) -> Any:
    """CommentedMap/Seq → plain dict/list so Pydantic sees ordinary Python objects."""
    if isinstance(obj, dict):
        return {str(k): _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_plain(v) for v in obj]
    return obj


def parse_note(text: str, path: Path | None = None) -> Note:
    try:
        yaml_text, body = split_frontmatter(text)
    except NoteParseError as exc:
        raise NoteParseError(str(exc), path) from None
    try:
        loaded = _yaml().load(io.StringIO(yaml_text))
    except YAMLError as exc:
        raise NoteParseError(f"frontmatter is not valid YAML: {exc}", path) from None
    except RecursionError:  # e.g. thousands of nested brackets — hostile or corrupt input
        raise NoteParseError("frontmatter is nested too deeply", path) from None
    if loaded is None:
        raise NoteParseError("frontmatter block is empty", path)
    if not isinstance(loaded, CommentedMap):
        raise NoteParseError("frontmatter must be a mapping", path)
    try:
        fm = Frontmatter.model_validate(_to_plain(loaded))
    except ValidationError as exc:
        raise NoteParseError(
            f"frontmatter schema violation:\n{format_validation_error(exc)}", path
        ) from None
    except RecursionError:
        raise NoteParseError("frontmatter is nested too deeply", path) from None
    return Note(
        frontmatter=fm, body=body, raw_frontmatter=loaded, path=path, links=extract_wikilinks(body)
    )


def read_note(path: Path) -> Note:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise NoteParseError(f"not UTF-8: {exc}", path) from None
    return parse_note(text, path=path)


def dump_note(note: Note) -> str:
    buf = io.StringIO()
    _yaml().dump(note.raw_frontmatter, buf)
    yaml_text = buf.getvalue()
    if not yaml_text.endswith("\n"):
        yaml_text += "\n"
    return f"{FM_DELIM}\n{yaml_text}{FM_DELIM}\n{note.body}"


def format_validation_error(exc: ValidationError) -> str:
    lines = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "<root>"
        lines.append(f"  - {loc}: {err['msg']}")
    return "\n".join(lines)
