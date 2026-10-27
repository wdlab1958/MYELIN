"""Obsidian workspace configuration for a MYELIN Vault — Graph View on, Domain colour groups.

MYELIN's Obsidian integration is "theme + file conventions", not a plugin (정본 §4.1 L4). This
module adds the third piece: the `.obsidian/*.json` files Obsidian reads on first open, so a
Vault shows its link graph without any manual step —

- `core-plugins.json`  Graph View, backlinks, outgoing links, tags, properties … enabled
- `graph.json`         one colour group per Domain (`path:10_Domains/<ID>/`) using the Emboss
                       accent of that Domain from `design/tokens.json` (single colour source),
                       plus Inbox / 40_IP / Archive groups
- `app.json`           new notes land in 00_Inbox, wikilinks stay `[[stem]]` (index contract)

Rules: never overwrite a file the user already has — existing JSON is *merged* (missing colour
groups appended, Graph View switched on), everything else is kept. Unreadable JSON is left alone
(fail-closed: we do not guess at a user's settings).
"""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any
from urllib.parse import quote

from myelin_core.vault import ARCHIVE, DOMAINS, INBOX, IP, OBSIDIAN_DIR, RESOURCES

CORE_PLUGINS_FILE = f"{OBSIDIAN_DIR}/core-plugins.json"
GRAPH_FILE = f"{OBSIDIAN_DIR}/graph.json"
APP_FILE = f"{OBSIDIAN_DIR}/app.json"
APPEARANCE_FILE = f"{OBSIDIAN_DIR}/appearance.json"
ADVANCED_URI_DIR = f"{OBSIDIAN_DIR}/plugins/obsidian-advanced-uri"

# Core plugins a MYELIN Vault relies on. Graph View is the point; backlink/outgoing-link show the
# same graph per note; properties renders Frontmatter v2; templates reads 90_System/templates.
# daily-notes stays off (50_Journal is MYELIN's); sync/publish off (정본 §4.4: the Vault stays
# local).
CORE_PLUGINS: dict[str, bool] = {
    "file-explorer": True,
    "global-search": True,
    "switcher": True,
    "graph": True,
    "backlink": True,
    "canvas": False,
    "outgoing-link": True,
    "tag-pane": True,
    "footnotes": False,
    "properties": True,
    "page-preview": True,
    "daily-notes": False,
    "templates": True,
    "note-composer": True,
    "command-palette": True,
    "slash-command": False,
    "editor-status": True,
    "bookmarks": True,
    "zk-prefixer": False,
    "random-note": False,
    "outline": True,
    "word-count": True,
    "slides": False,
    "audio-recorder": False,
    "workspaces": False,
    "file-recovery": True,
    "publish": False,
    "sync": False,
    "bases": False,
    "webviewer": False,
}
GRAPH_REQUIRED: tuple[str, ...] = ("graph", "backlink", "outgoing-link")

# Domain accent (Pack `accent`) → tokens.json colour name. Same mapping the Hub Orbs use.
ACCENT_TOKEN: dict[str, str] = {
    "violet": "violet-600",
    "cyan": "neon-cyan",
    "lime": "neon-lime",
    "magenta": "neon-magenta",
}
# Fixed groups after the Domains: (graph query, token). Order matters — Obsidian applies the
# first matching group, so Domain folders come first and these catch the rest.
FIXED_GROUPS: tuple[tuple[str, str], ...] = (
    (f"path:{INBOX}/", "muted"),
    (f"path:{IP}/", "magenta-ink"),
    (f"path:{ARCHIVE}/", "border"),
)

APP_SETTINGS: dict[str, Any] = {
    "newFileLocation": "folder",
    "newFileFolderPath": INBOX,
    "attachmentFolderPath": f"{RESOURCES}/attachments",
    "useMarkdownLinks": False,  # [[wikilinks]] — what the index and doctor resolve
    "newLinkFormat": "shortest",  # [[stem]] links (정본 §6; Level 2 link-patch convention)
    "alwaysUpdateLinks": True,
    "showUnsupportedFiles": False,
}

GRAPH_DEFAULTS: dict[str, Any] = {
    "collapse-filter": False,
    "search": "",
    "showTags": True,
    "showAttachments": False,
    "hideUnresolved": True,  # Sub-MOC placeholders ([[D1 - …]]) are not notes yet
    "showOrphans": True,
    "collapse-color-groups": False,
    "colorGroups": [],
    "collapse-display": False,
    "showArrow": True,
    "textFadeMultiplier": 0,
    "nodeSizeMultiplier": 1,
    "lineSizeMultiplier": 1,
    "collapse-forces": False,
    "centerStrength": 0.5,
    "repelStrength": 10,
    "linkStrength": 1,
    "linkDistance": 250,
    "scale": 1,
    "close": True,
}


