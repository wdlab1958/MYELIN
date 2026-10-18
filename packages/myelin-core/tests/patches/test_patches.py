"""구조화 patch — 파싱, 적용 계획, 안전 검사, 적용·반려·되돌리기."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from myelin_core.patches import (
    PatchError,
    apply_plan,
    apply_reject,
    list_patches,
    parse_patch,
    plan_patch,
    plan_reject,
    revert_plan,
    revert_reject,
)

TODAY = date(2026, 10, 18)
MOC = "10_Domains/AI-ML-AX/_MOC.md"
Put = Callable[[str, str], str]


def patch(
    kind: str = "append",
    body: str = "## append\n- [[WCET]]\n",
    target: str = MOC,
    under: str | None = "## 핵심 Evergreen",
    status: str = "proposed",
) -> str:
    u = f'under: "{under}"\n' if under else ""
    return (
        "---\n"
        "patch: 1\n"
        f"target: {target}\n"
        f"kind: {kind}\n"
        f"{u}"
        "origin: claude\n"
        "skill: link\n"
        "created: 2026-10-18\n"
        "rationale: 세 노트가 같은 개념을 인용\n"
        f"status: {status}\n"
        "---\n"
        f"{body}"
    )


def note(note_id: str, status: str = "verified", origin: str = "human", body: str = "") -> str:
    return (
        f"---\nid: {note_id}\ntype: evergreen\ndomain: [AI-ML-AX]\nstatus: {status}\n"
        f"origin: {origin}\ncreated: 2026-10-17\ntags: [a]\n---\n# 제목\n\n본문\n{body}"
    )


P = "_patches/20261018-0900-moc.patch.md"


def test_parse_errors() -> None:
    assert parse_patch(patch(), P).meta.kind == "append"
    bad = [
        patch(body="## before\nx\n"),
        patch(kind="replace", under=None, body="## before\nx\n"),
        patch(kind="replace", body="## before\nx\n## after\ny\n"),  # under + replace
        patch(target="../x.md"),
        patch(target="_patches/x.md"),
        patch().replace("skill: link", "skill: Link!"),
        patch().replace("patch: 1", "patch: 2"),
        patch().replace("origin: claude", "origin: claude\nextra: 1"),
        patch(body="## append\n- a\n## append\n- b\n"),
        "no frontmatter\n",
    ]
    for text in bad:
        with pytest.raises(PatchError):
            parse_patch(text, P)


def test_append_under_heading_and_apply(vault: Path, put: Put) -> None:
    put("10_Domains/AI-ML-AX/WCET.md", note("20261017-0900-wcet"))
    put(P, patch())
    plan = plan_patch(vault, P, TODAY)
    lines = plan.target_new.splitlines()
    i = lines.index("## 핵심 Evergreen")
    assert lines[i + 1] == "- [[WCET]]" and lines[i + 3].startswith("## ")  # 구획 끝
    assert "+- [[WCET]]" in plan.diff and plan.warnings == []
    assert set(plan.paths) == {MOC, P, "_patches/applied/20261018-0900-moc.patch.md"}
    before = (vault / MOC).read_text(encoding="utf-8")
    apply_plan(vault, plan)
    assert "- [[WCET]]" in (vault / MOC).read_text(encoding="utf-8")
    assert not (vault / P).exists()
    archived = (vault / plan.archived_rel).read_text(encoding="utf-8")
    assert "status: applied" in archived and "decided: 2026-10-18" in archived
    revert_plan(vault, plan)
    assert (vault / MOC).read_text(encoding="utf-8") == before and (vault / P).exists()
    assert not (vault / plan.archived_rel).exists()


def test_append_to_end_and_crlf(vault: Path, put: Put) -> None:
    rel = "20_Projects/c.md"
    raw = note("20261017-0901-crlf").replace("\n", "\r\n")
    (vault / rel).write_bytes(raw.encode())
    put(P, patch(target=rel, under=None, body="## append\n- 관련: [[_MOC]]\n"))
    plan = plan_patch(vault, P, TODAY)
    assert plan.target_new.startswith(raw) and plan.target_new.endswith("- 관련: [[_MOC]]\r\n")
    assert "\n" not in plan.target_new.replace("\r\n", "")


def test_under_missing(vault: Path, put: Put) -> None:
    put(P, patch(under="## 없는 제목"))
    with pytest.raises(PatchError) as exc:
        plan_patch(vault, P, TODAY)
    assert exc.value.issues[0].code == "under_not_found"


def test_replace(vault: Path, put: Put) -> None:
    rel = put("20_Projects/r.md", note("20261017-0902-r", body="옛 문장\n"))
    put(P, patch("replace", "## before\n옛 문장\n## after\n새 문장\n", rel, None))
    assert "새 문장" in plan_patch(vault, P, TODAY).target_new
    put(P, patch("replace", "## before\n없는 문장\n## after\nx\n", rel, None))
    with pytest.raises(PatchError) as exc:
        plan_patch(vault, P, TODAY)
    assert exc.value.issues[0].code == "before_mismatch"


def test_frontmatter_allow_and_protect(vault: Path, put: Put) -> None:
    rel = put("20_Projects/f.md", note("20261017-0903-f"))
    put(P, patch("frontmatter", "## set\ntags: [a, b]\n", rel, None))
    assert "tags:\n  - a\n  - b" in plan_patch(vault, P, TODAY).target_new or "b]" in (
        plan_patch(vault, P, TODAY).target_new
    )
    for key in ("status: verified", "origin: human", "classification: public", "id: x"):
        put(P, patch("frontmatter", f"## set\n{key}\n", rel, None))
        with pytest.raises(PatchError) as exc:
            plan_patch(vault, P, TODAY)
        assert exc.value.issues[0].code == "protected_key", key


@pytest.mark.parametrize(
    ("target", "setup"),
    [
        ("myelin.yaml", None),
        ("90_System/taxonomy.md", None),
        ("20_Projects/missing.md", None),
        ("40_IP/idea.md", "40_IP/idea.md"),
        ("20_Projects/conf.md", "20_Projects/conf.md"),
    ],
)
def test_target_refused(vault: Path, put: Put, target: str, setup: str | None) -> None:
    if setup:
        text = note("20261017-0904-x")
        if "conf" in setup:
            text = text.replace("tags: [a]", "classification: confidential\ntags: [a]")
        put(setup, text)
    put(P, patch(target=target, under=None))
    with pytest.raises(PatchError):
        plan_patch(vault, P, TODAY)


def test_symlinks_refused(vault: Path, put: Put, tmp_path: Path) -> None:
    outside = tmp_path / "out.md"
    outside.write_text(note("20261017-0905-o"), encoding="utf-8")
    os.symlink(outside, vault / "20_Projects/link.md")
    put(P, patch(target="20_Projects/link.md", under=None))
    with pytest.raises(PatchError):
        plan_patch(vault, P, TODAY)
    (vault / "_patches/evil.md").symlink_to(outside)
    with pytest.raises(PatchError):
        plan_patch(vault, "_patches/evil.md", TODAY)
    for bad in ("_patches/../myelin.yaml", "myelin.yaml", "_patches/a/b.md", "_patches/x.txt"):
        with pytest.raises(PatchError):
            plan_patch(vault, bad, TODAY)


def test_link_to_unverified_ai_refused(vault: Path, put: Put) -> None:
    put("00_Inbox/ai-drafts/초안.md", note("20261017-0906-d", status="draft", origin="claude"))
    put(P, patch(body="## append\n- [[초안]]\n"))
    with pytest.raises(PatchError) as exc:
        plan_patch(vault, P, TODAY)
    assert exc.value.issues[0].code == "links_unverified_ai"
    put(P, patch(body="## append\n- [[없는 노트]]\n"))
    assert plan_patch(vault, P, TODAY).warnings == ["링크 대상 없음: [[없는 노트]]"]


def test_stale_done_and_existing_archive(vault: Path, put: Put) -> None:
    put(P, patch())
    plan = plan_patch(vault, P, TODAY)
    (vault / MOC).write_text((vault / MOC).read_text(encoding="utf-8") + "x\n", encoding="utf-8")
    with pytest.raises(PatchError):
        apply_plan(vault, plan)
    put(P, patch(status="applied"))
    with pytest.raises(PatchError):
        plan_patch(vault, P, TODAY)
    put(P, patch())
    put("_patches/applied/20261018-0900-moc.patch.md", "x")
    with pytest.raises(PatchError):
        plan_patch(vault, P, TODAY)


def test_reject_and_list(vault: Path, put: Put) -> None:
    put(P, patch())
    put("_patches/20261018-link-legacy.md", "# Patch: 링크 제안\n\n- [ ] 수동 적용\n")
    rows = list_patches(vault)
    assert [r["structured"] for r in rows] == [True, False]
    assert rows[0]["target"] == MOC and "frontmatter" in rows[1]["reason"]
    for rel in (P, "_patches/20261018-link-legacy.md"):
        plan = plan_reject(vault, rel, TODAY)
        apply_reject(vault, plan)
        assert not (vault / rel).exists() and (vault / plan.archived_rel).exists()
    assert "status: rejected" in (vault / "_patches/rejected/20261018-0900-moc.patch.md").read_text(
        encoding="utf-8"
    )
    revert_reject(vault, plan)
    assert (vault / "_patches/20261018-link-legacy.md").exists()
    assert list_patches(vault)[0]["structured"] is False
    put("_patches/rejected/20261018-link-legacy.md", "dup")
    with pytest.raises(PatchError):
        plan_reject(vault, "_patches/20261018-link-legacy.md", TODAY)
