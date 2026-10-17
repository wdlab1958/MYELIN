"""Vault discovery helpers: pack roots, note iteration, read_all."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from myelin_core.vault import Vault, default_pack_roots


def test_default_pack_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, packs_dir: Path
) -> None:
    monkeypatch.setenv("MYELIN_PACKS", f"/a{os.pathsep}/b")
    roots = default_pack_roots(tmp_path)
    assert roots[:2] == [Path("/a"), Path("/b")]
    assert tmp_path / "packs" in roots
    assert roots[-1] == packs_dir  # repo packs discovered by walking up from the package
    monkeypatch.delenv("MYELIN_PACKS")
    assert default_pack_roots() == [packs_dir]


def test_iter_notes_skips_system_and_hidden(fixtures_dir: Path) -> None:
    v = Vault.open(fixtures_dir / "vaults/basic")
    rels = [v.rel(p) for p in v.iter_note_paths()]
    assert len(rels) == 35
    assert not any(r.startswith("90_System") or r == "CLAUDE.md" or r.startswith(".") for r in rels)
    notes, errors = v.read_all()
    assert len(notes) == 35 and errors == []
    assert Vault.is_vault(fixtures_dir / "vaults/basic") and not Vault.is_vault(fixtures_dir)


def test_declared_domains(fixtures_dir: Path, packs_dir: Path) -> None:
    v = Vault.open(fixtures_dir / "vaults/basic")
    declared = v.declared_domains([packs_dir])
    assert set(declared) == {"D1", "D2", "D3", "D4"}
    assert declared["D3"][1] == "자율학습 Robotics"
