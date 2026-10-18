"""P4-T3~T7 — VaultService: search/get/query/list/stats, boundary, confidential, write_draft."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from myelin_core.vault import AI_DRAFTS
from myelin_mcp.service import REDACTED, MCPError, VaultService

from .conftest import set_mcp


def test_search_hides_confidential_by_default(service: VaultService) -> None:
    assert service.search_notes("아이디어") == []  # only confidential idea-ip notes match → hidden
    hits = service.search_notes("설계")
    assert hits and all(h["classification"] != "confidential" for h in hits)
    assert all(not h["path"].startswith("40_IP/") for h in hits)
    assert service.search_notes("WCET", domain="D2", status="verified")
    assert service.search_notes("WCET", type="literature") == []
    with pytest.raises(MCPError, match="token"):
        service.search_notes("   ")


def test_get_note_redacts_confidential(service: VaultService) -> None:
    n = service.get_note("40_IP/candidates/Agentic CAD 검증 루프.md")
    assert n["redacted"] is True and n["body"] == REDACTED
    assert n["classification"] == "confidential" and n["title"] == "Agentic CAD 검증 루프"
    ok = service.get_note("20260907-0800-wcet-budget")
    assert ok["redacted"] is False and "WCET" in ok["body"]
    assert "10_Domains/D2/_MOC.md" in ok["backlinks"]
    assert (
        service.get_note("10_Domains/D2/WCET 예산은 측정값의 1.5배로 잡는다")["id"]
        == "20260907-0800-wcet-budget"
    )


def test_expose_confidential_opt_in(vault_root: Path, local_session: None) -> None:
    set_mcp(vault_root, expose=True)  # honoured only because the process is LOCAL (ADR-0011)
    svc = VaultService.open(vault_root)
    n = svc.get_note("40_IP/candidates/Agentic CAD 검증 루프.md")
    assert n["redacted"] is False and "Agentic" in n["body"]
    assert any(h["classification"] == "confidential" for h in svc.search_notes("아이디어"))
    assert any(
        r["classification"] == "confidential" for r in svc.query_frontmatter(type_="idea-ip")
    )


@pytest.mark.parametrize(
    "ref",
    [
        "../outside.md",
        "/etc/passwd",
        "~/x.md",
        "10_Domains/../../x.md",
        "",
        "10_Domains/D1/\x00.md",
    ],
)
def test_get_note_path_escape_rejected(service: VaultService, tmp_path: Path, ref: str) -> None:
    with pytest.raises(MCPError):
        service.get_note(ref)


def test_symlink_escape_rejected(service: VaultService, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text(
        "---\nid: 20260101-0000-s\ntype: fleeting\ncreated: 2026-01-01\n---\nsecret\n",
        encoding="utf-8",
    )
    (service.vault.root / "30_Resources" / "leak").symlink_to(outside, target_is_directory=True)
    with pytest.raises(MCPError, match=r"escapes|not found"):
        service.get_note("30_Resources/leak/secret.md")
    assert service.safe_rel("10_Domains/D1/_MOC.md") == "10_Domains/D1/_MOC.md"
    with pytest.raises(MCPError, match="escapes"):
        service.safe_rel("30_Resources/leak/secret.md")
    with pytest.raises(MCPError, match="not found"):
        service.get_note("10_Domains/D1/missing.md")


def test_query_frontmatter_and_limits(service: VaultService) -> None:
    rows = service.query_frontmatter(status="verified", domain="D2")
    assert rows and all(r["status"] == "verified" and "D2" in r["domains"] for r in rows)
    assert all(r["classification"] != "confidential" for r in service.query_frontmatter())
    assert len(service.query_frontmatter(limit=3)) == 3
    with pytest.raises(MCPError, match="bad filter"):
        service.query_frontmatter(order="rank")
    with pytest.raises(MCPError, match="bad filter"):
        service.query_frontmatter(bogus=1)


def test_list_domains_and_stats(service: VaultService) -> None:
    d = service.list_domains()
    assert d["level"] == 2 and d["packs"] == ["myelin.core", "brian.physical-ai"]
    roles = {x["id"]: x["role"] for x in d["configured"]}
    assert roles == {"D1": "primary", "D3": "research", "D4": "growth", "D2": "extra"}
    d3 = next(x for x in d["configured"] if x["id"] == "D3")
    assert d3["name"] == "자율학습 Robotics" and d3["notes"] == 11 and d3["accent"] == "lime"
    assert d["declared_but_inactive"] == []
    st = service.vault_stats(date(2026, 10, 18))
    assert st["notes"] == 35 and st["kpi"][0]["kpi"] == "inbox_dwell_days"
    assert service.vault_stats()["notes"] == 35


def test_write_draft_disabled_by_default(service: VaultService) -> None:
    assert service.write_enabled is False
    with pytest.raises(MCPError, match="disabled"):
        service.write_draft("x", "body")
    assert not list((service.vault.root / AI_DRAFTS).glob("x.md"))


def test_write_draft_requires_level(vault_root: Path) -> None:
    set_mcp(vault_root, write_draft=True, level=0)
    svc = VaultService.open(vault_root)
    assert svc.write_enabled is False
    with pytest.raises(MCPError, match="disabled"):
        svc.write_draft("x", "body")


def test_write_draft_enabled(vault_root: Path) -> None:
    set_mcp(vault_root, write_draft=True)
    # give the vault the core templates (fixture vault has none) by copying from the golden scaffold
    import shutil

    golden = (
        Path(__file__).resolve().parents[3] / "tests/fixtures/golden/init-basic/90_System/templates"
    )
    shutil.copytree(golden, vault_root / "90_System/templates", dirs_exist_ok=True)
    svc = VaultService.open(vault_root)
    assert svc.write_enabled
    now = datetime(2026, 10, 18, 14, 30)
    res = svc.write_draft(
        "MCP 초안 테스트",
        "본문 내용 trigram 검색용",
        type="evergreen",
        domain=["D1"],
        tags=["mcp", "test"],
        source=["https://example.org"],
        now=now,
    )
    assert res["path"] == f"{AI_DRAFTS}/MCP 초안 테스트.md" and res["id"] == "20261018-1430-mcp"
    text = (vault_root / res["path"]).read_text(encoding="utf-8")
    assert "origin: claude" in text and "status: draft" in text and "domain: [D1]" in text
    assert "tags: [mcp, test]" in text and '"https://example.org"' in text
    got = svc.get_note(res["path"])
    assert got["origin"] == "claude" and "trigram" in got["body"]
    assert svc.search_notes("trigram")[0]["path"] == res["path"]
    # never overwrite
    with pytest.raises(MCPError, match="already exists"):
        svc.write_draft("MCP 초안 테스트", "again", now=now)
    assert "again" not in (vault_root / res["path"]).read_text(encoding="utf-8")
    # validation
    for bad in ("", "a/b", ".hidden", "x" * 121):
        with pytest.raises(MCPError, match="title"):
            svc.write_draft(bad, "b", now=now)
    with pytest.raises(MCPError, match="unknown note type"):
        svc.write_draft("t2", "b", type="note", now=now)
    with pytest.raises(MCPError, match="not configured"):
        svc.write_draft("t3", "b", domain=["D9"], now=now)
    # draft that fails frontmatter validation is removed (tag pattern violation)
    with pytest.raises(MCPError, match="removed"):
        svc.write_draft("t4", "b", tags=["Bad Tag"], now=now)
    assert not (vault_root / AI_DRAFTS / "t4.md").exists()
    (vault_root / "90_System/templates/fleeting.md").unlink()
    with pytest.raises(MCPError, match="template missing"):
        svc.write_draft("t5", "b", now=now)


def test_refresh_reports_changes(service: VaultService) -> None:
    r = service.refresh()
    assert r["unchanged"] == 35 and r["added"] == 0
