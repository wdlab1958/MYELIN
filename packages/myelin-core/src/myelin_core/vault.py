"""Vault = a directory with `myelin.yaml` (정본 §6.1 folder standard)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from myelin_core.config import CONFIG_FILE, MyelinConfig, load_config
from myelin_core.note import Note, NoteParseError, read_note
from myelin_core.packs.loader import LoadedPack, PackRegistry, discover_packs, resolve_packs

# 정본 §6.1
INBOX = "00_Inbox"
AI_DRAFTS = "00_Inbox/ai-drafts"
CLIPS = "00_Inbox/clips"
DOMAINS = "10_Domains"
PROJECTS = "20_Projects"
RESOURCES = "30_Resources"
IP = "40_IP"
IP_CANDIDATES = "40_IP/candidates"
JOURNAL = "50_Journal"
OUTPUTS = "80_Outputs"
OUTPUT_DRAFTS = "80_Outputs/drafts"
SYSTEM = "90_System"
TEMPLATES = "90_System/templates"
PROMPTS = "90_System/prompts"
TAXONOMY_MD = "90_System/taxonomy.md"
ARCHIVE = "99_Archive"
PATCHES = "_patches"
RUNTIME = ".myelin"
MOC_FILE = "_MOC.md"

STANDARD_DIRS: tuple[str, ...] = (
    INBOX,
    AI_DRAFTS,
    CLIPS,
    DOMAINS,
    PROJECTS,
    RESOURCES,
    IP,
    IP_CANDIDATES,
    JOURNAL,
    OUTPUTS,
    OUTPUT_DRAFTS,
    SYSTEM,
    TEMPLATES,
    PROMPTS,
    ARCHIVE,
    PATCHES,
    RUNTIME,
)
# AI (Claude) may write only here (정본 §3 Fail-closed, §7.2 ALLOW)
AI_WRITE_ALLOW: tuple[str, ...] = (AI_DRAFTS, PATCHES, OUTPUT_DRAFTS, JOURNAL)
# directories excluded from note scanning
SKIP_DIRS: frozenset[str] = frozenset(
    {RUNTIME, ".git", ".obsidian", ".claude", "node_modules", "_patches", "packs"}
)  # <Vault>/packs holds personal Packs (templates are not notes)
NON_NOTE_FILES: frozenset[str] = frozenset({"CLAUDE.md", "README.md"})


OBSIDIAN_DIR = ".obsidian"
OBSIDIAN_THEME_NAME = "MYELIN Emboss"


def default_theme_dir() -> Path | None:
    """Generated Obsidian theme dir (`theme/obsidian-myelin-emboss/`): $MYELIN_THEME_DIR or repo."""
    env = os.environ.get("MYELIN_THEME_DIR")
    if env and (Path(env) / "theme.css").is_file():
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "theme" / "obsidian-myelin-emboss"
        if (cand / "theme.css").is_file() and (cand / "manifest.json").is_file():
            return cand
    return None


def default_pack_roots(vault: Path | None = None) -> list[Path]:
    """Pack search roots: $MYELIN_PACKS, <Vault>/packs, then the repo `packs/` of this checkout."""
    roots: list[Path] = []
    env = os.environ.get("MYELIN_PACKS")
    if env:
        roots += [Path(p) for p in env.split(os.pathsep) if p]
    if vault is not None:
        roots.append(Path(vault) / "packs")
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "packs" / "myelin.core" / "pack.yaml").is_file():
            roots.append(parent / "packs")
            break
    # de-duplicate by resolved path (e.g. $MYELIN_PACKS pointing at the repo packs/), keep order
    seen: set[Path] = set()
    unique: list[Path] = []
    for r in roots:
        key = r.resolve()
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def _is_note_file(p: Path, real_root: Path) -> bool:
    """A regular file whose real path stays inside the Vault.

    Fail-closed (정본 §3): a symlink that escapes the Vault or dangles is not a note — following
    it would read foreign files into the index (or crash on a missing target).
    """
    try:
        return p.is_file() and p.resolve().is_relative_to(real_root)
    except OSError:
        return False


@dataclass
class Vault:
    root: Path
    config: MyelinConfig

    @classmethod
    def open(cls, root: Path) -> Vault:
        root = Path(root).resolve()
        return cls(root=root, config=load_config(root))

    @staticmethod
    def is_vault(root: Path) -> bool:
        return (Path(root) / CONFIG_FILE).is_file()

    def iter_note_paths(self) -> Iterator[Path]:
        real_root = self.root.resolve()
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(
                d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
            )
            rel_dir = Path(dirpath).relative_to(self.root)
            if rel_dir.parts[:1] == (SYSTEM,):
                continue  # templates/prompts are not notes
            for fn in sorted(filenames):
                if fn.endswith(".md") and (rel_dir != Path() or fn not in NON_NOTE_FILES):
                    p = Path(dirpath) / fn
                    if _is_note_file(p, real_root):
                        yield p

    def read_all(self) -> tuple[list[Note], list[NoteParseError]]:
        notes: list[Note] = []
        errors: list[NoteParseError] = []
        for p in self.iter_note_paths():
            try:
                notes.append(read_note(p))
            except NoteParseError as exc:
                errors.append(exc)
        return notes, errors

    def rel(self, path: Path) -> str:
        return Path(path).resolve().relative_to(self.root).as_posix()

    def packs(self, roots: list[Path] | None = None) -> list[LoadedPack]:
        registry: PackRegistry = discover_packs(
            roots if roots is not None else default_pack_roots(self.root)
        )
        return resolve_packs(self.config.packs, registry)

    def declared_domains(
        self, roots: list[Path] | None = None
    ) -> dict[str, tuple[LoadedPack, str]]:
        """Domain ID → (pack, domain name) for every pack in config."""
        out: dict[str, tuple[LoadedPack, str]] = {}
        for lp in self.packs(roots):
            for d in lp.pack.domains:
                out[d.id] = (lp, d.name)
        return out
