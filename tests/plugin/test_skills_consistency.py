"""Agent-test campaign — SKILL.md ↔ myelin_core.levels ↔ Guard ↔ Frontmatter schema consistency.

The Skill files are the instructions an agent follows; they must never tell it to do something the
Guard will block or the schema will reject.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from myelin_core import parse_note, read_note
from myelin_core.levels import LEVEL_ALLOW, SKILLS, allowed_dirs
from myelin_core.patches import parse_patch
from myelin_core.schema.export import json_schema
from myelin_core.schema.frontmatter import Frontmatter, Origin, Status
from tests.plugin.conftest import make_vault, run_hook

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "plugin" / "skills"
COMMON = SKILLS_DIR / "_COMMON.md"
OUTPUTS = ROOT / "tests" / "fixtures" / "skill-outputs"
TOP_DIRS = (
    "00_Inbox",
    "10_Domains",
    "20_Projects",
    "30_Resources",
    "40_IP",
    "50_Journal",
    "80_Outputs",
    "90_System",
    "99_Archive",
    "_patches",
)
LEVEL_RE = re.compile(r"최소 Level:?\s*\*\*(\d)\*\*")
SCOPE_RE = re.compile(r"쓰기 범위:?\s*\*\*`([^`]+)`\*\*")
PATH_RE = re.compile(r"`((?:" + "|".join(map(re.escape, TOP_DIRS)) + r")/[^`]*)`")
PLACEHOLDER_RE = re.compile(r"<[^>]+>")


def _split(md: Path) -> tuple[dict[str, object], str]:
    text = md.read_text(encoding="utf-8")
    assert text.startswith("---\n"), md
    _, fm, body = text.split("---\n", 2)
    data = YAML(typ="safe").load(io.StringIO(fm))
    assert isinstance(data, dict)
    return data, body


def _declared_write_paths(body: str) -> list[str]:
    """Backticked Vault paths on lines that say the skill *creates* a file there."""
    paths: list[str] = []
    for line in body.splitlines():
        if "만든다" not in line and "새 파일" not in line:
            continue
        for m in PATH_RE.finditer(line):
            p = m.group(1)
            if p.endswith("/"):
                continue  # a directory mention ("…/ 만", "…/ 이동") — not a file target
            if p.startswith("90_System/templates/"):
                continue  # templates are inputs the skill reads, never outputs
            paths.append(p)
    return paths


@pytest.mark.parametrize("skill", SKILLS, ids=lambda s: s.name)
def test_skill_md_level_and_scope_match_levels_table(skill: object) -> None:
    name, min_level, scope = skill.name, skill.min_level, skill.write_scope  # type: ignore[attr-defined]
    fm, body = _split(SKILLS_DIR / name / "SKILL.md")
    assert fm["name"] == name
    levels = LEVEL_RE.findall(body)
    assert levels == [str(min_level)], (name, levels)
    scopes = SCOPE_RE.findall(body)
    assert scopes == [f"{scope}/"], (name, scopes)
    desc = str(fm["description"])
    assert f"Level ≥ {min_level}" in desc or f"Level {min_level}" in desc, (name, desc)
    assert scope in desc, (name, desc)
    assert "_COMMON.md" in body
    assert "Write" in str(fm["allowed-tools"])
    # a skill may only mention the write tool scope it is allowed; every /<name> is in the table
    assert scope in allowed_dirs(min_level)


@pytest.mark.parametrize("skill", SKILLS, ids=lambda s: s.name)
def test_skill_declared_output_paths_pass_the_guard(tmp_path: Path, skill: object) -> None:
    name, min_level, scope = skill.name, skill.min_level, skill.write_scope  # type: ignore[attr-defined]
    _, body = _split(SKILLS_DIR / name / "SKILL.md")
    paths = _declared_write_paths(body)
    assert paths, f"{name}: no declared output path found"
    vault = make_vault(tmp_path / "v", level=min_level)
    low = make_vault(tmp_path / "low", level=min_level - 1) if min_level > 0 else None
    for p in paths:
        concrete = PLACEHOLDER_RE.sub("x", p)
        assert concrete.startswith(scope + "/"), (name, p)
        ev = {"tool_name": "Write", "tool_input": {"file_path": str(vault / concrete)}}
        # /ip-scan writes 40_IP/candidates, which only a LOCAL session may touch (ADR-0011)
        llm = {"MYELIN_LLM": "local"} if name == "ip-scan" else {}
        r = run_hook("guard_write.py", ev, {"MYELIN_VAULT": str(vault), **llm})
        assert r.allowed, f"{name}: Guard blocks declared output {p!r}: {r.stderr}"
        if name == "ip-scan":
            r = run_hook("guard_write.py", ev, {"MYELIN_VAULT": str(vault)})
            assert r.blocked and "외부 LLM" in r.stderr, "ip-scan output must need a LOCAL session"
        if low is not None:
            ev["tool_input"] = {"file_path": str(low / concrete)}
            assert run_hook("guard_write.py", ev, {"MYELIN_VAULT": str(low), **llm}).blocked, (
                name,
                p,
            )


def test_no_skill_instructs_writes_outside_its_scope() -> None:
    human_only = ("10_Domains/", "20_Projects/", "30_Resources/", "90_System/", "99_Archive/")
    for s in SKILLS:
        _, body = _split(SKILLS_DIR / s.name / "SKILL.md")
        for p in _declared_write_paths(body):
            assert p.startswith(s.write_scope + "/"), (s.name, p)
            assert not p.startswith(human_only), (s.name, p)
            if s.name != "ip-scan":
                assert not p.startswith("40_IP/"), (s.name, p)


def test_common_rules_match_frontmatter_schema() -> None:
    common = COMMON.read_text(encoding="utf-8")
    required = {n for n, f in Frontmatter.model_fields.items() if f.is_required()}
    assert required == {"id", "type", "created"}
    schema = json_schema(Frontmatter)
    required_in_schema = schema["required"]
    assert isinstance(required_in_schema, list) and set(required_in_schema) == required
    assert "`id`" in common and "`created`" in common and "<type>" in common
    assert "`origin: claude`" in common and "`status: draft`" in common
    assert Origin("claude") is Origin.CLAUDE and Status("draft") is Status.DRAFT
    assert "[myelin:<skill>]" in common
    assert "`share: false`" in common
    # the allowed-area wording of rule 3 names every human-only root the Guard protects
    for d in ("10_Domains/", "40_IP/", "90_System/", "myelin.yaml", "CLAUDE.md"):
        assert d in common, d
    # Level gating rule: the CLI the skills must call exists in the table contract
    assert "myelin skills --json" in common
    # LEVEL_ALLOW documented in the plugin README matches the code
    readme = (ROOT / "plugin/README.md").read_text(encoding="utf-8")
    for lvl, dirs in LEVEL_ALLOW.items():
        for d in dirs:
            assert f"`{d}`" in readme, (lvl, d)


def test_skill_output_fixtures_validate_against_frontmatter_schema() -> None:
    files = [p for p in OUTPUTS.rglob("*.md") if not p.name.endswith(".patch.md")]
    assert len(files) >= 6
    for f in files:
        note = read_note(f)
        fm = Frontmatter.model_validate(note.raw_frontmatter)
        assert fm.origin is Origin.CLAUDE and fm.status is Status.DRAFT, f
        assert fm.share is False, f
        skill = f.parent.name
        expected_scope = next(s.write_scope for s in SKILLS if s.name == skill)
        if skill == "ip-scan":
            assert fm.classification.value == "confidential"
        assert expected_scope  # fixture folder maps onto a real skill
    patches = list((OUTPUTS / "link").glob("*.patch.md"))
    assert len(patches) == 2
    for p in patches:
        patch = parse_patch(p.read_text(encoding="utf-8"), p)
        assert patch.skill == "link" and patch.status == "proposed"
        assert not patch.target.startswith(("40_IP/", "../")) and patch.target.endswith(".md")


@pytest.mark.parametrize("skill", SKILLS, ids=lambda s: s.name)
def test_skill_md_examples_validate(skill: object) -> None:
    """The worked example inside each SKILL.md must itself satisfy the schema it teaches."""
    name = skill.name  # type: ignore[attr-defined]
    _, body = _split(SKILLS_DIR / name / "SKILL.md")
    blocks = re.findall(r"```markdown\n(.*?)```", body, flags=re.S)
    if name in ("ip-scan", "compose"):
        assert blocks == []  # these skills describe frontmatter in prose only
        return
    assert blocks, name
    for block in blocks:
        if name == "link":
            patch = parse_patch(block)
            assert patch.skill == "link" and patch.status == "proposed"
            continue
        note = parse_note(block)
        fm = Frontmatter.model_validate(note.raw_frontmatter)
        assert fm.origin is Origin.CLAUDE and fm.status is Status.DRAFT and fm.share is False
