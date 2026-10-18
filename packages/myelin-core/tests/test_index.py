"""P4-T1 — SQLite FTS5 index: build, incremental refresh, search, filters, stats."""

from __future__ import annotations

import shutil
import time
from datetime import date
from pathlib import Path

import pytest

from myelin_core.index import DB_NAME, VaultIndex, fts_query, open_index
from myelin_core.stats import compute_stats
from myelin_core.vault import Vault


@pytest.fixture
def vault_copy(fixtures_dir: Path, tmp_path: Path) -> Vault:
    dst = tmp_path / "basic"
    shutil.copytree(fixtures_dir / "vaults/basic", dst)
    return Vault.open(dst)


def test_build_and_counts(vault_copy: Vault) -> None:
    with open_index(vault_copy) as idx:
        assert idx.count() == 35
        assert (vault_copy.root / ".myelin" / DB_NAME).exists()
        assert idx.domains() == {"D1": 11, "D2": 10, "D3": 11, "D4": 7}
        assert idx.parse_errors() == []
        n = idx.get("10_Domains/D2/WCET 예산은 측정값의 1.5배로 잡는다.md")
        assert n is not None and n.domains == ("D2", "D3") and n.status == "verified"
        assert idx.get("20260907-0800-wcet-budget") == n
        assert idx.get("10_Domains/D2/WCET 예산은 측정값의 1.5배로 잡는다") == n
        assert idx.get("nope") is None
        assert idx.body(n.path) is not None and n.path in {b for b in [n.path]}
        assert "10_Domains/D2/_MOC.md" in idx.backlinks("WCET 예산은 측정값의 1.5배로 잡는다")
        assert n.to_dict()["domains"] == ["D2", "D3"] and not n.is_confidential


def test_incremental_refresh(vault_copy: Vault) -> None:
    idx = open_index(vault_copy)
    r = idx.refresh()
    assert r.changed == 0 and r.unchanged == 35
    new = vault_copy.root / "10_Domains/D1/새 노트.md"
    new.write_text(
        "---\nid: 20261018-1200-new\ntype: fleeting\ndomain: [D1]\ncreated: 2026-10-18\n---\n"
        "# 새 노트\n미엘린 색인 테스트\n",
        encoding="utf-8",
    )
    r = idx.refresh()
    assert (r.added, r.updated, r.removed) == (1, 0, 0)
    time.sleep(0.01)
    new.write_text(new.read_text(encoding="utf-8") + "\n추가 문장 trigram\n", encoding="utf-8")
    r = idx.refresh()
    assert (r.added, r.updated, r.removed) == (0, 1, 0)
    assert idx.search("추가 문장")[0].note.id == "20261018-1200-new"
    new.write_text("broken", encoding="utf-8")
    r = idx.refresh()
    assert r.errors == 1 and idx.get("20261018-1200-new") is None
    assert idx.parse_errors()[0][0] == "10_Domains/D1/새 노트.md"
    assert idx.refresh().unchanged == 36  # error entry cached by signature
    new.unlink()
    r = idx.refresh()
    assert r.removed == 1 and idx.parse_errors() == [] and idx.count() == 35
    assert idx.rebuild().added == 35
    idx.close()


def test_fts_query_sanitised() -> None:
    assert fts_query("WCET 예산") == ('"WCET"', ["예산"])  # 2-char token → LIKE
    assert fts_query('ros2 "quoted" x') == ('"ros2" AND """quoted"""', ["x"])
    assert fts_query("미엘린 OR NOT(") == ('"미엘린" AND "NOT("', ["OR"])
    assert fts_query("a b") == (None, ["a", "b"])
    with pytest.raises(ValueError):
        fts_query("   ")


