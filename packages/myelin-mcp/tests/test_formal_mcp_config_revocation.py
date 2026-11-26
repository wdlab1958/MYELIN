"""Deterministic reproduction of the TLC counterexample for `formal/mcp-config-revocation-stale`.

Trace (MC_bug.cfg / MC_bug_p2.cfg, FIX = FALSE):

    Open → Revoke(c) → Begin(r) → Check(r) [cache[c] = TRUE] → Prepare(r) → Release(r)

The MCP server process (VaultService) loads `myelin.yaml` once at Open. Another process (Hub
`PUT /api/settings`, `myelin` CLI or an editor) then commits the revocation to disk. A tool call
that *starts after* the revocation is on disk must not release anything (frozen properties
P1 `Inv_NoDraftAfterRevoke`, P2 `Inv_NoConfidentialAfterRevoke`).

The schedule is forced by plain sequencing in one thread: the revocation is a completed disk
write strictly before the tool call acquires the service lock (Begin), so there is no timing
dependence at all.
"""

from __future__ import annotations

import contextlib
import shutil
from pathlib import Path

from myelin_core.vault import AI_DRAFTS
from myelin_mcp.service import MCPError, VaultService

from .conftest import REPO_ROOT

CONFIDENTIAL = "40_IP/candidates/Agentic CAD 검증 루프.md"


def _write_policy(root: Path, base: str, *, write_draft: bool, expose: bool) -> None:
    """The other process of the trace: persist the `mcp:` policy to myelin.yaml (atomic, A3)."""
    text = (
        base
        + "mcp:\n"
        + f"  write_draft: {str(write_draft).lower()}\n"
        + f"  expose_confidential: {str(expose).lower()}\n"
    )
    (root / "myelin.yaml").write_text(text, encoding="utf-8")


def _install_templates(root: Path) -> None:
    golden = REPO_ROOT / "tests/fixtures/golden/init-basic/90_System/templates"
    shutil.copytree(golden, root / "90_System/templates", dirs_exist_ok=True)


def test_p1_no_draft_after_write_draft_revoked(vault_root: Path) -> None:
    base = (vault_root / "myelin.yaml").read_text(encoding="utf-8")
    _install_templates(vault_root)
    _write_policy(vault_root, base, write_draft=True, expose=False)

    # Open: the MCP server starts with write_draft allowed (write_draft tool registered).
    svc = VaultService.open(vault_root)
    assert svc.write_enabled

    # Revoke("write"): another process commits `mcp.write_draft: false` to disk.
    _write_policy(vault_root, base, write_draft=False, expose=False)

    # Begin → Check → Prepare → Release: a tool call that starts after the revocation.
    title = "철회 후 초안"
    # Denial (MCPError) is the correct outcome; the property below is what is judged.
    with contextlib.suppress(MCPError):
        svc.write_draft(title, "revoked body")
    target = vault_root / AI_DRAFTS / f"{title}.md"
    assert not target.exists(), (
        "P1 Inv_NoDraftAfterRevoke violated: a write_draft call that started after "
        "`mcp.write_draft: false` was on disk created " + str(target.relative_to(vault_root))
    )


def test_p2_no_confidential_after_expose_revoked(vault_root: Path, local_session: None) -> None:
    base = (vault_root / "myelin.yaml").read_text(encoding="utf-8")
    _write_policy(vault_root, base, write_draft=False, expose=True)

    # Open: LOCAL process with expose_confidential allowed (A2).
    svc = VaultService.open(vault_root)
    assert svc.expose_confidential

    # Revoke("expose"): another process commits `mcp.expose_confidential: false` to disk.
    _write_policy(vault_root, base, write_draft=False, expose=False)

    # A get_note call that starts after the revocation.
    n = svc.get_note(CONFIDENTIAL)
    assert n["redacted"] is True and "Agentic" not in n["body"], (
        "P2 Inv_NoConfidentialAfterRevoke violated: get_note started after "
        "`mcp.expose_confidential: false` was on disk returned the body of " + CONFIDENTIAL
    )
    # A search call that starts after the revocation.
    hits = svc.search_notes("아이디어")
    leaked = [h["path"] for h in hits if h["classification"] == "confidential"]
    assert not leaked, (
        "P2 Inv_NoConfidentialAfterRevoke violated: search_notes started after "
        f"`mcp.expose_confidential: false` was on disk returned confidential notes {leaked}"
    )


def test_domain_list_follows_the_file_too(vault_root: Path) -> None:
    """Side finding F3 of the same run: `list_domains` and the Domain check of write_draft used
    the start-up copy. The per-call reload that fixes F1 covers them."""
    svc = VaultService.open(vault_root)
    assert "D2" in [d["id"] for d in svc.list_domains()["configured"]]
    cfg = vault_root / "myelin.yaml"
    cfg.write_text(
        cfg.read_text(encoding="utf-8")
        .replace("extra: [D2]", "extra: []")
        .replace("level: 2", "level: 0"),
        encoding="utf-8",
    )
    d = svc.list_domains()
    assert "D2" not in [x["id"] for x in d["configured"]] and d["level"] == 0


def test_invalid_config_refuses_every_call_until_fixed(vault_root: Path) -> None:
    """Fail-closed branch of the fix: a broken myelin.yaml must not leave the old permissions."""
    import pytest

    svc = VaultService.open(vault_root)
    cfg = vault_root / "myelin.yaml"
    good = cfg.read_text(encoding="utf-8")
    cfg.write_text("level: [not, a, level\n", encoding="utf-8")
    for call in (
        lambda: svc.search_notes("WCET"),
        lambda: svc.get_note(CONFIDENTIAL),
        lambda: svc.list_domains(),
        lambda: svc.vault_stats(),
    ):
        with pytest.raises(MCPError, match="invalid"):
            call()
    cfg.unlink()
    with pytest.raises(MCPError):
        svc.search_notes("WCET")
    cfg.write_text(good, encoding="utf-8")
    assert svc.search_notes("WCET")  # recovers without a restart


def test_write_draft_refuses_secrets_and_customer_names(vault_root: Path) -> None:
    """고객정보 가드 (ADR-0017): must-block and must-pass through the MCP write path."""
    import pytest

    base = (vault_root / "myelin.yaml").read_text(encoding="utf-8")
    _install_templates(vault_root)
    _write_policy(vault_root, base, write_draft=True, expose=False)
    (vault_root / ".myelin").mkdir(exist_ok=True)
    (vault_root / ".myelin/customer-names.txt").write_text("테스트고객사\n", encoding="utf-8")
    svc = VaultService.open(vault_root)
    for title, body, word in (
        ("누출 초안", "password = Sup3rS3cret!!", "Sup3rS3cret"),
        ("고객 초안", "테스트고객사 포털에서 본 것", "테스트고객사"),
    ):
        with pytest.raises(MCPError, match="customer-information guard") as exc:
            svc.write_draft(title, body)
        assert word not in str(exc.value)
        assert not (vault_root / AI_DRAFTS / f"{title}.md").exists()
    res = svc.write_draft("정상 초안", "금융 고객 유형에서 비밀번호 정책을 12자로 권고했다")
    assert (vault_root / res["path"]).is_file()
