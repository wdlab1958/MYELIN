"""T10 — tests/fixtures/vaults/basic: 30+ notes, every enum value covered, all parse clean."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from myelin_core import read_note
from myelin_core.schema import Classification, Confidence, NoteType, Origin, Status


def _notes(fixtures_dir: Path):
    vault = fixtures_dir / "vaults/basic"
    return vault, sorted(
        p for p in vault.rglob("*.md") if p.name != "CLAUDE.md" and "90_System" not in p.parts
    )


def test_vault_has_30_plus_valid_notes(fixtures_dir: Path) -> None:
    vault, files = _notes(fixtures_dir)
    assert len(files) >= 30
    notes = [read_note(p) for p in files]
    assert len({n.id for n in notes}) == len(notes)
    for n in notes:
        assert n.frontmatter.consistency_issues() == [], (
            n.path,
            n.frontmatter.consistency_issues(),
        )
    manifest = json.loads((vault / ".fixture-manifest.json").read_text(encoding="utf-8"))
    assert manifest["count"] == len(notes)


def test_vault_covers_every_enum(fixtures_dir: Path) -> None:
    _, files = _notes(fixtures_dir)
    fms = [read_note(p).frontmatter for p in files]
    assert {f.type for f in fms} == set(NoteType)
    assert {f.status for f in fms} == set(Status)
    assert {f.origin for f in fms} == set(Origin)
    assert {f.confidence for f in fms} == set(Confidence)
    assert {f.classification for f in fms} == set(Classification)
    assert any(f.share for f in fms) and any(not f.share for f in fms)
    assert any(len(f.domain) >= 2 for f in fms)  # cross-domain (KPI §11.1)
    assert any(f.domain == [] for f in fms)


def test_vault_layout_and_ai_draft_placement(fixtures_dir: Path) -> None:
    vault, files = _notes(fixtures_dir)
    for d in [
        "00_Inbox/ai-drafts",
        "10_Domains/D1/_MOC.md",
        "40_IP",
        "50_Journal",
        "80_Outputs",
        "90_System",
        "99_Archive",
        "_patches",
        "myelin.yaml",
        "CLAUDE.md",
    ]:
        assert (vault / d).exists(), d
    # origin: claude + status: draft notes live only in 00_Inbox/ai-drafts (fail-closed, 정본 §3)
    for p in files:
        fm = read_note(p).frontmatter
        if fm.origin is Origin.CLAUDE and fm.status is Status.DRAFT:
            assert p.parent == vault / "00_Inbox/ai-drafts", p
    # confidential notes are never share: true and live under 40_IP
    for p in files:
        fm = read_note(p).frontmatter
        if fm.classification is Classification.CONFIDENTIAL:
            assert not fm.share and "40_IP" in p.parts, p


def test_vault_links_resolve(fixtures_dir: Path) -> None:
    _, files = _notes(fixtures_dir)
    notes = [read_note(p) for p in files]
    # Obsidian-style: file stem or vault-relative path without .md (doctor._resolve_targets)
    vault = fixtures_dir / "vaults/basic"
    rel = {n.path: n.path.relative_to(vault).as_posix()[:-3] for n in notes if n.path}
    titles = {n.path.stem for n in notes if n.path} | set(rel.values())
    for n in notes:
        for t in n.link_targets:
            assert t in titles, (n.path, t)
            # Level 2 link-patch (2026-10-19): a MOC link names its own Domain folder, so Obsidian
            # opens that Domain's _MOC rather than an arbitrary one of the four same-named files.
            if t.endswith("_MOC"):
                assert n.path and t == rel[n.path].rsplit("/", 1)[0] + "/_MOC", (n.path, t)
    c = Counter(len(n.links) for n in notes)
    assert c[0] >= 1  # at least one orphan-ish note (no outgoing links) for later doctor fixtures
