"""P9-T8 — Obsidian Graph View config: tokens → colour groups, merge-never-overwrite, status."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from myelin_core.obsidian import (
    APP_FILE,
    CORE_PLUGINS_FILE,
    GRAPH_FILE,
    ensure_obsidian_config,
    graph_color_groups,
    graph_uri,
    is_registered,
    obsidian_status,
    open_uri,
    render_graph,
    token_colors,
)

DOMAINS = [("D1", "violet"), ("D2", "cyan"), ("D3", "lime"), ("D4", "magenta")]


def test_token_colors_come_from_design_tokens() -> None:
    colors = token_colors()
    assert colors["violet-600"] == "#7C3AED" and colors["neon-cyan"] == "#22E4FF"
    assert token_colors(Path("/nonexistent/tokens.json")) == {}


def test_graph_groups_one_per_domain_in_emboss_accent() -> None:
    groups = graph_color_groups(DOMAINS)
    queries = [g["query"] for g in groups]
    assert queries[:4] == [f"path:10_Domains/D{i}/" for i in (1, 2, 3, 4)]
    assert groups[0]["color"] == {"a": 1, "rgb": 0x7C3AED}  # violet-600
    assert groups[1]["color"]["rgb"] == 0x22E4FF and groups[3]["color"]["rgb"] == 0xFF3DCB
    assert {"path:00_Inbox/", "path:40_IP/", "path:99_Archive/"} <= set(queries)
    # unknown accent / missing token → no invented colour
    assert graph_color_groups([("DX", "plaid")], {"violet-600": "#7C3AED"}) == []


def test_render_graph_is_valid_obsidian_json() -> None:
    data = json.loads(render_graph(DOMAINS[:1]))
    assert data["showTags"] is True and data["hideUnresolved"] is True
    assert data["colorGroups"][0]["query"] == "path:10_Domains/D1/"


def test_ensure_writes_three_files_when_missing(tmp_path: Path) -> None:
    touched = ensure_obsidian_config(tmp_path, DOMAINS)
    assert touched == [CORE_PLUGINS_FILE, GRAPH_FILE, APP_FILE]
    plugins = json.loads((tmp_path / CORE_PLUGINS_FILE).read_text(encoding="utf-8"))
    assert plugins["graph"] and plugins["backlink"] and plugins["outgoing-link"]
    assert plugins["sync"] is False and plugins["daily-notes"] is False
    app = json.loads((tmp_path / APP_FILE).read_text(encoding="utf-8"))
    assert app["newFileFolderPath"] == "00_Inbox" and app["useMarkdownLinks"] is False
    # idempotent
    assert ensure_obsidian_config(tmp_path, DOMAINS) == []


def test_ensure_merges_into_existing_user_config(tmp_path: Path) -> None:
    ob = tmp_path / ".obsidian"
    ob.mkdir()
    (ob / "core-plugins.json").write_text(
        json.dumps({"file-explorer": True, "graph": False, "canvas": True}), encoding="utf-8"
    )
    mine = {"query": "tag:#refeed", "color": {"a": 1, "rgb": 1}}
    (ob / "graph.json").write_text(
        json.dumps(
            {
                "search": "-path:99_Archive",
                "repelStrength": 17,
                "colorGroups": [
                    mine,
                    {"query": "path:10_Domains/D1/", "color": {"a": 1, "rgb": 2}},
                ],
            }
        ),
        encoding="utf-8",
    )
    (ob / "app.json").write_text('{"useMarkdownLinks": true}', encoding="utf-8")
    touched = ensure_obsidian_config(tmp_path, DOMAINS)
    assert touched == [CORE_PLUGINS_FILE, GRAPH_FILE]  # app.json is the user's
    plugins = json.loads((ob / "core-plugins.json").read_text(encoding="utf-8"))
    assert plugins == {
        "file-explorer": True,
        "graph": True,
        "canvas": True,
        "backlink": True,
        "outgoing-link": True,
    }
    graph = json.loads((ob / "graph.json").read_text(encoding="utf-8"))
    assert graph["search"] == "-path:99_Archive" and graph["repelStrength"] == 17  # kept
    queries = [g["query"] for g in graph["colorGroups"]]
    assert queries[:2] == ["tag:#refeed", "path:10_Domains/D1/"]  # user's first, D1 colour kept
    assert graph["colorGroups"][1]["color"]["rgb"] == 2
    assert {"path:10_Domains/D2/", "path:10_Domains/D3/", "path:10_Domains/D4/"} <= set(queries)
    assert json.loads((ob / "app.json").read_text(encoding="utf-8")) == {"useMarkdownLinks": True}


def test_ensure_is_fail_closed_on_unreadable_json(tmp_path: Path) -> None:
    ob = tmp_path / ".obsidian"
    ob.mkdir()
    (ob / "graph.json").write_text("{not json", encoding="utf-8")
    (ob / "core-plugins.json").write_text("[]", encoding="utf-8")  # wrong shape
    with pytest.raises(ValueError):
        ensure_obsidian_config(tmp_path, DOMAINS)
    assert not (ob / "app.json").exists()  # nothing else was written either
    st = obsidian_status(tmp_path, DOMAINS)
    assert st["ready"] is False and st["error"]


def test_status_and_uris(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "My Vault"
    root.mkdir()
    st = obsidian_status(root, DOMAINS)
    assert st["graph_enabled"] is False and st["domains_without_group"] == [d for d, _ in DOMAINS]
    ensure_obsidian_config(root, DOMAINS)
    appearance = root / ".obsidian/appearance.json"
    appearance.write_text('{"cssTheme": "MYELIN Emboss"}', encoding="utf-8")
    st = obsidian_status(root, DOMAINS)
    assert st["ready"] and st["theme"] == "MYELIN Emboss" and st["vault_name"] == "My Vault"
    encoded = str(root.resolve()).replace("/", "%2F").replace(" ", "%20")
    assert st["open_url"] == "obsidian://open?path=" + encoded
    assert st["graph_url"] == st["open_url"] and st["advanced_uri"] is False
    (root / ".obsidian/plugins/obsidian-advanced-uri").mkdir(parents=True)
    assert graph_uri(root) == "obsidian://advanced-uri?vault=My%20Vault&commandid=graph%3Aopen"
    assert open_uri(root).startswith("obsidian://open?path=")
    # registration: read from Obsidian's own vault list
    reg = tmp_path / "obsidian.json"
    monkeypatch.setattr("myelin_core.obsidian.obsidian_registry_file", lambda: reg)
    assert is_registered(root) is None  # file missing → unknown
    reg.write_text(json.dumps({"vaults": {"ab": {"path": str(root)}}}), encoding="utf-8")
    assert is_registered(root) is True and is_registered(tmp_path / "other") is False
    reg.write_text("junk", encoding="utf-8")
    assert is_registered(root) is None


def test_init_and_add_domain_keep_graph_in_sync(tmp_path: Path, packs_dir: Path) -> None:
    from myelin_core.config import MyelinConfig
    from myelin_core.scaffold import add_domain, init_vault
    from myelin_core.vault import Vault

    cfg = MyelinConfig.model_validate(
        {
            "owner": {"name": "T", "team": "t", "email": "t@example.org"},
            "packs": ["myelin.core", "brian.physical-ai"],
            "domains": {"primary": "D1", "research": "D2", "growth": "D3"},
            "level": 1,
        }
    )
    root = tmp_path / "v"
    init_vault(root, cfg, datetime(2026, 10, 27, 9, 0), pack_roots=[packs_dir])
    graph = json.loads((root / GRAPH_FILE).read_text(encoding="utf-8"))
    queries = [g["query"] for g in graph["colorGroups"]]
    assert queries[:3] == ["path:10_Domains/D1/", "path:10_Domains/D2/", "path:10_Domains/D3/"]
    graph["repelStrength"] = 3  # user tweak survives add-domain
    (root / GRAPH_FILE).write_text(json.dumps(graph), encoding="utf-8")
    touched = add_domain(
        Vault.open(root), "D4", datetime(2026, 10, 27, 9, 1), pack_roots=[packs_dir]
    )
    assert GRAPH_FILE in touched and CORE_PLUGINS_FILE not in touched
    graph = json.loads((root / GRAPH_FILE).read_text(encoding="utf-8"))
    assert graph["repelStrength"] == 3
    d4 = [g for g in graph["colorGroups"] if g["query"] == "path:10_Domains/D4/"]
    assert len(d4) == 1 and d4[0]["color"]["rgb"] == 0xFF3DCB  # magenta, appended once