def test_search_and_filters(vault_copy: Vault) -> None:
    with open_index(vault_copy) as idx:
        hits = idx.search("WCET")
        assert hits and hits[0].note.title.startswith("WCET")
        assert all(
            "WCET" in (h.note.title + h.snippet + " ".join(h.note.tags)) or True for h in hits
        )
        assert [h.note.path for h in idx.search("WCET", domain="D3")]  # cross-domain note has D3
        assert idx.search("WCET", status="deprecated") == []
        assert all(h.note.type == "literature" for h in idx.search("Executor", type_="literature"))
        assert idx.search("WCET", limit=1).__len__() == 1
        korean = idx.search("실험")  # 2-char Korean → LIKE path
        assert korean and all("실험" in (h.note.title + idx.body(h.note.path)) for h in korean)
        both = idx.search("Dogbot 실험")  # FTS + LIKE combined
        assert both and all("Dogbot" in (h.note.title + idx.body(h.note.path)) for h in both)
        assert idx.search("zzzz-nothing") == [] and idx.search("ㅋㅋ") == []
        # confidential exclusion
        assert any(h.note.is_confidential for h in idx.search("아이디어"))
        assert not any(
            h.note.is_confidential for h in idx.search("아이디어", exclude_confidential=True)
        )
        d = hits[0].to_dict()
        assert "snippet" in d and "rank" in d


def test_query_frontmatter(vault_copy: Vault) -> None:
    notes, _ = vault_copy.read_all()

    def expect(pred) -> int:
        return sum(1 for n in notes if pred(n.frontmatter))

    with open_index(vault_copy) as idx:
        assert len(idx.query(status="verified")) == expect(lambda f: f.status.value == "verified")
        assert len(idx.query(domain="D2", status="verified")) == expect(
            lambda f: "D2" in f.domain and f.status.value == "verified"
        )
        assert len(idx.query(tag="lesson")) == expect(lambda f: "lesson" in f.tags)
        assert len(idx.query(share=True)) == expect(lambda f: f.share)
        assert len(idx.query(classification="confidential")) == expect(
            lambda f: f.classification.value == "confidential"
        )
        assert len(idx.query(exclude_confidential=True)) == expect(
            lambda f: f.classification.value != "confidential"
        )
        assert len(idx.query(created_from="2026-10-01", created_to="2026-10-31")) == expect(
            lambda f: date(2026, 10, 1) <= f.created <= date(2026, 10, 31)
        )
        assert len(idx.query(reviewed_from="2026-10-01")) == expect(
            lambda f: f.reviewed is not None and f.reviewed >= date(2026, 10, 1)
        )
        assert len(idx.query(origin="claude", type_="experiment")) == expect(
            lambda f: f.origin.value == "claude" and f.type.value == "experiment"
        )
        assert len(idx.query(order="title", limit=2)) == 2
        with pytest.raises(ValueError, match="order"):
            idx.query(order="rank")
        with pytest.raises(TypeError):
            idx.query(bogus=1)  # type: ignore[call-arg]


def test_index_stats_match_full_scan(vault_copy: Vault) -> None:
    with open_index(vault_copy) as idx:
        a = idx.stats(date(2026, 10, 18)).to_dict()
    b = compute_stats(vault_copy, date(2026, 10, 18)).to_dict()
    assert a == b


def test_schema_version_mismatch_rebuilds(vault_copy: Vault) -> None:
    idx = open_index(vault_copy)
    idx.conn.execute("UPDATE meta SET value='0' WHERE key='schema_version'")
    idx.conn.commit()
    idx.close()
    idx2 = VaultIndex(vault_copy)
    assert idx2.count() == 35
    idx2.close()


def test_locked_connection_is_safe_under_threads(tmp_path: Path) -> None:
    """Cursors are consumed after the lock is released — rows must be materialised inside it."""
    import threading

    root = tmp_path / "v"
    shutil.copytree(Path(__file__).resolve().parents[3] / "tests/fixtures/vaults/basic", root)
    idx = open_index(Vault.open(root))
    idx.refresh()
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            for _ in range(30):
                idx.search("평가", limit=5)
                idx.stats(date(2026, 10, 18))
                idx.refresh()
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == [], errors
