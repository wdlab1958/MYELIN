"""색인과 읽기 정책 — Guard 스크립트와 판정이 같은지 포함."""

from __future__ import annotations

import os
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from myelin_core.config import parse_config
from myelin_core.frontmatter import Classification
from myelin_core.index import VaultIndex
from myelin_core.loader import discover_packs, resolve
from myelin_core.policy import ReadPolicy
from myelin_core.resources import myelin_guard
from myelin_core.scaffold import apply_plan, plan_init

ROOT = Path(__file__).resolve().parents[3]


def vault(tmp_path: Path) -> Path:
    packs = resolve(["brian.physical-ai"], discover_packs(ROOT / "packs"))
    cfg = parse_config(
        {"owner": {"name": "t"}, "packs": ["myelin.core", "brian.physical-ai"],
         "domains": {"primary": "AI-ML-AX"}}
    )  # fmt: skip
    v = tmp_path / "v"
    apply_plan(v, plan_init(cfg, packs, date(2026, 10, 18)))
    return v


def write(
    v: Path, rel: str, body: str, cls: str = "internal", nid: str = "20261018-0900-a"
) -> Path:
    p = v / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"---\nid: {nid}\ntype: evergreen\ndomain: [AI-ML-AX]\nstatus: verified\norigin: human\n"
        f"classification: {cls}\ncreated: 2026-10-18\ntags: [rtos]\n---\n{body}\n",
        encoding="utf-8",
    )
    return p


def test_policy_matches_guard(tmp_path: Path) -> None:
    v = vault(tmp_path)
    policy = ReadPolicy()
    cases = {
        "40_IP/a.md": Classification.INTERNAL,
        "40_IP/candidates/a.md": Classification.INTERNAL,
        "30_Resources/a.md": Classification.CONFIDENTIAL,
        "30_Resources/b.md": Classification.INTERNAL,
    }
    for rel, cls in cases.items():
        write(v, rel, "x", cls.value)
        ev = {"tool_name": "Read", "tool_input": {"file_path": rel}, "cwd": str(v)}
        guard_blocks = myelin_guard.check(ev, v) is not None
        assert policy.blocked(rel, cls) == guard_blocks, rel
    cfg = parse_config(
        {"owner": {"name": "t"}, "packs": ["myelin.core"], "domains": {"primary": "A"},
         "llm": {"route": {"confidential": "claude", "40_IP/**": "claude"}}}
    )  # fmt: skip
    open_policy = ReadPolicy.from_config(cfg)
    assert not open_policy.blocked("40_IP/a.md", Classification.CONFIDENTIAL)


def test_incremental_refresh_and_search(tmp_path: Path) -> None:
    v = vault(tmp_path)
    a = write(
        v, "10_Domains/AI-ML-AX/스케줄러.md", "실시간 스케줄러 WCET 분석", nid="20261018-0900-a"
    )
    idx = VaultIndex(v, ReadPolicy())
    first = idx.refresh(force=True)
    assert first.added >= 1 and first.removed == 0
    assert idx.refresh().skipped_refresh  # 2초 이내 재호출 생략
    assert idx.refresh(force=True).added == 0  # 바뀐 것 없음

    write(v, "10_Domains/AI-ML-AX/스케줄러.md", "바뀐 본문 우선순위 역전", nid="20261018-0900-a")
    os.utime(a, ns=(a.stat().st_atime_ns, a.stat().st_mtime_ns + 10**9))
    assert idx.refresh(force=True).updated == 1
    assert idx.search("우선순위")[0]["title"] == "스케줄러"
    assert idx.search("WCET") == []  # 옛 내용은 사라짐

    a.unlink()
    assert idx.refresh(force=True).removed == 1
    assert idx.search("우선순위") == []


def test_invalid_and_protected_not_searchable(tmp_path: Path) -> None:
    v = vault(tmp_path)
    (v / "30_Resources/깨진.md").write_text("---\ntype: x\n---\n깨진 노트 비밀\n", encoding="utf-8")
    write(v, "30_Resources/기밀.md", "기밀 비밀 내용", cls="confidential", nid="20261018-0900-b")
    idx = VaultIndex(v, ReadPolicy())
    stats = idx.refresh(force=True)
    assert stats.invalid == 1 and stats.protected == 1
    assert idx.search("비밀") == []
    with sqlite3.connect(v / ".myelin/index.db") as con:
        bodies = [r[0] for r in con.execute("SELECT body FROM notes WHERE indexed = 0")]
    assert bodies == [None, None]  # 보호·깨진 노트는 내용 자체를 저장하지 않는다


def test_policy_change_rebuilds(tmp_path: Path) -> None:
    v = vault(tmp_path)
    write(v, "30_Resources/기밀.md", "기밀 비밀 내용", cls="confidential")
    closed = VaultIndex(v, ReadPolicy())
    closed.refresh(force=True)
    assert closed.search("비밀") == []
    opened = VaultIndex(v, ReadPolicy(confidential_local=False))
    opened.refresh(force=True)
    assert opened.search("비밀")[0]["path"] == "30_Resources/기밀.md"
    closed.refresh(force=True)  # 다시 닫으면 다시 사라진다
    assert closed.search("비밀") == []


def test_query_get_counts(tmp_path: Path) -> None:
    v = vault(tmp_path)
    write(v, "10_Domains/AI-ML-AX/a.md", "aaa", nid="20261018-0900-dup")
    write(v, "10_Domains/AI-ML-AX/b.md", "bbb", nid="20261018-0900-dup")
    idx = VaultIndex(v, ReadPolicy())
    idx.refresh(force=True)
    assert len(idx.query(domain="AI-ML-AX", tag="#rtos", created_after="2026-01-01",
                         created_before="2026-12-31", origin="human")) == 2  # fmt: skip
    assert "warning" in (idx.get(note_id="20261018-0900-dup") or {})
    assert idx.get(path="nope.md") is None
    with pytest.raises(ValueError):
        idx.get()
    with pytest.raises(ValueError):
        idx.search(" ")
    assert idx.domain_counts()["AI-ML-AX"] >= 2
    assert idx.counts()["indexed"] >= 2
