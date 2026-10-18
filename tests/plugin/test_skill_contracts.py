"""Skill 출력 계약 e2e — 각 SKILL.md 의 출력 블록을 실제로 채워 Vault에 넣는다.

검사 (P3-T7, T9):
  1. 최소 Level에서 Guard가 그 경로 쓰기를 허용한다.
  2. 한 단계 낮은 Level에서는 차단한다 (Level 게이트가 Skill 설명과 일치).
  3. 결과물을 넣은 Vault의 `myelin doctor` 오류가 0이다.
실제 Claude 실행은 docs/manual/P3-e2e.md 의 수동 체크리스트로 확인한다.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from myelin_core.doctor import run_doctor
from myelin_core.errors import MyelinError
from myelin_core.frontmatter import Origin, Status
from myelin_core.note import parse_note, split_frontmatter
from myelin_core.scaffold import GUARD_FILE
from myelin_core.yamlio import load_yaml

from .conftest import ROOT, event, make_vault, run_guard

SKILLS_DIR = ROOT / "plugin" / "skills"
SKILLS = sorted(p.name for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file())
OUTPUT_RE = re.compile(
    r'<!-- myelin:output path="(?P<path>[^"]+)" -->\n```markdown\n(?P<body>.*?)\n```\n'
    r"<!-- /myelin:output -->",
    re.DOTALL,
)
LEVEL_RE = re.compile(r"<!-- myelin:min-level (\d) -->")
VALUES = {
    "id": "20261018-0930-contract-test",
    "date": "2026-10-18",
    "domain": "AI-ML-AX",
    "title": "계약 테스트",
    "slug": "20261018-contract",
    "source": "https://example.com/paper",
    "note": "10_Domains/AI-ML-AX/_MOC",
    "week": "2026-W42",
}


def fill(text: str) -> str:
    out = re.sub(r"\{\{(\w+)\}\}", lambda m: VALUES[m.group(1)], text)
    assert "{{" not in out
    return out


def contract(name: str) -> tuple[int, str, str]:
    text = (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
    level = LEVEL_RE.search(text)
    output = OUTPUT_RE.search(text)
    assert level and output, f"{name}: min-level 또는 출력 계약 블록이 없습니다"
    return int(level.group(1)), fill(output.group("path")), fill(output.group("body")) + "\n"


def test_all_seven_skills_present() -> None:
    assert SKILLS == ["compose", "distill", "ingest", "interview", "ip-scan", "link", "review"]


@pytest.mark.parametrize("name", SKILLS)
def test_frontmatter_is_human_invoked(name: str) -> None:
    text = (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
    fm_text, _ = split_frontmatter(text, name)
    fm = load_yaml(fm_text, name, MyelinError)
    assert fm["name"] == name and len(fm["description"]) < 1536
    assert fm["disable-model-invocation"] is True
    assert len(text.splitlines()) <= 500


@pytest.mark.parametrize("name", SKILLS)
def test_output_contract(tmp_path: Path, name: str) -> None:
    level, rel, body = contract(name)

    # 1·2. Level 게이트
    vault = make_vault(tmp_path / "v", level=level)
    code, err = run_guard(vault / GUARD_FILE, event("Write", rel, vault))
    assert code == 0, f"{name}: Level {level} 에서 {rel} 쓰기가 막힘 — {err}"
    if level > 0:
        low = make_vault(tmp_path / "low", level=level - 1)
        assert run_guard(low / GUARD_FILE, event("Write", rel, low))[0] == 2

    # 3. doctor
    target = vault / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    errors = [
        f
        for f in run_doctor(vault, today=date(2026, 10, 18), check_location=False)
        if f.severity == "error"
    ]
    assert errors == [], errors

    # 노트형 출력은 AI 기여가 표시된 초안이어야 한다
    if body.startswith("---"):
        note = parse_note(body, source=rel)
        assert note.frontmatter.origin in (Origin.CLAUDE, Origin.MIXED)
        assert note.frontmatter.status is Status.DRAFT
        assert not note.frontmatter.policy_issues()


def test_level_zero_blocks_every_skill_output(tmp_path: Path) -> None:
    vault = make_vault(tmp_path / "v", level=0)
    for name in SKILLS:
        _, rel, _ = contract(name)
        assert run_guard(vault / GUARD_FILE, event("Write", rel, vault))[0] == 2, name
