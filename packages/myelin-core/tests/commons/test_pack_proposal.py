"""Personal Pack → Org Pack 제안, 익명 지표 집계 (P9)."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from myelin_cli.main import app
from myelin_core.commons import CommonsError, pack_proposal, proposals, propose_pack, push
from myelin_core.gitops import Author

TODAY = date(2026, 10, 18)
ME = Author("Tester", "tester@localhost")
Link = Callable[..., None]


def _pack(root: Path, kind: str = "personal", extra: str = "") -> Path:
    d = root / "me.side"
    (d / "templates").mkdir(parents=True)
    (d / "pack.yaml").write_text(
        f"pack: me.side\nversion: 0.3.0\nkind: {kind}\nmaintainer: me\n"
        "domains:\n  - id: SIDE\n    name: 사이드 연구\n"
        "    sub_mocs: [실험]\n    templates: templates\n",
        encoding="utf-8",
    )
    (d / "templates/lesson.md").write_text(
        f'---\nid: <% tp.date.now("YYYYMMDD-HHmm-ssSSS") %>\n---\n# <% tp.file.title %>\n{extra}',
        encoding="utf-8",
    )
    return d


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout


def test_propose_pack_flow(vault: Path, commons: Path, link: Link, tmp_path: Path) -> None:
    link(vault, commons)
    pack = _pack(tmp_path / "packs")
    check = pack_proposal(vault, pack)
    assert check["ok"] and check["branch"] == "propose/me.side"
    assert check["files"] == [
        "proposals/packs/me.side/pack.yaml",
        "proposals/packs/me.side/templates/lesson.md",
    ]
    with pytest.raises(CommonsError):
        propose_pack(vault, pack, confirmed=False, author=ME, today=TODAY)
    head_before = _git(commons, "rev-parse", "HEAD")
    out = propose_pack(vault, pack, confirmed=True, author=ME, today=TODAY)
    assert _git(commons, "rev-parse", "HEAD") == head_before  # 작업 브랜치 그대로
    assert _git(commons, "status", "--porcelain") == ""
    files = _git(commons, "show", "--name-only", "--format=", out["branch"]).split()
    assert "proposals/packs/me.side/PROPOSAL.md" in files and len(files) == 3
    assert "Tester" in _git(commons, "show", f"{out['branch']}:proposals/packs/me.side/PROPOSAL.md")
    assert {"branch": "propose/me.side", "subject": "commons: propose pack me.side 0.3.0",
            "pushed": "no"} in proposals(commons)  # fmt: skip
    push(vault, out["branch"])
    assert "propose/me.side" in _git(commons.parent / "remote.git", "branch", "--list")
    again = pack_proposal(vault, pack)
    assert not again["ok"] and again["blocks"][0]["code"] == "already_proposed"


@pytest.mark.parametrize(
    ("kind", "extra", "code"),
    [
        ("org", "", "not_personal"),
        ("personal", "연락: kim@corp.example\n", "deid_email"),
        ("personal", "<%* app.vault.delete() %>\n", "unsafe_template"),
    ],
)
def test_propose_pack_refusals(
    vault: Path, commons: Path, link: Link, tmp_path: Path, kind: str, extra: str, code: str
) -> None:
    link(vault, commons)
    pack = _pack(tmp_path / "packs", kind=kind, extra=extra)
    check = pack_proposal(vault, pack)
    codes = {i["code"] for i in (*check["blocks"], *check["deid"])}
    assert not check["ok"] and code in codes
    with pytest.raises(CommonsError):
        propose_pack(vault, pack, confirmed=True, author=ME, today=TODAY)


def test_propose_pack_symlink_and_disabled(
    vault: Path, commons: Path, link: Link, tmp_path: Path
) -> None:
    pack = _pack(tmp_path / "packs")
    assert not pack_proposal(vault, pack)["ok"]  # Commons 꺼짐
    link(vault, commons)
    (pack / "templates/evil.md").symlink_to(tmp_path)
    check = pack_proposal(vault, pack)
    assert not check["ok"]


# ── 집계 ─────────────────────────────────────────────────────────────────
def _sub(week: str = "2026-W43", **kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema": 1, "week": week, "level": 1, "packs": ["myelin.core", "org.security-consulting"],
        "domains": 3, "notes": "25-49", "verified_notes": "10-24", "verified_last_7d": "1-4",
        "ai_drafts_pending": "1-4", "ai_promotion_rate": 0.5, "orphan_ratio": 0.1,
        "cross_domain_ratio": 0.2, "inbox_items": "5-9", "commons_enabled": False,
        "mcp_write_drafts": False,
    }  # fmt: skip
    base.update(kw)
    return base


def test_aggregate(tmp_path: Path) -> None:
    from myelin_core.metrics import aggregate

    subs = [
        _sub(),
        _sub(verified_last_7d="0", ai_promotion_rate=None, cross_domain_ratio=0.4),
        _sub(ai_promotion_rate=0.7, commons_enabled=True),
        _sub(week="2026-W44"),
        {**_sub(), "owner": "brian"},  # 익명 형식 위반
        _sub(packs=["brian.physical-ai"]),  # 개인을 가리키는 Pack
        _sub(notes=37),  # 구간이 아닌 정확한 수
    ]
    files = []
    for i, s in enumerate(subs):
        f = tmp_path / f"m{i}.json"
        f.write_text(json.dumps(s), encoding="utf-8")
        files.append(f)
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    files.append(tmp_path / "broken.json")
    out = aggregate(files)
    w = out["weeks"]["2026-W43"]
    assert w["submissions"] == 3 and w["active"] == 2 and w["active_ratio"] == 0.67
    assert w["ai_promotion_rate_median"] == 0.6 and w["commons_enabled"] == 1
    assert w["packs"] == {"myelin.core": 3, "org.security-consulting": 3}
    assert out["weeks"]["2026-W44"]["submissions"] == 1
    assert sorted(r["file"] for r in out["rejected"]) == [
        "broken.json",
        "m4.json",
        "m5.json",
        "m6.json",
    ]

    runner = CliRunner()
    res = runner.invoke(app, ["metrics-aggregate", str(tmp_path)])
    assert res.exit_code == 1 and "2026-W43" in res.output and "거부 m4.json" in res.output
    for f in (
        tmp_path / "m4.json",
        tmp_path / "m5.json",
        tmp_path / "m6.json",
        tmp_path / "broken.json",
    ):
        f.unlink()
    ok = runner.invoke(app, ["metrics-aggregate", str(tmp_path), "--json"])
    assert ok.exit_code == 0 and json.loads(ok.output)["rejected"] == []


def test_cli_propose_pack(vault: Path, commons: Path, link: Link, tmp_path: Path) -> None:
    link(vault, commons)
    pack = _pack(tmp_path / "packs")
    runner = CliRunner()
    no = runner.invoke(app, ["commons", "propose-pack", str(vault), str(pack)])
    assert no.exit_code == 1  # 비대화형 + --yes 없음
    res = runner.invoke(app, ["commons", "propose-pack", str(vault), str(pack), "--yes"])
    assert res.exit_code == 0 and "propose/me.side" in res.output
    bad = runner.invoke(app, ["commons", "propose-pack", str(vault), str(pack), "--yes"])
    assert bad.exit_code == 1
