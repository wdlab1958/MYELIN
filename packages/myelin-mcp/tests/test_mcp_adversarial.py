"""Agent-test campaign — MCP server adversarial suite (정본 §7.3, ADR-0007).

Tools are exercised through the MCPServer in-process (`server.call_tool`, the same path the stdio
client takes after JSON-RPC decoding), so argument validation and error wrapping are included.
"""

from __future__ import annotations

import asyncio
import shutil
import threading
from pathlib import Path
from typing import Any

import pytest

from myelin_core.vault import AI_DRAFTS
from myelin_mcp.__main__ import main
from myelin_mcp.server import build_server
from myelin_mcp.service import REDACTED, MCPError, VaultService

from .conftest import REPO_ROOT, set_mcp

CONFIDENTIAL_PATHS = {
    "40_IP/candidates/Agentic CAD 검증 루프.md",
    "40_IP/candidates/프롬프트 인젭션 다층 가드 아이디어.md",
}
CONFIDENTIAL_TITLES = {Path(p).stem for p in CONFIDENTIAL_PATHS}
CONFIDENTIAL_IDS = {"20260922-1200-ip-agentic-cad", "20260915-1500-ip-prompt-guard"}
GOLDEN_TEMPLATES = REPO_ROOT / "tests/fixtures/golden/init-basic/90_System/templates"


class ToolRefusedError(Exception):
    """Argument validation failure or a MYELIN policy error surfaced to the client."""


def call(server: Any, name: str, **args: Any) -> Any:
    try:
        result = asyncio.run(server.call_tool(name, args))
    except Exception as exc:  # ToolError / UnexpectedToolError: the client sees an error result
        raise ToolRefusedError(f"{exc}: {exc.__cause__ or ''}") from None
    if result.is_error:
        raise ToolRefusedError("".join(getattr(c, "text", "") for c in result.content))
    sc = result.structured_content
    if isinstance(sc, dict) and set(sc) == {"result"}:
        return sc["result"]
    return sc


def _leaks(obj: Any) -> bool:
    text = repr(obj)
    return any(t in text for t in CONFIDENTIAL_TITLES | CONFIDENTIAL_IDS) or "40_IP/" in text


@pytest.fixture
def server(service: VaultService) -> Any:
    return build_server(service)


# ----------------------------------------------------------------------------- bad arguments
@pytest.mark.parametrize(
    "name,args",
    [
        ("search_notes", {}),
        ("search_notes", {"query": 123}),
        ("search_notes", {"query": ["a"]}),
        ("search_notes", {"query": None}),
        ("search_notes", {"query": "WCET", "limit": 2.5}),
        ("search_notes", {"query": "WCET", "limit": "many"}),
        ("search_notes", {"query": "WCET", "status": 5}),
        ("search_notes", {"query": "   "}),
        ("get_note", {}),
        ("get_note", {"ref": 5}),
        ("get_note", {"ref": ""}),
        ("get_note", {"ref": "nope"}),
        ("query_frontmatter", {"limit": "abc"}),
        ("query_frontmatter", {"order": "created; DROP TABLE notes"}),
        ("query_frontmatter", {"order": "rank"}),
        ("vault_stats", {"today": "2026-13-45"}),
        ("vault_stats", {"today": "18/10/2026"}),
        ("vault_stats", {"today": 20261018}),
        ("nope", {}),
        ("write_draft", {"title": "x", "body": "y"}),  # not registered by default
    ],
)
def test_bad_arguments_are_refused_not_crashes(
    server: Any, name: str, args: dict[str, Any]
) -> None:
    with pytest.raises(ToolRefusedError):
        call(server, name, **args)


