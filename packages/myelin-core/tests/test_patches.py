"""P9 port — patch plan: under-heading append, settable keys, fail-closed targets, digest, moves."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from myelin_core.patches import (
    APPLIED_DIR,
    REJECTED_DIR,
    PatchError,
    apply_plan,
    digest,
    list_patches,
    plan_patch,
    read_patch,
    reject_patch,
)

NOTE = (
    "---\nid: 20261001-0900-moc\ntype: moc\ndomain: [D1]\nstatus: verified\norigin: human\n"
    "confidence: high\nclassification: internal\nshare: false\nsource: []\ncreated: 2026-10-01\n"
    "reviewed: 2026-10-01\ntags: [moc]\n---\n# D1\n\n## Sub-MOC\n- a\n\n"
    "## 최근 verified\n- [[Old]]\n\n## 열린 질문\n"
)


def _patch(root: Path, name: str, text: str) -> Path:
    p = root / "_patches" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _hdr(kind: str, extra: str = "") -> str:
    return (
        f"---\npatch: 1\ntarget: 10_Domains/D1/_MOC.md\nkind: {kind}\n{extra}"
        "origin: claude\nskill: link\n"
        "created: 2026-10-18\nrationale: r\n---\n"
    )


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "v"
    (root / "10_Domains/D1").mkdir(parents=True)
    (root / "myelin.yaml").write_text(
        "owner: {name: x}\npacks: [myelin.core]\ndomains: {primary: D1}\n", encoding="utf-8"
    )
    (root / "10_Domains/D1/_MOC.md").write_text(NOTE, encoding="utf-8")
    (root / "10_Domains/D1/Old.md").write_text(
        NOTE.replace("20261001-0900-moc", "20261001-0901-old").replace(
            "type: moc", "type: evergreen"
        ),
        encoding="utf-8",
    )
    return root


def test_append_under_heading(vault: Path) -> None:
    _patch(
        vault,
        "p1.patch.md",
        _hdr("append", 'under: "## 최근 verified"\n') + "## append\n- [[Old]]\n- [[Old]] again\n",
    )
    plan = plan_patch(vault, "p1.patch.md")
    assert plan.ok, plan.issues
    assert "- [[Old]] again\n\n## 열린 질문" in plan.result
    assert plan.diff.startswith("--- a/10_Domains/D1/_MOC.md") and "+- [[Old]] again" in plan.diff
    assert plan.digest == digest(plan.patch_text) and len(plan.digest) == 16
    touched = apply_plan(vault, plan)
    assert (vault / APPLIED_DIR / "p1.patch.md").exists() and not (
        vault / "_patches/p1.patch.md"
    ).exists()
    assert "status: applied" in (vault / APPLIED_DIR / "p1.patch.md").read_text(encoding="utf-8")
    assert touched[0] == "10_Domains/D1/_MOC.md"
    groups = {p["file"]: p["group"] for p in list_patches(vault)}
    assert groups == {"p1.patch.md": "applied"}


def test_append_missing_heading_and_plain_append(vault: Path) -> None:
    _patch(vault, "p.patch.md", _hdr("append", "under: 없는 제목\n") + "## append\n- x\n")
    assert any("not found" in i for i in plan_patch(vault, "p.patch.md").issues)
    _patch(vault, "q.patch.md", _hdr("append") + "## append\n- tail\n")
    plan = plan_patch(vault, "q.patch.md")
    assert plan.ok and plan.result.endswith("## 열린 질문\n- tail\n")


def test_frontmatter_allowlist(vault: Path) -> None:
    _patch(vault, "f.patch.md", _hdr("frontmatter") + "## set\ntags: [moc, extra]\n")
    plan = plan_patch(vault, "f.patch.md")
    assert plan.ok and "tags: [moc, extra]" in plan.result
    _patch(vault, "g.patch.md", _hdr("frontmatter") + "## set\nstatus: draft\n")
    plan = plan_patch(vault, "g.patch.md")
    assert not plan.ok and "Review Gate" in plan.issues[0]


def test_fail_closed_targets(vault: Path, tmp_path: Path) -> None:
    (vault / "40_IP").mkdir()
    (vault / "40_IP/secret.md").write_text(
        NOTE.replace("classification: internal", "classification: confidential"), encoding="utf-8"
    )
    _patch(
        vault,
        "ip.patch.md",
        _hdr("append").replace("10_Domains/D1/_MOC.md", "40_IP/secret.md") + "## append\n- x\n",
    )
    plan = plan_patch(vault, "ip.patch.md")
    assert {
        "40_IP/ 노트는 patch 로 바꿀 수 없다",
        "confidential 노트는 patch 로 바꿀 수 없다",
    } <= set(plan.issues)
    with pytest.raises(PatchError, match="plan has issues"):
        apply_plan(vault, plan)
    _patch(
        vault, "m.patch.md", _hdr("append").replace("_MOC.md", "missing.md") + "## append\n- x\n"
    )
    assert any("target missing" in i for i in plan_patch(vault, "m.patch.md").issues)
    with pytest.raises(PatchError, match="bad patch name"):
        plan_patch(vault, "../x.patch.md")
    with pytest.raises(PatchError, match="not found"):
        plan_patch(vault, "nope.patch.md")
    _patch(
        vault,
        "esc.patch.md",
        _hdr("append").replace("10_Domains/D1/_MOC.md", "../x.md") + "## append\n- x\n",
    )
    with pytest.raises(PatchError, match="Vault-relative"):
        plan_patch(vault, "esc.patch.md")


def test_fail_closed_link_rule(vault: Path) -> None:
    (vault / "00_Inbox/ai-drafts").mkdir(parents=True)
    (vault / "00_Inbox/ai-drafts/AI Draft.md").write_text(
        NOTE.replace("20261001-0900-moc", "20261001-0905-ai")
        .replace("origin: human", "origin: claude")
        .replace("status: verified", "status: draft")
        .replace("type: moc", "type: evergreen"),
        encoding="utf-8",
    )
    _patch(vault, "l.patch.md", _hdr("append") + "## append\n- [[AI Draft]]\n")
    plan = plan_patch(vault, "l.patch.md")
    assert not plan.ok and "미검증 AI 노트" in plan.issues[0]


def test_replace_and_reject(vault: Path) -> None:
    _patch(vault, "r.patch.md", _hdr("replace") + "## before\n- a\n## after\n- b\n")
    plan = plan_patch(vault, "r.patch.md")
    assert plan.ok and "- b\n" in plan.result
    _patch(vault, "r2.patch.md", _hdr("replace") + "## before\nverified\n## after\nx\n")
    assert "exactly once" in plan_patch(vault, "r2.patch.md").issues[0]
    touched = reject_patch(vault, "r.patch.md")
    assert touched == ["_patches/r.patch.md", f"{REJECTED_DIR}/r.patch.md"]
    assert "status: rejected" in (vault / REJECTED_DIR / "r.patch.md").read_text(encoding="utf-8")
    assert [p["group"] for p in list_patches(vault) if p["file"] == "r.patch.md"] == ["rejected"]
    with pytest.raises(PatchError, match="not found"):
        reject_patch(vault, "r.patch.md")


def test_under_only_for_append_and_invalid_listed(vault: Path) -> None:
    with pytest.raises(PatchError, match="only valid for kind: append"):
        read_patch(
            _patch(
                vault, "u.patch.md", _hdr("replace", "under: x\n") + "## before\na\n## after\nb\n"
            )
        )
    rows = list_patches(vault)
    assert rows and rows[0]["status"] == "invalid" and "error" in rows[0]
    shutil.rmtree(vault / "_patches")
    assert list_patches(vault) == []
