"""CHAOS — hostile / broken inputs against myelin-core (notes, vault walk, index, patches, config).

Every case must end in a typed error (NoteParseError / PatchError / ConfigError / ValueError) or a
correct result — never a traceback, a hang, or a write outside the Vault.
"""

from __future__ import annotations

import os
import shutil
import time
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from myelin_core.config import ConfigError, load_config
from myelin_core.doctor import run_doctor
from myelin_core.index import make_snippet, open_index
from myelin_core.note import NoteParseError, parse_note
from myelin_core.patches import (
    APPLIED_DIR,
    REJECTED_DIR,
    PatchError,
    apply_plan,
    check_patch_name,
    history_dest,
    list_patches,
    plan_patch,
    reject_patch,
)
from myelin_core.vault import Vault

FM = "---\nid: 20261018-1000-{slug}\ntype: fleeting\ncreated: 2026-10-18\n{extra}---\n{body}"


def note(slug: str, extra: str = "", body: str = "x\n") -> str:
    return FM.format(slug=slug, extra=extra, body=body)


@pytest.fixture
def vault(tmp_path: Path, fixtures_dir: Path) -> Vault:
    root = tmp_path / "basic"
    shutil.copytree(fixtures_dir / "vaults" / "basic", root)
    return Vault.open(root)


# ----------------------------------------------------------------------------- notes
@pytest.mark.parametrize(
    ("label", "text", "ok"),
    [
        ("unterminated", "---\nid: x\n", False),
        ("yaml-list", "---\n- a\n- b\n---\nx\n", False),
        ("yaml-string", "---\njust a string\n---\nx\n", False),
        ("tabs", "---\nid:\t20261018-1000-t\n\ttype: fleeting\n---\nx\n", False),
        ("empty-block", "---\n---\nx\n", False),
        ("missing-keys", "---\ntype: fleeting\n---\nx\n", False),
        ("unknown-status", note("bs", "status: wat\n"), False),
        (
            "datetime-not-date",
            "---\nid: 20261018-1000-d\ntype: fleeting\ncreated: 2026-10-18 10:00:00\n---\n",
            False,
        ),
        ("zero-bytes", "", False),
        (
            "duplicate-key",
            "---\nid: 20261018-1000-a\nid: 20261018-1000-b\ntype: fleeting\n"
            "created: 2026-10-18\n---\n",
            False,
        ),
        ("deep-nesting", note("deep", "extra: " + "[" * 2000 + "]" * 2000 + "\n"), False),
        ("recursive-anchor", note("anc", "tags: &a [a, *a]\n"), False),
        ("bom", "﻿" + note("bom"), True),
        ("crlf", note("crlf").replace("\n", "\r\n"), True),
        ("domain-as-string", note("ds", "domain: D1\n"), True),
        (
            "date-as-string",
            note("dt", "created: '2026-10-18'\n").replace("created: 2026-10-18\n", "", 1),
            True,
        ),
        (
            "python-tag-is-inert",
            note("py", "extra: !!python/object/apply:os.system [echo pwned]\n"),
            True,
        ),
        ("null-key", "---\n~: 1\n" + note("nk")[4:], True),
        ("nul-in-body", note("nul", body="x\x00y\n"), True),
        ("merge-key", note("mg", "<<: {status: draft}\n"), True),
    ],
)
def test_parse_note_never_raises_anything_but_parse_error(label: str, text: str, ok: bool) -> None:
    if ok:
        n = parse_note(text)
        assert n.frontmatter.id.startswith("20261018-1000-")
        if label == "domain-as-string":
            assert n.frontmatter.domain == ["D1"]
        if label == "python-tag-is-inert":  # RT loader never constructs Python objects
            assert n.frontmatter.extra_fields["extra"] == ["echo pwned"]
    else:
        with pytest.raises(NoteParseError):
            parse_note(text)


