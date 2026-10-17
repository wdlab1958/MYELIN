"""T11 — every invalid pack fixture fails with a PackError naming the problem and the path."""

from __future__ import annotations

from pathlib import Path

import pytest

from myelin_core import PackError, load_pack

# dir name == pack name (loader enforces it), except me.name-mismatch which tests that rule
EXPECTED: dict[str, str] = {
    "me.missing-pack-file": "pack.yaml not found",
    "me.bad-yaml": "invalid YAML",
    "me.empty-file": "file is empty",
    "me.unknown-field": "sub_moc: unknown field",
    "me.name-mismatch": "must match its directory name",
    "me.bad-accent": "accent 'amber' is not an Emboss accent token",
    "me.no-core": "must require myelin.core",
    "me.core-with-domains": "core pack must not declare domains",
    "me.missing-ref": "referenced path 'interviews.yaml' does not exist",
    "me.empty-templates": "contains no *.md templates",
    "me.iv-domain": "references domain 'Y' not declared",
    "me.bad-version": "invalid version 'v1'",
    "me.dup-domains": "duplicate domain id(s) in pack: ['X']",
    "me.path-escape": "must be relative and inside the pack directory",
}


def test_fixture_set_is_complete(fixtures_dir: Path) -> None:
    dirs = {p.name for p in (fixtures_dir / "packs/invalid").iterdir() if p.is_dir()}
    assert dirs == set(EXPECTED)
    assert len(dirs) >= 10  # 정본 P1 Gate: 10종 이상


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_invalid_pack_has_clear_error(fixtures_dir: Path, name: str) -> None:
    pack_dir = fixtures_dir / "packs/invalid" / name
    with pytest.raises(PackError) as ei:
        load_pack(pack_dir)
    msg = str(ei.value)
    assert EXPECTED[name] in msg, msg
    assert str(pack_dir) in msg  # path always included
    assert ei.value.path.is_relative_to(pack_dir) or ei.value.path == pack_dir