@pytest.mark.parametrize(
    "query",
    [
        "' OR 1=1 --",
        '"*"',
        "NEAR(a b)",
        "NEAR(",
        'WCET"',
        '"WCET',
        "WCET OR",
        "AND",
        "NOT WCET",
        "col:WCET",
        "WCET*",
        ".*+?[]{}()^$\\",
        "%_%",
        "\\",
        "x" * 100_000,
        "abc " * 25_000,
        "🙂 émoji 한글",
    ],
)
def test_search_syntax_is_quoted_never_injected(server: Any, query: str) -> None:
    hits = call(server, "search_notes", query=query, limit=200)
    assert isinstance(hits, list)
    assert not _leaks(hits)
    for h in hits:
        assert h["classification"] != "confidential" and not h["path"].startswith("40_IP/")


def test_search_filters_are_parameterized(server: Any) -> None:
    for kw in ("domain", "status", "type"):
        assert call(server, "search_notes", query="WCET", **{kw: "D2' OR '1'='1"}) == []
    assert call(server, "query_frontmatter", tag="x' OR 1=1 --") == []
    assert call(server, "query_frontmatter", domain="D2' OR '1'='1") == []
    assert call(server, "query_frontmatter", created_from="notadate") == []


def test_limits_are_clamped(server: Any) -> None:
    assert len(call(server, "search_notes", query="WCET", limit=-5)) >= 1
    assert len(call(server, "search_notes", query="WCET", limit=10**12)) <= 200
    assert len(call(server, "query_frontmatter", limit=0)) == 1
    assert len(call(server, "query_frontmatter", limit=10**9)) <= 1000


# ----------------------------------------------------------------------------- path boundary
@pytest.mark.parametrize(
    "ref",
    [
        "../basic/myelin.yaml",
        "../../etc/passwd",
        "/etc/passwd",
        "~/x.md",
        "~root/x.md",
        "10_Domains/../../x.md",
        "10_Domains/D1/../../../x.md",
        "a/" * 50_000,
        "10_Domains/\x00",
        "myelin.yaml",
        ".myelin/index.db",
        "CLAUDE.md",
        ".git/config",
        "..\\..\\etc\\passwd",
        "40_IP/candidates/../../myelin.yaml",
    ],
)
def test_get_note_ref_traversal_refused(server: Any, ref: str) -> None:
    with pytest.raises(ToolRefusedError) as exc:
        call(server, "get_note", ref=ref)
    assert "root:x:0" not in str(exc.value)  # never echoes outside content (only the ref itself)


