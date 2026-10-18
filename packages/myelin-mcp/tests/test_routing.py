"""ADR-0011 §3 — MCP honours `mcp.expose_confidential: true` only in a LOCAL process."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from myelin_mcp import server as server_mod
from myelin_mcp.server import INSTRUCTIONS, INSTRUCTIONS_LOCAL, build_server, serve
from myelin_mcp.service import REDACTED, VaultService

from .conftest import set_mcp
from .test_server import _call

IP_NOTE = "40_IP/candidates/Agentic CAD 검증 루프.md"


def _descriptions(service: VaultService) -> tuple[str, list[str]]:
    srv = build_server(service)
    tools = asyncio.run(srv.list_tools())
    return str(srv.instructions), [t.description or "" for t in tools]


def test_opt_in_ignored_in_external_process(vault_root: Path) -> None:
    set_mcp(vault_root, expose=True)
    svc = VaultService.open(vault_root)
    assert svc.vault.config.mcp.expose_confidential is True  # the owner did opt in …
    assert svc.expose_confidential is False  # … but the process is EXTERNAL
    warn = svc.routing_warning()
    assert warn and "MYELIN_LLM=local" in warn and "expose_confidential" in warn
    n = svc.get_note(IP_NOTE)
    assert n["redacted"] is True and n["body"] == REDACTED
    assert all(h["classification"] != "confidential" for h in svc.search_notes("아이디어"))
    assert svc.query_frontmatter(classification="confidential") == []
    srv = build_server(svc)
    assert _call(srv, "query_frontmatter", classification="confidential") == []
    assert _call(srv, "get_note", ref=IP_NOTE)["redacted"] is True


@pytest.mark.parametrize("value", ["Local", "LOCAL", "local ", "1", "true", ""])
def test_only_exact_local_value_counts(
    vault_root: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    set_mcp(vault_root, expose=True)
    monkeypatch.setenv("MYELIN_LLM", value)
    svc = VaultService.open(vault_root)
    assert svc.expose_confidential is False and svc.routing_warning()


def test_opt_in_honoured_in_local_process(vault_root: Path, local_session: None) -> None:
    set_mcp(vault_root, expose=True)
    svc = VaultService.open(vault_root)
    assert svc.expose_confidential is True and svc.routing_warning() is None
    assert svc.get_note(IP_NOTE)["redacted"] is False
    instructions, _ = _descriptions(svc)
    assert instructions == INSTRUCTIONS_LOCAL and "confidential" in instructions


def test_no_warning_when_not_opted_in(vault_root: Path, local_session: None) -> None:
    svc = VaultService.open(vault_root)  # default expose_confidential: false
    assert svc.expose_confidential is False and svc.routing_warning() is None


def test_external_descriptions_never_mention_confidential(vault_root: Path) -> None:
    for expose in (False, True):
        set_mcp(vault_root, expose=expose) if expose else None
        instructions, descs = _descriptions(VaultService.open(vault_root))
        assert instructions == INSTRUCTIONS
        for text in (instructions, *descs):
            assert "confidential" not in text.lower(), text
            assert "40_IP" not in text, text


def test_serve_warns_on_stderr_and_runs_redacted(
    vault_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    set_mcp(vault_root, expose=True)
    seen: dict[str, Any] = {}

    class _Dummy:
        def run(self, transport: str) -> None:
            seen["transport"] = transport

    def fake_build(service: VaultService) -> _Dummy:
        seen["expose"] = service.expose_confidential
        return _Dummy()

    monkeypatch.setattr(server_mod, "build_server", fake_build)
    serve(vault_root)
    err = capsys.readouterr().err
    assert "expose_confidential" in err and "MYELIN_LLM=local" in err
    assert seen == {"expose": False, "transport": "stdio"}


def test_serve_silent_when_local(
    vault_root: Path,
    local_session: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    set_mcp(vault_root, expose=True)

    class _Dummy:
        def run(self, transport: str) -> None:
            pass

    monkeypatch.setattr(server_mod, "build_server", lambda service: _Dummy())
    serve(vault_root)
    assert capsys.readouterr().err == ""
