"""T4/T7 — init_vault (fail-closed) and add_domain."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from myelin_core import read_note
from myelin_core.config import MyelinConfig, load_config
from myelin_core.render import PERSONAL_END, PERSONAL_START
from myelin_core.scaffold import (
    ScaffoldError,
    VaultExistsError,
    add_domain,
    init_vault,
    plan_init,
    resolve_config_packs,
)
from myelin_core.vault import STANDARD_DIRS, Vault

NOW = datetime(2026, 10, 18, 9, 0)


def _cfg(**over: object) -> MyelinConfig:
    data: dict[str, object] = {
        "owner": {"name": "Brian", "team": "A3"},
        "packs": ["myelin.core", "brian.physical-ai"],
        "domains": {"primary": "D1", "research": "D3"},
        "level": 1,
    }
    data.update(over)
    return MyelinConfig.model_validate(data)


def test_init_creates_standard_layout(tmp_path: Path, packs_dir: Path) -> None:
    root = tmp_path / "vault"
    plan = init_vault(root, _cfg(), NOW, pack_roots=[packs_dir])
    for d in STANDARD_DIRS:
        assert (root / d).is_dir(), d
    assert (root / "myelin.yaml").is_file() and (root / "CLAUDE.md").is_file()
    assert (root / "10_Domains/D1/_MOC.md").is_file() and (root / "10_Domains/D3/_MOC.md").is_file()
    assert not (root / "10_Domains/D4").exists()
    names = {p.name for p in (root / "90_System/templates").iterdir()}
    assert {"evergreen.md", "lesson.md", "D3-experiment-log.md"} <= names
    assert "D4-design-rule.md" not in names
    assert (root / ".gitignore").read_text(encoding="utf-8").startswith("# MYELIN runtime")
    assert set(plan.files) >= {"myelin.yaml", "CLAUDE.md", "90_System/taxonomy.md"}
    # everything scaffolded parses and doctor-level consistency holds for MOCs
    for moc in root.glob("10_Domains/*/_MOC.md"):
        assert read_note(moc).frontmatter.consistency_issues() == []
    assert load_config(root) == _cfg()


def test_init_is_fail_closed(tmp_path: Path, packs_dir: Path) -> None:
    root = tmp_path / "vault"
    init_vault(root, _cfg(), NOW, pack_roots=[packs_dir])
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    with pytest.raises(VaultExistsError) as ei:
        init_vault(root, _cfg(level=3), NOW, pack_roots=[packs_dir])
    assert "myelin.yaml" in ei.value.conflicts and "덮어쓰기 금지" in str(ei.value)
    after = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert before == after  # nothing touched
    # a single pre-existing file is enough to abort, and nothing else is created
    other = tmp_path / "other"
    other.mkdir()
    (other / "CLAUDE.md").write_text("mine", encoding="utf-8")
    with pytest.raises(VaultExistsError):
        init_vault(other, _cfg(), NOW, pack_roots=[packs_dir])
    assert [p.name for p in other.iterdir()] == ["CLAUDE.md"]
    # not a directory
    f = tmp_path / "file"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(ScaffoldError, match="not a directory"):
        init_vault(f, _cfg(), NOW, pack_roots=[packs_dir])


def test_init_unknown_domain_or_pack(tmp_path: Path, packs_dir: Path) -> None:
    with pytest.raises(ScaffoldError, match=r"domains \['D9'\] are not declared"):
        init_vault(tmp_path / "v", _cfg(domains={"primary": "D9"}), NOW, pack_roots=[packs_dir])
    from myelin_core import PackError

    with pytest.raises(PackError, match="not found"):
        init_vault(
            tmp_path / "v", _cfg(packs=["myelin.core", "me.ghost"]), NOW, pack_roots=[packs_dir]
        )
    assert not (tmp_path / "v").exists()


def test_plan_is_deterministic(packs_dir: Path) -> None:
    cfg = _cfg()
    packs = resolve_config_packs(cfg, [packs_dir])
    a = plan_init(cfg, packs, NOW)
    b = plan_init(cfg, packs, NOW)
    assert a.files == b.files and a.paths() == b.paths()


def test_add_domain(tmp_path: Path, packs_dir: Path) -> None:
    root = tmp_path / "vault"
    init_vault(root, _cfg(), NOW, pack_roots=[packs_dir])
    # personal edits that must survive
    claude = root / "CLAUDE.md"
    claude.write_text(
        claude.read_text(encoding="utf-8").replace(
            "- (여기에 나만의 규칙을 적는다. Pack 재생성 시 보존된다.)", "- RULE-X"
        ),
        encoding="utf-8",
    )
    tax = root / "90_System/taxonomy.md"
    tax.write_text(
        tax.read_text(encoding="utf-8").replace("## 개인 용어\n", "## 개인 용어\n- TERM-X\n"),
        encoding="utf-8",
    )
    note = root / "10_Domains/D1/My Note.md"
    note.write_text(
        "---\nid: 20261018-0905-my\ntype: fleeting\ncreated: 2026-10-18\n---\nhi\n",
        encoding="utf-8",
    )
    snapshot = {p: p.read_bytes() for p in root.rglob("*.md") if "D4" not in p.parts}

    v = Vault.open(root)
    touched = add_domain(v, "D4", datetime(2026, 10, 19, 10, 0), pack_roots=[packs_dir])
    assert "10_Domains/D4/_MOC.md" in touched and "myelin.yaml" in touched
    assert "90_System/templates/D4-design-rule.md" in touched
    cfg = load_config(root)
    assert cfg.domains.extra == ["D4"] and cfg.domains.all_ids == ["D1", "D3", "D4"]
    assert "- RULE-X" in claude.read_text(encoding="utf-8")
    assert "**D4**" in claude.read_text(encoding="utf-8")
    t = tax.read_text(encoding="utf-8")
    assert "- TERM-X" in t and t.count(PERSONAL_START) == 1 and t.count(PERSONAL_END) == 1
    # existing notes & MOCs untouched byte-for-byte (except the regenerated CLAUDE.md / taxonomy.md)
    for p, content in snapshot.items():
        if p.name in ("CLAUDE.md", "taxonomy.md"):
            continue
        assert p.read_bytes() == content, p

    with pytest.raises(ScaffoldError, match="already configured"):
        add_domain(v, "D4", NOW, pack_roots=[packs_dir])
    with pytest.raises(ScaffoldError, match="no pack declares"):
        add_domain(v, "D9", NOW, pack_roots=[packs_dir])
    with pytest.raises(ScaffoldError, match="no pack declares"):
        add_domain(v, "D2", NOW, pack_name="a3.security-consulting", pack_roots=[packs_dir])


def test_add_domain_from_new_pack_and_conflicts(tmp_path: Path, packs_dir: Path) -> None:
    root = tmp_path / "vault"
    init_vault(root, _cfg(), NOW, pack_roots=[packs_dir])
    v = Vault.open(root)
    add_domain(v, "SEC-CONSULT", NOW, pack_roots=[packs_dir])
    cfg = load_config(root)
    assert "a3.security-consulting" in cfg.pack_names
    assert (root / "10_Domains/SEC-CONSULT/_MOC.md").is_file()
    # refuse to overwrite an existing MOC
    (root / "10_Domains/D2").mkdir()
    (root / "10_Domains/D2/_MOC.md").write_text("mine", encoding="utf-8")
    with pytest.raises(ScaffoldError, match="refusing to overwrite"):
        add_domain(v, "D2", NOW, pack_roots=[packs_dir])
    assert (root / "10_Domains/D2/_MOC.md").read_text(encoding="utf-8") == "mine"


def test_add_domain_ambiguous(tmp_path: Path, packs_dir: Path) -> None:
    import shutil

    extra = tmp_path / "packs"
    extra.mkdir()
    shutil.copytree(packs_dir / "myelin.core", extra / "myelin.core")
    shutil.copytree(packs_dir / "brian.physical-ai", extra / "brian.physical-ai")
    (extra / "me.alt").mkdir()
    (extra / "me.alt/pack.yaml").write_text(
        "pack: me.alt\nkind: personal\nmaintainer: me\nrequires: [myelin.core]\n"
        "domains:\n  - {id: D4, name: alt}\n",
        encoding="utf-8",
    )
    root = tmp_path / "vault"
    init_vault(root, _cfg(), NOW, pack_roots=[extra])
    v = Vault.open(root)
    with pytest.raises(ScaffoldError, match="several packs"):
        add_domain(v, "D4", NOW, pack_roots=[extra])
    add_domain(v, "D4", NOW, pack_name="brian.physical-ai", pack_roots=[extra])
    assert load_config(root).domains.extra == ["D4"]