# ----------------------------------------------------------------------------- vault walk
def test_vault_walk_skips_symlink_escapes_dangling_links_and_packs(
    vault: Vault, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text(note("out", body="SECRET\n"), encoding="utf-8")
    (vault.root / "30_Resources/esc.md").symlink_to(outside)
    (vault.root / "30_Resources/dangling.md").symlink_to(tmp_path / "nope.md")
    (vault.root / "30_Resources/dirlink").symlink_to(tmp_path)
    inside = vault.root / "30_Resources/Lit - ROS2 Executor.md"
    (vault.root / "30_Resources/alias.md").symlink_to(inside)  # inside the Vault → still a note
    (vault.root / "packs/me.x/templates").mkdir(parents=True)
    (vault.root / "packs/me.x/templates/tpl.md").write_text("not a note", encoding="utf-8")
    names = {p.name for p in vault.iter_note_paths()}
    assert "esc.md" not in names and "dangling.md" not in names and "outside.md" not in names
    assert "tpl.md" not in names and "alias.md" in names
    notes, errors = vault.read_all()
    assert not any("SECRET" in n.body for n in notes) and errors == []
    with open_index(vault) as idx:
        assert idx.search("SECRET") == []
        assert idx.get("30_Resources/esc.md") is None
    report = run_doctor(vault)
    assert all("esc.md" not in f.path and "tpl.md" not in f.path for f in report.findings)


def test_index_refresh_tolerates_files_vanishing_mid_walk(
    vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    ghost = vault.root / "30_Resources/ghost.md"
    ghost.write_text(note("ghost"), encoding="utf-8")
    original = vault.iter_note_paths

    def racy() -> Iterator[Path]:
        for p in original():
            if p.name == "ghost.md":
                p.unlink()  # deleted between os.walk and stat()
            yield p

    monkeypatch.setattr(vault, "iter_note_paths", racy)
    with open_index(vault) as idx:
        assert idx.get("30_Resources/ghost.md") is None
        assert idx.count() == 35


def test_index_survives_broken_notes_and_rebuild(vault: Vault) -> None:
    d = vault.root / "00_Inbox/ai-drafts"
    (d / "bin.md").write_bytes(os.urandom(2048))
    (d / "zero.md").write_bytes(b"")
    (d / "deep.md").write_text(
        note("deep", "x: " + "[" * 3000 + "]" * 3000 + "\n"), encoding="utf-8"
    )
    (d / "dup.md").write_text(note("dup", "id: 20261018-1000-other\n"), encoding="utf-8")
    with open_index(vault) as idx:
        errors = dict(idx.parse_errors())
        assert {Path(p).name for p in errors} == {"bin.md", "zero.md", "deep.md", "dup.md"}
        assert all(msg for msg in errors.values())
        res = idx.rebuild()
        assert res.errors == 4 and idx.count() == 35
        assert idx.stats(date(2026, 10, 18)).parse_errors == 4


# ----------------------------------------------------------------------------- search
def test_snippet_is_linear_and_marks_hits() -> None:
    body = "가나다 lorem ipsum " * 300_000  # ≈ 5.4 MB
    t = time.perf_counter()
    snip = make_snippet(body, ["lorem", "ipsum"])
    assert time.perf_counter() - t < 1.0
    assert "[lorem]" in snip and "[ipsum]" in snip and snip.endswith("…") and len(snip) < 200
    assert make_snippet("short body", ["zzz"]) == "short body"
    assert make_snippet("line1\nline2 hit here", ["HIT"]) == "line1 line2 [hit] here"


def test_search_over_a_5mb_note_is_fast_and_bad_query_is_value_error(vault: Vault) -> None:
    big = vault.root / "30_Resources/big.md"
    big.write_text(note("big", body="가나다 lorem ipsum " * 300_000), encoding="utf-8")
    with open_index(vault) as idx:
        t = time.perf_counter()
        hits = idx.search("lorem ipsum")
        assert time.perf_counter() - t < 5.0
        assert [h.note.path for h in hits] == ["30_Resources/big.md"] and "[lorem]" in hits[
            0
        ].snippet
        with pytest.raises(ValueError, match="invalid search query"):
            idx.search("abc\x00def")
        with pytest.raises(ValueError):
            idx.search("   ")


# ----------------------------------------------------------------------------- patches
PATCH = (
    "---\npatch: 1\ntarget: {target}\nkind: append\norigin: claude\nskill: link\n"
    "created: 2026-10-18\nrationale: r\nstatus: proposed\n---\n## append\n- x\n"
)


@pytest.mark.parametrize(
    "name",
    [
        "a" * 300 + ".patch.md",
        "x\\..\\y.patch.md",
        "a\x00.patch.md",
        ".hidden.patch.md",
        "a/b.patch.md",
        "x.md",
        "",
    ],
)
def test_bad_patch_names_are_rejected_without_touching_disk(vault: Vault, name: str) -> None:
    with pytest.raises(PatchError, match="bad patch name"):
        check_patch_name(name)
    with pytest.raises(PatchError):
        plan_patch(vault.root, name)
    with pytest.raises(PatchError):
        reject_patch(vault.root, name)


def test_malformed_patch_files_are_listed_as_invalid_not_raised(vault: Vault) -> None:
    pdir = vault.root / "_patches"
    (pdir / "badyaml.patch.md").write_text("---\npatch: [\n---\n## append\nx\n", encoding="utf-8")
    (pdir / "bin.patch.md").write_bytes(b"\xff\xfe\x00garbage")
    (pdir / "dupkey.patch.md").write_text(
        "---\npatch: 1\npatch: 1\n---\n## append\nx\n", encoding="utf-8"
    )
    (pdir / "deep.patch.md").write_text(
        "---\nx: " + "[" * 3000 + "]" * 3000 + "\n---\n## append\nx\n", encoding="utf-8"
    )
    (pdir / "escape.patch.md").write_text(PATCH.format(target="../outside.md"), encoding="utf-8")
    (pdir / "ip.patch.md").write_text(
        PATCH.format(target="40_IP/candidates/Agentic CAD 검증 루프.md"), encoding="utf-8"
    )
    listed = {p["file"]: p for p in list_patches(vault.root)}
    for bad in ("badyaml", "bin", "dupkey", "deep", "escape"):
        assert (
            listed[f"{bad}.patch.md"]["status"] == "invalid" and listed[f"{bad}.patch.md"]["error"]
        )
        with pytest.raises(PatchError):
            plan_patch(vault.root, f"{bad}.patch.md")
    plan = plan_patch(vault.root, "ip.patch.md")
    assert not plan.ok and any("40_IP" in i for i in plan.issues)
    with pytest.raises(PatchError):
        apply_plan(vault.root, plan)


def test_patch_history_is_never_overwritten(vault: Vault, fixtures_dir: Path) -> None:
    name = "20261018-1700-d2-moc-missing-links.patch.md"
    src = fixtures_dir / "skill-outputs/link" / name
    moc = vault.root / "10_Domains/D2/_MOC.md"
    original = moc.read_text(encoding="utf-8")
    (vault.root / APPLIED_DIR).mkdir(parents=True)
    (vault.root / APPLIED_DIR / name).write_text("HISTORY", encoding="utf-8")
    shutil.copy(src, vault.root / "_patches" / name)
    touched = apply_plan(vault.root, plan_patch(vault.root, name))
    assert touched[-1] == f"{APPLIED_DIR}/20261018-1700-d2-moc-missing-links (2).patch.md"
    assert (vault.root / APPLIED_DIR / name).read_text(encoding="utf-8") == "HISTORY"
    assert "status: applied" in (vault.root / touched[-1]).read_text(encoding="utf-8")
    # second apply of a re-proposed copy → (3)
    moc.write_text(original, encoding="utf-8")
    shutil.copy(src, vault.root / "_patches" / name)
    assert history_dest(vault.root, APPLIED_DIR, name).name.endswith(" (3).patch.md")
    # reject history likewise
    (vault.root / REJECTED_DIR).mkdir(parents=True)
    (vault.root / REJECTED_DIR / name).write_text("HISTORY", encoding="utf-8")
    touched = reject_patch(vault.root, name)
    assert touched[-1].endswith(" (2).patch.md")
    assert (vault.root / REJECTED_DIR / name).read_text(encoding="utf-8") == "HISTORY"


# ----------------------------------------------------------------------------- config
@pytest.mark.parametrize(
    "text",
    [
        "",
        "a: [b",
        "- a\n",
        "owner: {name: x}\npacks: [myelin.core]\ndomains: {primary: D1}\nlevel: 9\n",
        "owner: {name: x}\npacks: [myelin.core]\ndomains: {primary: D1}\nlevel: -1\n",
        "owner: {name: x}\npacks: [myelin.core]\ndomains: {primary: D1}\nlevel: two\n",
        "owner: {name: x}\npacks: [myelin.core]\ndomains: {primary: D1, research: D1}\n",
        "owner: {name: x}\npacks: [myelin.core]\ndomains: {primary: D1}\nlevel: 1\nlevel: 2\n",
        "owner: {name: x}\npacks: [myelin.core, ../x]\ndomains: {primary: D1}\n",
        "owner: {name: x}\npacks: [myelin.core]\ndomains: {primary: ../x}\n",
        "owner: {name: x}\npacks: [a3.x]\ndomains: {primary: D1}\n",
    ],
)
def test_corrupt_config_is_config_error(tmp_path: Path, text: str) -> None:
    (tmp_path / "myelin.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError) as ei:
        load_config(tmp_path)
    assert "myelin.yaml" in str(ei.value)


def test_missing_config_is_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path)
