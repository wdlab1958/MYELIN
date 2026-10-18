"""T5~T10 — SKILL.md contracts, Level gating, skill-output fixtures pass doctor, patches parse."""

from __future__ import annotations

import io
import shutil
from datetime import datetime
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from myelin_core.config import MyelinConfig
from myelin_core.doctor import run_doctor
from myelin_core.levels import SKILLS, available_skills, skill_table
from myelin_core.patches import PatchError, read_patch
from myelin_core.scaffold import init_vault
from myelin_core.vault import Vault

SKILLS_DIR = Path(__file__).resolve().parents[2] / "plugin" / "skills"
OUTPUTS = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "skill-outputs"


def _frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    fm = text.split("---\n", 2)[1]
    data = YAML(typ="safe").load(io.StringIO(fm))
    assert isinstance(data, dict)
    return data


def test_seven_skills_exist_and_match_table() -> None:
    dirs = {p.name for p in SKILLS_DIR.iterdir() if p.is_dir()}
    assert (
        dirs
        == {s.name for s in SKILLS}
        == {"ingest", "distill", "interview", "review", "link", "compose", "ip-scan"}
    )
    for s in SKILLS:
        md = SKILLS_DIR / s.name / "SKILL.md"
        fm = _frontmatter(md)
        assert fm["name"] == s.name
        assert isinstance(fm["description"], str) and len(fm["description"]) < 1536
        body = md.read_text(encoding="utf-8")
        assert f"Level **{s.min_level}**" in body or f"Level ≥ {s.min_level}" in body, s.name
        assert s.write_scope in body, (s.name, s.write_scope)
        assert "_COMMON.md" in body
        assert "allowed-tools" in fm
        if s.name == "ip-scan":
            assert fm.get("disable-model-invocation") is True
    assert (SKILLS_DIR / "_COMMON.md").is_file()


def test_level_gating_table() -> None:
    assert [s.name for s in available_skills(0)] == []
    assert [s.name for s in available_skills(1)] == ["ingest", "distill", "interview", "review"]
    assert [s.name for s in available_skills(2)] == [
        "ingest",
        "distill",
        "interview",
        "review",
        "link",
        "compose",
    ]
    assert len(available_skills(3)) == 7
    t0 = skill_table(0)
    assert all(r["enabled"] is False for r in t0)  # Level 0: every write skill disabled
    assert sum(1 for r in skill_table(3) if r["enabled"]) == 7


@pytest.fixture
def skill_vault(tmp_path: Path, repo_root: Path) -> Vault:
    cfg = MyelinConfig.model_validate(
        {
            "owner": {"name": "t"},
            "packs": ["myelin.core", "brian.physical-ai"],
            "domains": {"primary": "D1", "research": "D2", "growth": "D3"},
            "level": 3,
        }
    )
    root = tmp_path / "vault"
    init_vault(root, cfg, datetime(2026, 10, 18, 9, 0), pack_roots=[repo_root / "packs"])
    # anchor notes the fixtures link to
    d2 = root / "10_Domains/D2"
    for title, slug in [
        ("WCET 예산은 측정값의 1.5배로 잡는다", "wcet"),
        ("ISR 안에서 로그를 찍지 않는다", "isr"),
        ("ROS2 Executor 선택 ADR", "adr"),
        ("Lit - ROS2 Executor", "lit"),
    ]:
        (d2 / f"{title}.md").write_text(
            f"---\nid: 20261001-09{len(slug):02d}-{slug}\ntype: evergreen\ndomain: [D2]\n"
            "status: verified\n"
            f"origin: human\nconfidence: high\nclassification: internal\nshare: false\nsource: []\n"
            f"created: 2026-10-01\nreviewed: 2026-10-02\ntags: []\n---\n# {title}\n[[_MOC]]\n",
            encoding="utf-8",
        )
    (root / "00_Inbox/오늘 회의 메모 - 평가 지표.md").write_text(
        "---\nid: 20261015-0930-meeting\ntype: fleeting\ncreated: 2026-10-15\n---\n# memo\n",
        encoding="utf-8",
    )
    return Vault.open(root)