# ------------------------------------------------------------------------------ colour source
def default_tokens_file() -> Path | None:
    """`design/tokens.json`: $MYELIN_TOKENS or the repo checkout this package lives in."""
    env = os.environ.get("MYELIN_TOKENS")
    if env and Path(env).is_file():
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "design" / "tokens.json"
        if cand.is_file():
            return cand
    return None


def token_colors(tokens_file: Path | None = None) -> dict[str, str]:
    """{token name: '#RRGGBB'} from tokens.json `color`; {} when the file is missing/unreadable."""
    f = tokens_file or default_tokens_file()
    if f is None:
        return {}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        colors = data["color"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    out: dict[str, str] = {}
    for name, spec in colors.items():
        value = spec.get("value") if isinstance(spec, dict) else spec
        if isinstance(value, str) and value.startswith("#") and len(value) == 7:
            out[name] = value.upper()
    return out


def _rgb_int(hex_color: str) -> int:
    return int(hex_color.lstrip("#"), 16)


def domain_query(domain_id: str) -> str:
    return f"path:{DOMAINS}/{domain_id}/"


def graph_color_groups(
    domains: list[tuple[str, str]], colors: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    """Obsidian colour groups for (domain id, accent) pairs + fixed folders. Domains whose accent
    has no colour in tokens.json get no group (never invent a colour)."""
    colors = token_colors() if colors is None else colors
    groups: list[dict[str, Any]] = []
    for did, accent in domains:
        hex_color = colors.get(ACCENT_TOKEN.get(accent, ""))
        if hex_color:
            groups.append(
                {"query": domain_query(did), "color": {"a": 1, "rgb": _rgb_int(hex_color)}}
            )
    for query, token in FIXED_GROUPS:
        hex_color = colors.get(token)
        if hex_color:
            groups.append({"query": query, "color": {"a": 1, "rgb": _rgb_int(hex_color)}})
    return groups


# ------------------------------------------------------------------------------ renderers
def _dump(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def render_core_plugins() -> str:
    return _dump(CORE_PLUGINS)


def render_graph(domains: list[tuple[str, str]], colors: dict[str, str] | None = None) -> str:
    return _dump({**GRAPH_DEFAULTS, "colorGroups": graph_color_groups(domains, colors)})


def render_app() -> str:
    return _dump(APP_SETTINGS)


def obsidian_config_files(domains: list[tuple[str, str]]) -> dict[str, str]:
    """The three config files for a fresh Vault (relative path → content)."""
    return {
        CORE_PLUGINS_FILE: render_core_plugins(),
        GRAPH_FILE: render_graph(domains),
        APP_FILE: render_app(),
    }


# ---------------------------------------------------------------------- merge (existing Vault)
def _load_json(path: Path) -> dict[str, Any] | None:
    """Parsed object, or None when the file is missing. Raises ValueError on unreadable JSON."""
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: expected a JSON object")
    return data


def ensure_obsidian_config(root: Path, domains: list[tuple[str, str]]) -> list[str]:
    """Make an existing Vault's Obsidian config Graph-View-ready. Returns the touched paths.

    - missing file → written whole
    - core-plugins.json present → only `graph`/`backlink`/`outgoing-link` switched on
    - graph.json present → colour groups for Domains/folders that have none are appended;
      every other setting (forces, filters, the user's own groups) is kept
    - app.json present → left untouched
    Unreadable JSON raises ValueError and nothing is written (fail-closed).
    """
    root = Path(root)
    touched: list[str] = []
    (root / OBSIDIAN_DIR).mkdir(parents=True, exist_ok=True)

    plugins_path = root / CORE_PLUGINS_FILE
    plugins = _load_json(plugins_path)
    if plugins is None:
        plugins_path.write_text(render_core_plugins(), encoding="utf-8")
        touched.append(CORE_PLUGINS_FILE)
    elif any(not plugins.get(k) for k in GRAPH_REQUIRED):
        for k in GRAPH_REQUIRED:
            plugins[k] = True
        plugins_path.write_text(_dump(plugins), encoding="utf-8")
        touched.append(CORE_PLUGINS_FILE)

    graph_path = root / GRAPH_FILE
    graph = _load_json(graph_path)
    if graph is None:
        graph_path.write_text(render_graph(domains), encoding="utf-8")
        touched.append(GRAPH_FILE)
    else:
        existing = graph.get("colorGroups")
        groups: list[dict[str, Any]] = list(existing) if isinstance(existing, list) else []
        have = {g.get("query") for g in groups if isinstance(g, dict)}
        missing = [g for g in graph_color_groups(domains) if g["query"] not in have]
        if missing:
            graph["colorGroups"] = groups + missing
            graph_path.write_text(_dump(graph), encoding="utf-8")
            touched.append(GRAPH_FILE)

    app_path = root / APP_FILE
    if not app_path.exists():
        app_path.write_text(render_app(), encoding="utf-8")
        touched.append(APP_FILE)
    return touched


# ------------------------------------------------------------------------------ status (CLI · Hub)
def obsidian_registry_file() -> Path | None:
    """Obsidian's own vault list (`obsidian.json`) for this OS, if it exists."""
    system = platform.system()
    cand: Path | None
    if system == "Darwin":
        cand = Path.home() / "Library/Application Support/obsidian/obsidian.json"
    elif system == "Windows":
        appdata = os.environ.get("APPDATA")
        cand = Path(appdata) / "obsidian/obsidian.json" if appdata else None
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        cand = Path(xdg) / "obsidian/obsidian.json"
        if cand is not None and not cand.is_file():  # flatpak / snap installs keep their own HOME
            for alt in (
                Path.home() / ".var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json",
                Path.home() / "snap/obsidian/current/.config/obsidian/obsidian.json",
            ):
                if alt.is_file():
                    cand = alt
                    break
    return cand if cand is not None and cand.is_file() else None


def is_registered(root: Path) -> bool | None:
    """True/False when Obsidian's vault list is readable; None when it is not (no Obsidian)."""
    reg = obsidian_registry_file()
    if reg is None:
        return None
    try:
        data = json.loads(reg.read_text(encoding="utf-8"))
        vaults = data.get("vaults", {})
    except (OSError, ValueError, AttributeError):
        return None
    want = Path(root).resolve()
    for entry in vaults.values():
        try:
            if Path(entry["path"]).resolve() == want:
                return True
        except (KeyError, TypeError, OSError):
            continue
    return False


def open_uri(root: Path) -> str:
    """`obsidian://open?path=<Vault>` — opens the Vault; Obsidian registers it if unknown."""
    return f"obsidian://open?path={quote(str(Path(root).resolve()), safe='')}"


def graph_uri(root: Path) -> str:
    """Deep link to Graph View when the Advanced URI community plugin is installed; otherwise the
    Vault itself (Graph View is then one keystroke away: Ctrl/Cmd+G)."""
    root = Path(root).resolve()
    if (root / ADVANCED_URI_DIR).is_dir():
        return f"obsidian://advanced-uri?vault={quote(root.name, safe='')}&commandid=graph%3Aopen"
    return open_uri(root)


def obsidian_status(root: Path, domains: list[tuple[str, str]]) -> dict[str, Any]:
    """What the Hub/CLI show: is Graph View on, which Domains have a colour group, is the Vault
    known to Obsidian, which URI opens the graph."""
    root = Path(root).resolve()
    plugins = graph = appearance = None
    error: str | None = None
    try:
        plugins = _load_json(root / CORE_PLUGINS_FILE)
        graph = _load_json(root / GRAPH_FILE)
        appearance = _load_json(root / APPEARANCE_FILE)
    except ValueError as exc:
        error = str(exc)
    groups = graph.get("colorGroups", []) if isinstance(graph, dict) else []
    queries = {g.get("query") for g in groups if isinstance(g, dict)}
    missing = [did for did, _ in domains if domain_query(did) not in queries]
    graph_on = bool(plugins) and all(bool(plugins.get(k)) for k in GRAPH_REQUIRED)  # type: ignore[union-attr]
    return {
        "root": str(root),
        "vault_name": root.name,
        "config_dir": bool((root / OBSIDIAN_DIR).is_dir()),
        "graph_enabled": graph_on,
        "color_groups": len(groups),
        "domains_without_group": missing,
        "theme": appearance.get("cssTheme") if isinstance(appearance, dict) else None,
        "ready": graph_on and not missing and error is None,
        "registered": is_registered(root),
        "advanced_uri": (root / ADVANCED_URI_DIR).is_dir(),
        "open_url": open_uri(root),
        "graph_url": graph_uri(root),
        "error": error,
    }
