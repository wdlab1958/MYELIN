"""formal/hub-config-stale-cache F1 — the Hub decides with myelin.yaml on disk, not a stale cache.

`myelin add-domain` runs in another process and rewrites `<Vault>/myelin.yaml`. The running Hub
must list the new Domain, accept a promotion into it (ADR-0009 §3: "Domain 이 설정된 것"), and a
Settings save must not write the stale Domain list back (ADR-0004 §2: `domains.extra` belongs to
add-domain; the Settings page cannot edit Domains). TLC traces: formal/hub-config-stale-cache/.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from myelin_core.config import load_config

from .conftest import CLICK, REPO_ROOT

NEW_DOMAIN = "SEC-CONSULT"  # declared by packs/a3.security-consulting, not in the basic fixture
DRAFT = "00_Inbox/ai-drafts/Lit - 양자화 서베이.md"


def _cli_add_domain(vault_root: Path, domain: str) -> None:
    """The other actor of the trace: `myelin add-domain` as a separate OS process (CliAddDomain)."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "myelin_cli",
            "add-domain",
            domain,
            "--vault",
            str(vault_root),
            "--packs-dir",
            str(REPO_ROOT / "packs"),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert domain in load_config(vault_root).domains.all_ids  # the file on disk changed


def test_f1_hub_sees_domain_added_by_cli_without_restart(
    client: TestClient, vault_root: Path
) -> None:
    """Trace trace_bug_P1.md: CliAddDomain(d1) -> HubPromote(d1) rejected, yet d1 is in the file."""
    assert NEW_DOMAIN not in {d["id"] for d in client.get("/api/domains").json()}  # Hub loaded
    _cli_add_domain(vault_root, NEW_DOMAIN)
    on_disk = set(load_config(vault_root).domains.all_ids)
    # P1: every Hub decision reflects the Domain list currently in myelin.yaml
    r = client.post(f"/api/review/promote/{DRAFT}", headers=CLICK, json={"domain": NEW_DOMAIN})
    assert r.status_code == 200, f"P1 violated (stale reject): {r.status_code} {r.text}"
    assert r.json()["domain"] == NEW_DOMAIN
    assert (vault_root / "10_Domains" / NEW_DOMAIN / "Lit - 양자화 서베이.md").is_file()
    assert {d["id"] for d in client.get("/api/domains").json()} == on_disk
    assert set(client.get("/api/settings").json()["domains"]["extra"]) == set(
        load_config(vault_root).domains.extra
    )


def test_f1_settings_save_keeps_domain_added_by_cli(client: TestClient, vault_root: Path) -> None:
    """Trace trace_bug_P2.md: CliAddDomain(d1) -> BrowserGet (stale) -> BrowserPut drops d1."""
    assert client.get("/api/settings").status_code == 200  # Hub has its cache
    _cli_add_domain(vault_root, NEW_DOMAIN)
    current = client.get("/api/settings").json()  # Settings.tsx:17 — spread into the PUT body
    current["level"] = 3
    r = client.put("/api/settings", headers=CLICK, json=current)
    assert r.status_code == 200, r.text
    # P2: a Settings save never removes a Domain from myelin.yaml
    assert NEW_DOMAIN in load_config(vault_root).domains.all_ids, (
        "P2 violated (lost update): Settings save wrote the stale Domain list back"
    )
    assert load_config(vault_root).level == 3