SCOPE = {
    "ingest": "00_Inbox/ai-drafts",
    "distill": "00_Inbox/ai-drafts",
    "interview": "00_Inbox/ai-drafts",
    "review": "50_Journal",
    "compose": "80_Outputs/drafts",
    "ip-scan": "40_IP/candidates",
}


@pytest.mark.parametrize("skill", sorted(SCOPE))
def test_skill_output_fixture_passes_doctor(
    skill_vault: Vault, repo_root: Path, skill: str
) -> None:
    """Each SKILL.md output contract, placed in its write scope, yields 0 doctor errors (T6/T7)."""
    src = OUTPUTS / skill
    files = sorted(src.glob("*.md"))
    assert files, skill
    for f in files:
        shutil.copy(f, skill_vault.root / SCOPE[skill] / f.name)
    report = run_doctor(skill_vault, pack_roots=[repo_root / "packs"])
    errors = [x for x in report.findings if x.severity == "error"]
    assert errors == [], errors
    # ai outputs are drafts with origin claude (ip-scan keeps confidential + share false)
    from myelin_core import read_note

    for f in files:
        fm = read_note(skill_vault.root / SCOPE[skill] / f.name).frontmatter
        assert fm.origin.value == "claude" and fm.status.value == "draft"
        if skill == "ip-scan":
            assert fm.classification.value == "confidential" and fm.share is False


def test_link_patch_fixtures_parse(skill_vault: Vault) -> None:
    patches = sorted((OUTPUTS / "link").glob("*.patch.md"))
    assert len(patches) == 2
    kinds = set()
    for p in patches:
        patch = read_patch(p)
        kinds.add(patch.kind)
        assert patch.skill == "link" and patch.status == "proposed"
        assert (skill_vault.root / patch.target).exists(), patch.target
        if patch.kind == "replace":
            target_text = (skill_vault.root / patch.target).read_text(encoding="utf-8")
            assert target_text.count(patch.sections["before"]) <= 1
    assert kinds == {"append", "replace"}
    # patches live in _patches and are not notes
    for p in patches:
        shutil.copy(p, skill_vault.root / "_patches" / p.name)
    assert not [f for f in run_doctor(skill_vault).findings if f.path.startswith("_patches")]


def test_patch_errors(tmp_path: Path) -> None:
    good = (
        "---\npatch: 1\ntarget: 10_Domains/D1/_MOC.md\nkind: append\nskill: link\n"
        "created: 2026-10-18\nrationale: r\n---\n## append\n- x\n"
    )
    p = tmp_path / "ok.patch.md"
    p.write_text(good, encoding="utf-8")
    assert read_patch(p).kind == "append"
    with pytest.raises(PatchError, match="requires sections"):
        read_patch(_w(tmp_path, good.replace("## append\n- x\n", "")))
    with pytest.raises(PatchError, match="must not be empty"):
        read_patch(_w(tmp_path, good.replace("- x\n", "")))
    with pytest.raises(PatchError, match="schema violation"):
        read_patch(_w(tmp_path, good.replace("kind: append", "kind: delete")))
    with pytest.raises(PatchError, match="outside _patches"):
        read_patch(_w(tmp_path, good.replace("target: 10_Domains/D1/_MOC.md", "target: ../x.md")))
    with pytest.raises(PatchError, match="not found"):
        read_patch(_w(tmp_path, "no frontmatter"))
    with pytest.raises(PatchError, match="mapping"):
        read_patch(_w(tmp_path, "---\n- a\n---\n## append\nx\n"))
    rep = good.replace("kind: append", "kind: replace").replace(
        "## append\n- x\n", "## before\na\n## after\nb\n"
    )
    assert read_patch(_w(tmp_path, rep)).sections == {"before": "a", "after": "b"}


def _w(tmp: Path, text: str) -> Path:
    p = tmp / f"p{abs(hash(text))}.patch.md"
    p.write_text(text, encoding="utf-8")
    return p
