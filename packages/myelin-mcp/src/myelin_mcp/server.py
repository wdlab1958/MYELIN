"""MYELIN MCP server (stdio) — 정본 §7.3 tools.

search_notes · get_note · query_frontmatter · list_domains · vault_stats, plus write_draft only when
the Vault opts in (ADR-0007). Handlers are async (run on the loop thread); the index is also
lock-protected so worker-thread execution is safe.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from myelin_mcp import __version__
from myelin_mcp.service import MCPError, VaultService

# ADR-0011 §3: an EXTERNAL process must not even advertise that confidential content exists.
INSTRUCTIONS = (
    "MYELIN Personal Knowledge OS — read-only access to one Obsidian Vault. "
    "Notes have Frontmatter v2 (id/type/domain/status/origin/classification). "
    "status: verified notes are human-approved; origin: claude + status: draft are AI drafts. "
    "Never claim to have modified the Vault: only write_draft (if present) creates files, and only "
    "in 00_Inbox/ai-drafts."
)
INSTRUCTIONS_LOCAL = (
    INSTRUCTIONS + " This is a LOCAL-model session (MYELIN_LLM=local): classification: "
    "confidential notes and 40_IP/** are included; never relay them to an external service."
)


def build_server(service: VaultService) -> MCPServer:
    server = MCPServer(
        name="myelin",
        instructions=INSTRUCTIONS_LOCAL if service.expose_confidential else INSTRUCTIONS,
        version=__version__,
    )

    @server.tool(
        name="search_notes",
        description="Full-text search (FTS5) over the Vault. Filters: domain, status, type.",
    )
    async def search_notes(
        query: str,
        domain: str | None = None,
        status: str | None = None,
        type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return _guard(
            lambda: service.search_notes(
                query, domain=domain, status=status, type=type, limit=limit
            )
        )

    @server.tool(
        name="get_note",
        description="Note frontmatter + body + backlinks by Vault-relative path or note id.",
    )
    async def get_note(ref: str) -> dict[str, Any]:
        return _guard(lambda: service.get_note(ref))

    @server.tool(
        name="query_frontmatter",
        description=(
            "Dataview-style frontmatter query: type, status, origin, classification, domain, tag, "
            "share, created_from/to, reviewed_from/to, order (created|reviewed|title|path), limit."
        ),
    )
    async def query_frontmatter(
        type: str | None = None,
        status: str | None = None,
        origin: str | None = None,
        classification: str | None = None,
        domain: str | None = None,
        tag: str | None = None,
        share: bool | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
        reviewed_from: str | None = None,
        reviewed_to: str | None = None,
        order: str = "created",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return _guard(
            lambda: service.query_frontmatter(
                type_=type,
                status=status,
                origin=origin,
                classification=classification,
                domain=domain,
                tag=tag,
                share=share,
                created_from=created_from,
                created_to=created_to,
                reviewed_from=reviewed_from,
                reviewed_to=reviewed_to,
                order=order,
                limit=limit,
            )
        )

    @server.tool(
        name="list_domains",
        description="Configured 3+1 domains (role, note counts, pack metadata) and packs.",
    )
    async def list_domains() -> dict[str, Any]:
        return _guard(service.list_domains)

    @server.tool(
        name="vault_stats",
        description="Personal KPIs (spec §11.1) from the index. today: YYYY-MM-DD optional.",
    )
    async def vault_stats(today: str | None = None) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            try:
                d = date.fromisoformat(today) if today else None
            except ValueError:
                raise MCPError(f"today must be YYYY-MM-DD, got {today!r}") from None
            return service.vault_stats(d)

        return _guard(run)

    if service.write_enabled:

        @server.tool(
            name="write_draft",
            description=(
                "Create a NEW AI draft note in 00_Inbox/ai-drafts (origin claude, status draft). "
                "Never overwrites. Enabled by myelin.yaml mcp.write_draft and level >= 1."
            ),
        )
        async def write_draft(
            title: str,
            body: str,
            type: str = "fleeting",
            domain: list[str] | None = None,
            tags: list[str] | None = None,
            source: list[str] | None = None,
        ) -> dict[str, Any]:
            return _guard(
                lambda: service.write_draft(
                    title, body, type=type, domain=domain, tags=tags, source=source
                )
            )

    return server


def _guard[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except MCPError as exc:
        raise ValueError(f"MYELIN: {exc}") from None


def serve(vault: Path) -> None:
    """Run the server on stdio (the only transport MYELIN supports — ADR-0007 §1)."""
    service = VaultService.open(vault)
    warning = service.routing_warning()
    if warning:
        print(warning, file=sys.stderr, flush=True)
    server = build_server(service)
    server.run(transport="stdio")
