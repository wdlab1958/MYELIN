"""MYELIN MCP 서버 — stdio 전용, 기본 읽기 전용 (ADR-0006).

실행: `myelin-mcp --vault <경로>`  (또는 환경변수 MYELIN_VAULT)
"""

from __future__ import annotations

import argparse
import functools
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from myelin_core.errors import MyelinError
from myelin_mcp import __version__
from myelin_mcp.service import VaultService

READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
WRITE_DRAFT = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False
)

INSTRUCTIONS = """\
MYELIN Vault(개인 지식 저장소) 검색 서버입니다.
- 노트는 Obsidian Markdown이며 frontmatter에 type·status·origin·domain이 있습니다.
- status: verified 노트가 검증된 지식, origin: claude 는 AI 초안입니다. 답할 때 이를 구분하세요.
- 40_IP와 confidential 노트는 로컬 전용이라 이 서버로는 볼 수 없습니다. 우회하지 마세요.
"""


def _tool_errors[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """MyelinError → ToolError (메시지와 위치를 Claude에게 그대로)."""

    @functools.wraps(fn)  # 시그니처 보존 — SDK가 이것으로 도구 인자 스키마를 만든다
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except MyelinError as err:
            raise ToolError("; ".join(str(i) for i in err.issues)) from err

    return wrapper


def build_server(vault: Path) -> MCPServer:
    svc = VaultService(vault)
    server: MCPServer = MCPServer(
        name="myelin", version=__version__, instructions=INSTRUCTIONS, log_level="WARNING"
    )

    @server.tool(annotations=READ_ONLY)
    @_tool_errors
    def search_notes(
        query: str,
        domain: str | None = None,
        note_type: str | None = None,
        status: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Vault 노트 전문 검색 (부분 문자열, 한국어 가능). domain·type·status로 거른다."""
        return svc.search_notes(query, domain, note_type, status, limit)

    @server.tool(annotations=READ_ONLY)
    @_tool_errors
    def get_note(path: str | None = None, note_id: str | None = None) -> dict[str, Any]:
        """노트 하나의 frontmatter와 본문. path(Vault 상대경로) 또는 note_id 중 하나."""
        return svc.get_note(path=path, note_id=note_id)

    @server.tool(annotations=READ_ONLY)
    @_tool_errors
    def query_frontmatter(
        domain: str | None = None,
        note_type: str | None = None,
        status: str | None = None,
        origin: str | None = None,
        tag: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """frontmatter 조건으로 노트 목록 (본문 없음). 날짜는 YYYY-MM-DD."""
        return svc.query_frontmatter(
            domain=domain,
            note_type=note_type,
            status=status,
            origin=origin,
            tag=tag,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
        )

    @server.tool(annotations=READ_ONLY)
    @_tool_errors
    def list_domains() -> list[dict[str, Any]]:
        """이 Vault의 Domain(역할·Pack·노트 수)."""
        return svc.list_domains()

    @server.tool(annotations=READ_ONLY)
    @_tool_errors
    def vault_stats() -> dict[str, Any]:
        """지표(§11.1)와 doctor 요약 — 숫자만, 노트 내용·경로 없음."""
        return svc.vault_stats()

    if svc.write_enabled:

        @server.tool(annotations=WRITE_DRAFT)
        @_tool_errors
        def write_draft(
            title: str,
            body: str,
            note_type: str = "literature",
            domain: list[str] | None = None,
            source: list[str] | None = None,
        ) -> dict[str, Any]:
            """00_Inbox/ai-drafts 에 초안을 만든다 (origin: claude, draft, 덮어쓰기 없음)."""
            return svc.write_draft(title, body, note_type, domain, source)

    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="myelin-mcp", description="MYELIN MCP server (stdio)")
    parser.add_argument("--vault", default=os.environ.get("MYELIN_VAULT"), help="Vault 경로")
    parser.add_argument("--version", action="version", version=f"myelin-mcp {__version__}")
    args = parser.parse_args(argv)
    if not args.vault:
        print("myelin-mcp: --vault 또는 MYELIN_VAULT 가 필요합니다", file=sys.stderr)
        return 2
    try:
        server = build_server(Path(args.vault).expanduser())
    except MyelinError as err:
        print(f"myelin-mcp: {err}", file=sys.stderr)
        return 2
    server.run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
