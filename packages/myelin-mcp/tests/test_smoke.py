"""MCP 서비스·서버 테스트 — 프라이버시, 경로 탈출, 쓰기 opt-in, stdio e2e."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from mcp import Client, StdioServerParameters

from myelin_mcp import __version__
from myelin_mcp.server import build_server, main
from myelin_mcp.service import NOT_AVAILABLE, ServiceError, VaultService

from .conftest import make_vault, note

READ_TOOLS = {"search_notes", "get_note", "query_frontmatter", "list_domains", "vault_stats"}


def test_version() -> None:
    assert __version__ == "0.0.1"


# ── 프라이버시: 보호 노트는 어떤 경로로도 나오지 않는다 ─────────────────────────
def test_search_never_returns_protected(vault: Path) -> None:
    svc = VaultService(vault)
    paths = {h["path"] for h in svc.search_notes("WCET", limit=50)}
    assert "30_Resources/고객 진단 결과.md" not in paths
    assert "40_IP/아이디어.md" not in paths
    assert "40_IP/candidates/후보.md" in paths  # candidates는 열려 있다 (Guard와 같음)
    assert "10_Domains/AI-ML-AX/WCET 예산은 추론 지연을 포함해야 한다.md" in paths
    assert not any(
        "비밀" in h["snippet"] or "출원 전" in h["snippet"] for h in svc.search_notes("WCET")
    )


@pytest.mark.parametrize(
    "path", ["30_Resources/고객 진단 결과.md", "40_IP/아이디어.md", "./40_IP/../40_IP/아이디어.md"]
)
def test_get_note_refuses_protected(vault: Path, path: str) -> None:
    with pytest.raises(ServiceError) as info:
        VaultService(vault).get_note(path=path)
    assert NOT_AVAILABLE in str(info.value)


def test_protected_by_id_and_query(vault: Path) -> None:
    svc = VaultService(vault)
    assert all(r["path"] != "40_IP/아이디어.md" for r in svc.query_frontmatter(note_type="idea-ip"))
    secret = svc.index.counts()
    assert secret.get("protected") == 2


def test_route_claude_opens_confidential(tmp_path: Path) -> None:
    v = make_vault(tmp_path / "v")
    cfg = v / "myelin.yaml"
    cfg.write_text(
        cfg.read_text(encoding="utf-8").replace('"confidential": local', '"confidential": claude'),
        encoding="utf-8",
    )
    svc = VaultService(v)
    assert (
        svc.get_note(path="30_Resources/고객 진단 결과.md")["frontmatter"]["classification"]
        == "confidential"
    )
    with pytest.raises(ServiceError):
        svc.get_note(path="40_IP/아이디어.md")


def test_classification_change_reindexes(vault: Path) -> None:
    svc = VaultService(vault)
    rel = "10_Domains/EMBEDDED-SW/Watchdog은 정책이다.md"
    assert svc.get_note(path=rel)
    note(vault, rel, classification="confidential", domain="[EMBEDDED-SW]", body="바뀜 - 길이 다름")
    svc.index._last_refresh = 0.0
    with pytest.raises(ServiceError):
        svc.get_note(path=rel)


# ── 경로 탈출 ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "path",
    [
        "../../etc/passwd",
        "/etc/passwd",
        "myelin.yaml",
        "90_System/taxonomy.md",
        "50_Journal/x.md",
        ".claude/settings.json",
        "10_Domains/AI-ML-AX/없는 노트.md",
    ],
)
def test_get_note_rejects_outside_or_non_notes(vault: Path, path: str) -> None:
    with pytest.raises(ServiceError):
        VaultService(vault).get_note(path=path)


def test_symlink_escape(tmp_path: Path, vault: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("---\nid: x\n---\n", encoding="utf-8")
    (vault / "10_Domains" / "AI-ML-AX" / "link.md").symlink_to(outside)
    svc = VaultService(vault)
    with pytest.raises(ServiceError):
        svc.get_note(path="10_Domains/AI-ML-AX/link.md")


def test_get_note_by_path_and_id(vault: Path) -> None:
    svc = VaultService(vault)
    by_path = svc.get_note(path=str(vault / "10_Domains/EMBEDDED-SW/Watchdog은 정책이다.md"))
    by_id = svc.get_note(note_id=by_path["id"])
    assert by_id["body"].strip() == "워치독 타이머 설계 교훈" and by_id["path"] == by_path["path"]
    for kwargs in ({}, {"path": "a", "note_id": "b"}):
        with pytest.raises(ServiceError):
            svc.get_note(**kwargs)
    with pytest.raises(ServiceError):
        svc.get_note(note_id="nope")


def test_search_filters_and_errors(vault: Path) -> None:
    svc = VaultService(vault)
    assert [h["domain"] for h in svc.search_notes("교훈", domain="EMBEDDED-SW")] == [
        ["EMBEDDED-SW"]
    ]
    assert svc.search_notes("WCET", status="draft", note_type="literature")[0]["origin"] == "claude"
    with pytest.raises(ServiceError):
        svc.search_notes("   ")


def test_list_domains_and_stats(vault: Path) -> None:
    svc = VaultService(vault)
    domains = {d["id"]: d for d in svc.list_domains()}
    assert (
        set(domains) == {"AI-ML-AX", "EMBEDDED-SW"} and domains["EMBEDDED-SW"]["role"] == "research"
    )
    stats = svc.vault_stats()
    assert stats["level"] == 1 and "doctor" in stats and stats["index"]["protected"] == 2
    assert "고객" not in str(stats)  # 숫자만


def test_not_a_vault(tmp_path: Path) -> None:
    with pytest.raises(ServiceError):
        VaultService(tmp_path)


# ── 쓰기 opt-in ───────────────────────────────────────────────────────────
NOW = datetime(2026, 10, 18, 9, 30, 5)


def test_write_disabled_by_default(vault: Path) -> None:
    with pytest.raises(ServiceError) as info:
        VaultService(vault).write_draft("제목", "본문")
    assert "write_drafts" in str(info.value)


def test_write_draft_when_enabled(tmp_path: Path) -> None:
    v = make_vault(tmp_path / "v", write_drafts=True)
    svc = VaultService(v)
    out = svc.write_draft("ROS2 Executor 요약", "내용", "literature", ["AI-ML-AX"], ['a "b"'], NOW)
    assert out["path"] == "00_Inbox/ai-drafts/ROS2 Executor 요약.md"
    text = (v / out["path"]).read_text(encoding="utf-8")
    assert (
        "origin: claude" in text
        and "status: draft" in text
        and "20261018-0930-ros2-executor" in text
    )
    assert svc.search_notes("Executor")[0]["path"] == out["path"]
    with pytest.raises(ServiceError):  # 덮어쓰기 금지
        svc.write_draft("ROS2 Executor 요약", "x", now=NOW)
    traversal = svc.write_draft("../../10_Domains/x", "y", now=NOW)
    assert traversal["path"].startswith("00_Inbox/ai-drafts/")


@pytest.mark.parametrize(
    ("kwargs", "needle"),
    [
        ({"note_type": "moc"}, "note_type"),
        ({"domain": ["GHOST"]}, "GHOST"),
        ({"title": "   "}, "title"),
        ({"title": "..."}, "title"),
    ],
)
def test_write_draft_rejections(tmp_path: Path, kwargs: dict[str, Any], needle: str) -> None:
    svc = VaultService(make_vault(tmp_path / "v", write_drafts=True))
    args: dict[str, Any] = {"title": "ok", "body": "b", **kwargs}
    with pytest.raises(ServiceError) as info:
        svc.write_draft(**args)
    assert needle in str(info.value)


def test_write_draft_respects_level_zero(tmp_path: Path) -> None:
    svc = VaultService(make_vault(tmp_path / "v", level=0, write_drafts=True))
    with pytest.raises(ServiceError) as info:
        svc.write_draft("t", "b")
    assert "Level 0" in str(info.value)


# ── 서버 (MCP 프로토콜) ────────────────────────────────────────────────────
async def _tools(vault: Path) -> set[str]:
    async with Client(build_server(vault)) as c:
        return {t.name for t in (await c.list_tools()).tools}


def test_default_tools_are_read_only(vault: Path, tmp_path: Path) -> None:
    assert asyncio.run(_tools(vault)) == READ_TOOLS
    writable = make_vault(tmp_path / "w", write_drafts=True)
    assert asyncio.run(_tools(writable)) == READ_TOOLS | {"write_draft"}


def test_tool_annotations_and_errors(vault: Path) -> None:
    async def run() -> None:
        async with Client(build_server(vault)) as c:
            tools = {t.name: t for t in (await c.list_tools()).tools}
            assert all(t.annotations and t.annotations.read_only_hint for t in tools.values())
            bad = await c.call_tool("get_note", {"path": "../../etc/passwd"})
            assert bad.is_error and NOT_AVAILABLE in bad.content[0].text  # type: ignore[union-attr]
            ok = await c.call_tool("search_notes", {"query": "워치독"})
            assert not ok.is_error and ok.structured_content
            assert ok.structured_content["result"][0]["title"] == "Watchdog은 정책이다"
            for name, args in (
                ("query_frontmatter", {"status": "draft"}),
                ("list_domains", {}),
                ("vault_stats", {}),
                ("get_note", {"note_id": "nope"}),
            ):
                await c.call_tool(name, args)

    asyncio.run(run())


def test_write_tool_through_protocol(tmp_path: Path) -> None:
    v = make_vault(tmp_path / "w", write_drafts=True)

    async def run() -> Any:
        async with Client(build_server(v)) as c:
            return await c.call_tool("write_draft", {"title": "프로토콜 초안", "body": "x"})

    res = asyncio.run(run())
    assert not res.is_error and (v / "00_Inbox/ai-drafts/프로토콜 초안.md").is_file()


def test_stdio_end_to_end(vault: Path) -> None:
    """실제 하위 프로세스(stdio)로 띄워 Claude Desktop/Code와 같은 방식으로 호출한다."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "myelin_mcp", "--vault", str(vault)],
        env={"PYTHONPATH": os.pathsep.join(sys.path)},
    )

    async def run() -> tuple[set[str], Any]:
        async with Client(params) as c:
            names = {t.name for t in (await c.list_tools()).tools}
            res = await c.call_tool("search_notes", {"query": "WCET"})
            return names, res

    names, res = asyncio.run(run())
    assert names == READ_TOOLS
    assert not res.is_error and all(
        "40_IP/아이디어" not in h["path"] for h in res.structured_content["result"]
    )


def test_main_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("MYELIN_VAULT", raising=False)
    assert main([]) == 2
    assert main(["--vault", str(tmp_path)]) == 2
    assert "Vault가 아닙니다" in capsys.readouterr().err


def test_main_runs_server(vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []
    from mcp.server.mcpserver import MCPServer

    monkeypatch.setattr(
        MCPServer, "run", lambda self, transport="stdio", **kw: called.append(transport)
    )
    assert main(["--vault", str(vault)]) == 0 and called == ["stdio"]
