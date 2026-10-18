"""P4-T2/T6/T7 — MCPServer wiring: tool list, read-only default, call_tool round trips."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from myelin_mcp.__main__ import main
from myelin_mcp.server import build_server
from myelin_mcp.service import VaultService

from .conftest import set_mcp

READ_TOOLS = {"search_notes", "get_note", "query_frontmatter", "list_domains", "vault_stats"}


def _call(server: Any, name: str, **args: Any) -> Any:
    """Invoke a tool like a client would; tool errors surface as RuntimeError with the reason."""
    try:
        result = asyncio.run(server.call_tool(name, args))
    except Exception as exc:  # mcp wraps handler errors (UnexpectedToolError) — unwrap the cause
        cause = exc.__cause__ or exc
        raise RuntimeError(f"{exc}: {cause}") from None
    if result.is_error:
        raise RuntimeError("".join(getattr(c, "text", "") for c in result.content))
    sc = result.structured_content
    if isinstance(sc, dict) and set(sc) == {"result"}:
        return sc["result"]
    return sc


def test_default_tools_are_read_only(service: VaultService) -> None:
    server = build_server(service)
    names = {t.name for t in asyncio.run(server.list_tools())}
    assert names == READ_TOOLS  # write_draft absent → 기본 읽기 전용


def test_write_draft_registered_only_when_enabled(vault_root: Path) -> None:
    set_mcp(vault_root, write_draft=True)
    names = {t.name for t in asyncio.run(build_server(VaultService.open(vault_root)).list_tools())}
    assert names == READ_TOOLS | {"write_draft"}
    set_mcp(vault_root, level=0)  # level 0 wins even with write_draft: true
    names0 = {t.name for t in asyncio.run(build_server(VaultService.open(vault_root)).list_tools())}
    assert "write_draft" not in names0


def test_call_tools_round_trip(service: VaultService) -> None:
    server = build_server(service)
    hits = _call(server, "search_notes", query="WCET", limit=5)
    assert isinstance(hits, list) and hits and hits[0]["title"].startswith("WCET")
    note = _call(server, "get_note", ref="20260907-0800-wcet-budget")
    assert note["id"] == "20260907-0800-wcet-budget" and "body" in note
    rows = _call(server, "query_frontmatter", status="verified", domain="D2", limit=50)
    assert rows and all(r["status"] == "verified" for r in rows)
    doms = _call(server, "list_domains")
    assert {d["id"] for d in doms["configured"]} == {"D1", "D2", "D3", "D4"}
    st = _call(server, "vault_stats", today="2026-10-18")
    assert st["notes"] == 35
    with pytest.raises(RuntimeError, match="YYYY-MM-DD"):
        _call(server, "vault_stats", today="18/10/2026")


def test_errors_surface_as_tool_errors(service: VaultService) -> None:
    server = build_server(service)
    with pytest.raises(RuntimeError, match=r"escapes|Vault-relative"):
        _call(server, "get_note", ref="../x.md")
    with pytest.raises(RuntimeError, match="not found"):
        _call(server, "get_note", ref="nope")
    with pytest.raises(RuntimeError, match="MYELIN"):
        _call(server, "search_notes", query="  ")


def test_main_refuses_non_vault(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--vault", str(tmp_path)]) == 2
    assert "myelin.yaml missing" in capsys.readouterr().err
