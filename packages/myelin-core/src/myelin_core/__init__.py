"""MYELIN core: schema, note parser, Pack loader, doctor, index (shared by CLI/MCP/Hub)."""

from myelin_core.note import Note, NoteParseError, WikiLink, dump_note, parse_note, read_note
from myelin_core.packs import (
    LoadedPack,
    PackError,
    PackRegistry,
    discover_packs,
    load_pack,
    resolve_packs,
)
from myelin_core.schema import Domain, Frontmatter, Pack

__version__ = "0.1.0a0"

__all__ = [
    "Domain",
    "Frontmatter",
    "LoadedPack",
    "Note",
    "NoteParseError",
    "Pack",
    "PackError",
    "PackRegistry",
    "WikiLink",
    "__version__",
    "discover_packs",
    "dump_note",
    "load_pack",
    "parse_note",
    "read_note",
    "resolve_packs",
]