def test_get_note_symlink_escape_refused(service: VaultService, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text(
        "---\nid: 20260101-0000-s\ntype: fleeting\ncreated: 2026-01-01\n---\nSECRET-BODY\n",
        encoding="utf-8",
    )
    (service.vault.root / "30_Resources/leak").symlink_to(outside, target_is_directory=True)
    server = build_server(service)
    with pytest.raises(ToolRefusedError) as exc:
        call(server, "get_note", ref="30_Resources/leak/secret.md")
    assert "SECRET-BODY" not in str(exc.value)


# ----------------------------------------------------------------------------- confidential
def test_confidential_hidden_by_default_everywhere(server: Any) -> None:
    assert call(server, "search_notes", query="아이디어") == []
    assert call(server, "search_notes", query="Agentic") == []
    assert call(server, "search_notes", query="CAD", type="idea-ip") == []
    assert call(server, "query_frontmatter", classification="confidential") == []
    assert call(server, "query_frontmatter", type="idea-ip") == []
    assert call(server, "query_frontmatter", domain="D1", limit=1000) != []
    for rows in (
        call(server, "query_frontmatter", limit=1000),
        call(server, "search_notes", query="설계", limit=200),
    ):
        assert rows and not _leaks(rows)
    # direct access by path/id/stem: frontmatter only, body withheld (ADR-0007 §3)
    for ref in [*CONFIDENTIAL_PATHS, *CONFIDENTIAL_IDS, *(p[:-3] for p in CONFIDENTIAL_PATHS)]:
        n = call(server, "get_note", ref=ref)
        assert n["redacted"] is True and n["body"] == REDACTED, ref
    # backlinks of a public note must not name confidential notes (title leaks via path)
    for path in [
        "10_Domains/D4/설계 규칙은 실패에서 태어난다.md",
        "10_Domains/D1/LLM 평가는 오프라인 지표만으로 충분하지 않다.md",
    ]:
        n = call(server, "get_note", ref=path)
        assert n["redacted"] is False
        assert not any(b.startswith("40_IP/") for b in n["backlinks"]), n["backlinks"]
    # aggregate tools expose counts, never titles/paths
    assert not _leaks(call(server, "vault_stats", today="2026-10-18"))
    assert not _leaks(call(server, "list_domains"))


def test_expose_confidential_opt_in_restores_backlinks(
    vault_root: Path, local_session: None
) -> None:
    set_mcp(vault_root, expose=True)
    server = build_server(VaultService.open(vault_root))
    n = call(server, "get_note", ref="10_Domains/D4/설계 규칙은 실패에서 태어난다.md")
    assert any(b.startswith("40_IP/") for b in n["backlinks"])
    n = call(server, "get_note", ref=next(iter(CONFIDENTIAL_PATHS)))
    assert n["redacted"] is False and n["body"] != REDACTED


def test_resources_and_prompts_do_not_exist_or_leak(server: Any) -> None:
    assert asyncio.run(server.list_resources()) == []
    assert asyncio.run(server.list_resource_templates()) == []
    assert asyncio.run(server.list_prompts()) == []
    tools = asyncio.run(server.list_tools())
    assert not _leaks([t.description for t in tools])


# ----------------------------------------------------------------------------- write_draft
def _enable_write(vault_root: Path, level: int | None = None) -> VaultService:
    set_mcp(vault_root, write_draft=True, level=level)
    shutil.copytree(GOLDEN_TEMPLATES, vault_root / "90_System/templates", dirs_exist_ok=True)
    return VaultService.open(vault_root)


def test_write_draft_refused_at_level_0_and_when_disabled(vault_root: Path) -> None:
    svc0 = _enable_write(vault_root, level=0)
    assert svc0.write_enabled is False
    assert "write_draft" not in {t.name for t in asyncio.run(build_server(svc0).list_tools())}
    with pytest.raises(MCPError, match="disabled"):
        svc0.write_draft("x", "y")
    with pytest.raises(ToolRefusedError, match="Unknown tool"):
        call(build_server(svc0), "write_draft", title="x", body="y")
    # write_draft: false explicitly, level 2
    text = (vault_root / "myelin.yaml").read_text(encoding="utf-8")
    text = text.replace("write_draft: true", "write_draft: false").replace("level: 0", "level: 2")
    (vault_root / "myelin.yaml").write_text(text, encoding="utf-8")
    svc = VaultService.open(vault_root)
    assert svc.write_enabled is False
    with pytest.raises(ToolRefusedError, match="Unknown tool"):
        call(build_server(svc), "write_draft", title="x", body="y")
    assert not list((vault_root / AI_DRAFTS).glob("x.md"))


@pytest.mark.parametrize(
    "title",
    [
        "",
        "   ",
        "a/b",
        "/abs",
        "..",
        "...",
        "a/../b",
        ".hidden",
        "..x",
        "x" * 121,
        "x" * 300,
        "a\\b",
        "..\\..\\x",
        "x\x00y",
        "a\nb",
        "a\rb",
        "a\tb",
        "a\x7fb",
        "a‮b",
        "a⁦b",
    ],
)
def test_write_draft_rejects_bad_titles(vault_root: Path, title: str) -> None:
    svc = _enable_write(vault_root)
    before = sorted(p.name for p in (vault_root / AI_DRAFTS).iterdir())
    with pytest.raises(ToolRefusedError, match="title"):
        call(build_server(svc), "write_draft", title=title, body="b")
    assert sorted(p.name for p in (vault_root / AI_DRAFTS).iterdir()) == before
    assert not any(p.is_file() for p in vault_root.glob("x*")) or title.startswith("x" * 3)


@pytest.mark.parametrize(
    "args",
    [
        {"title": "t1", "body": "b", "domain": "D1"},  # must be a list
        {"title": "t2", "body": "b", "tags": "x"},
        {"title": "t3", "body": "b", "type": 5},
        {"title": "t4"},  # body missing
        {"title": "t5", "body": "b", "type": "note"},
        {"title": "t6", "body": "b", "domain": ["D9"]},
        {"title": "t7", "body": "b", "domain": ["../D1"]},
        {"title": "t8", "body": "b", "tags": ["Bad Tag"]},  # schema violation → file removed
        {"title": "t9", "body": "b", "type": "../../etc/passwd"},
    ],
)
def test_write_draft_rejects_bad_fields_without_side_effects(
    vault_root: Path, args: dict[str, Any]
) -> None:
    svc = _enable_write(vault_root)
    before = sorted(p.name for p in (vault_root / AI_DRAFTS).iterdir())
    with pytest.raises(ToolRefusedError):
        call(build_server(svc), "write_draft", **args)
    assert sorted(p.name for p in (vault_root / AI_DRAFTS).iterdir()) == before


def test_write_draft_only_creates_in_ai_drafts(vault_root: Path) -> None:
    svc = _enable_write(vault_root)
    server = build_server(svc)
    snapshot = {p.relative_to(vault_root) for p in vault_root.rglob("*") if p.is_file()}
    res = call(
        server,
        "write_draft",
        title="MCP adversarial 초안",
        body="본문",
        type="idea-ip",  # type cannot pull the file into 40_IP
        domain=["D1"],
        tags=["mcp"],
        source=["[[WCET 예산은 측정값의 1.5배로 잡는다]]"],
    )
    assert res["path"] == f"{AI_DRAFTS}/MCP adversarial 초안.md"
    assert res["status"] == "draft" and res["origin"] == "claude"
    after = {p.relative_to(vault_root) for p in vault_root.rglob("*") if p.is_file()}
    new = {str(p) for p in after - snapshot if not str(p).startswith(".myelin/")}
    assert new == {res["path"]}
    text = (vault_root / res["path"]).read_text(encoding="utf-8")
    assert "origin: claude" in text and "status: draft" in text
    note = call(server, "get_note", ref=res["path"])
    assert note["origin"] == "claude" and note["status"] == "draft"
    # never overwrites, even via a second server instance
    with pytest.raises(ToolRefusedError, match="already exists"):
        call(
            build_server(VaultService.open(vault_root)),
            "write_draft",
            title="MCP adversarial 초안",
            body="x",
        )
    assert (vault_root / res["path"]).read_text(encoding="utf-8") == text


# ----------------------------------------------------------------------------- concurrency
def test_concurrent_tool_calls_do_not_crash_sqlite(service: VaultService) -> None:
    server = build_server(service)

    async def burst() -> list[Any]:
        return await asyncio.gather(
            *[server.call_tool("search_notes", {"query": "WCET"}) for _ in range(10)],
            *[server.call_tool("get_note", {"ref": "20260907-0800-wcet-budget"}) for _ in range(5)],
            *[server.call_tool("vault_stats", {}) for _ in range(5)],
        )

    results = asyncio.run(burst())
    assert len(results) == 20 and all(not r.is_error for r in results)

    errors: list[str] = []

    def worker() -> None:
        try:
            for _ in range(20):
                service.search_notes("WCET")
                service.get_note("20260907-0800-wcet-budget")
                service.query_frontmatter(status="verified")
                service.vault_stats()
        except Exception as exc:
            errors.append(repr(exc))

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []


# ----------------------------------------------------------------------------- startup
def test_startup_fails_closed_outside_a_vault(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert main(["--vault", str(tmp_path)]) == 2
    assert "not a MYELIN Vault" in capsys.readouterr().err
    monkeypatch.delenv("MYELIN_VAULT", raising=False)
    monkeypatch.chdir(tmp_path)
    assert main([]) == 2
    assert "myelin.yaml missing" in capsys.readouterr().err
    (tmp_path / "myelin.yaml").write_text("level: 9\n", encoding="utf-8")
    assert main(["--vault", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("myelin-mcp:") and "Traceback" not in err
    assert main(["--vault", str(tmp_path / "missing")]) == 2
