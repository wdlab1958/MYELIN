"""MYELIN Emboss toolchain — single source `design/tokens.json` (P5).

    python scripts/emboss.py build            # → design/dist/emboss.css, tailwind.preset.cjs, theme/…/theme.css
    python scripts/emboss.py check            # generated files in sync with tokens.json (gate)
    python scripts/emboss.py a11y             # text contrast ≥ 4.5:1 for every a11y.text-pairs; neon-as-text rule
    python scripts/emboss.py lint [paths...]  # no raw colors outside tokens.json / generated :root blocks

Standard library only, so it can run in CI before the Python workspace is synced.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOKENS = ROOT / "design" / "tokens.json"
DIST = ROOT / "design" / "dist"
CSS_OUT = DIST / "emboss.css"
TW_OUT = DIST / "tailwind.preset.cjs"
THEME_OUT = ROOT / "theme" / "obsidian-myelin-emboss" / "theme.css"


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


GENERATED_MARK = "GENERATED from design/tokens.json by scripts/emboss.py — do not edit"

REF_RE = re.compile(r"\{([a-z-]+)\.([a-z0-9-]+)\}")
HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RGB_RE = re.compile(r"\brgba?\(")
NEON_TEXT_RE = re.compile(r"(?<![-\w])color\s*:\s*var\(--mx-(?:neon-)?(lime|cyan|magenta)\)")
LINT_GLOBS = (
    "design/gallery/**/*.html",
    "design/gallery/**/*.css",
    "design/dist/*.css",
    "theme/**/*.css",
    "packages/myelin-hub/web/src/**/*.tsx",
    "packages/myelin-hub/web/src/**/*.css",
)


# ------------------------------------------------------------------------------- tokens
def load_tokens(path: Path = TOKENS) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    for group in ("color", "shadow", "radius", "semantic", "a11y"):
        if group not in data:
            raise SystemExit(f"tokens.json: missing group {group!r}")
    return data


def resolve(data: dict[str, Any], value: str) -> str:
    """Replace `{group.name}` references with the referenced token's value (recursively)."""

    def sub(m: re.Match[str]) -> str:
        group, name = m.group(1), m.group(2)
        try:
            return resolve(data, data[group][name]["value"])
        except KeyError:
            raise SystemExit(f"tokens.json: unresolved reference {{{group}.{name}}}") from None

    return REF_RE.sub(sub, value)


def flat_vars(data: dict[str, Any]) -> list[tuple[str, str]]:
    """CSS custom properties `--mx-<group>-<name>` (color names keep their own names: --mx-ink …)."""
    out: list[tuple[str, str]] = []
    for group in ("color", "shadow", "radius", "space", "font", "motion"):
        for name, tok in data.get(group, {}).items():
            var = f"--mx-{name}" if group == "color" else f"--mx-{group}-{name}"
            out.append((var, resolve(data, tok["value"])))
    out.append(("--mx-focus-ring", resolve(data, data["focus"]["ring"]["value"])))
    out.append(("--mx-focus-offset", data["focus"]["ring"].get("offset", "2px")))
    return out


# ------------------------------------------------------------------------------- generators
def gen_css(data: dict[str, Any]) -> str:
    vars_block = "\n".join(f"  {k}: {v};" for k, v in flat_vars(data))
    return f"""/* {GENERATED_MARK} · v{data["version"]} · 정본 §8.4 */
:root {{
{vars_block}
}}

/* ---- base ---- */
.mx, .mx * {{ box-sizing: border-box; }}
.mx {{ background: var(--mx-surface); color: var(--mx-ink); font-family: var(--mx-font-sans); font-size: var(--mx-font-size-md); line-height: 1.5; }}
.mx a {{ color: var(--mx-violet-600); text-decoration: none; }}
.mx a:focus-visible, .mx button:focus-visible, .mx input:focus-visible, .mx [tabindex]:focus-visible {{ outline: var(--mx-focus-ring); outline-offset: var(--mx-focus-offset); }}
.mx-muted {{ color: var(--mx-muted); }}
.mx-mono {{ font-family: var(--mx-font-mono); }}

/* ---- surfaces (§8.3 Card / KPI Tile) ---- */
.mx-card {{ background: var(--mx-surface); border-radius: var(--mx-radius-card); box-shadow: var(--mx-shadow-raised); padding: var(--mx-space-5); }}
.mx-kpi {{ display: grid; gap: var(--mx-space-2); }}
.mx-kpi__value {{ font-size: var(--mx-font-size-kpi); font-weight: 700; line-height: 1; color: var(--mx-ink); font-variant-numeric: tabular-nums; }}
.mx-kpi__value--verified {{ color: var(--mx-lime-ink); }}
.mx-kpi__value--ai {{ color: var(--mx-cyan-ink); }}
.mx-kpi__value--blocked {{ color: var(--mx-magenta-ink); }}
.mx-kpi__label {{ color: var(--mx-muted); font-size: var(--mx-font-size-sm); }}

/* ---- buttons ---- */
.mx-btn {{ display: inline-flex; align-items: center; gap: var(--mx-space-2); padding: var(--mx-space-3) var(--mx-space-5); border: 1px solid var(--mx-border); border-radius: var(--mx-radius-control); background: var(--mx-surface); color: var(--mx-ink); font: inherit; font-weight: 600; cursor: pointer; box-shadow: var(--mx-shadow-raised-sm); }}
.mx-btn:active, .mx-btn[aria-pressed="true"] {{ box-shadow: var(--mx-shadow-inset); }}
.mx-btn-primary {{ display: inline-flex; align-items: center; gap: var(--mx-space-2); padding: var(--mx-space-3) var(--mx-space-5); border: 0; border-radius: var(--mx-radius-control); background: var(--mx-violet-600); color: var(--mx-on-violet); font: inherit; font-weight: 700; cursor: pointer; box-shadow: var(--mx-shadow-glow-violet); }}
.mx-btn-promote {{ background: var(--mx-neon-lime); color: var(--mx-ink); box-shadow: var(--mx-shadow-raised-sm); border: 1px solid var(--mx-border); }}
.mx-btn[disabled], .mx-btn-primary[disabled] {{ opacity: .5; cursor: not-allowed; }}

/* ---- inputs (inset + 1px border + focus ring) ---- */
.mx-input {{ width: 100%; padding: var(--mx-space-3) var(--mx-space-4); border: 1px solid var(--mx-border); border-radius: var(--mx-radius-control); background: var(--mx-surface); color: var(--mx-ink); font: inherit; box-shadow: var(--mx-shadow-inset); }}
.mx-input::placeholder {{ color: var(--mx-muted); }}
.mx-input:focus {{ outline: var(--mx-focus-ring); outline-offset: var(--mx-focus-offset); }}

/* ---- nav ---- */
.mx-nav {{ display: grid; gap: var(--mx-space-1); }}
.mx-nav-item {{ display: flex; align-items: center; gap: var(--mx-space-3); padding: var(--mx-space-3) var(--mx-space-4); border-radius: var(--mx-radius-control); color: var(--mx-ink); background: transparent; border: 0; font: inherit; text-align: left; cursor: pointer; }}
.mx-nav-item.is-active, .mx-nav-item[aria-current="page"] {{ box-shadow: var(--mx-shadow-inset); color: var(--mx-violet-600); font-weight: 700; }}

/* ---- status chips (§8.2) — always with a text label ---- */
.mx-chip {{ display: inline-flex; align-items: center; gap: var(--mx-space-1); padding: 2px var(--mx-space-3); border-radius: var(--mx-radius-chip); font-size: var(--mx-font-size-xs); font-weight: 700; line-height: 1.6; border: 2px solid transparent; }}
.mx-chip--draft {{ border-color: var(--mx-violet-600); color: var(--mx-violet-600); background: var(--mx-violet-50); }}
.mx-chip--ai {{ background: var(--mx-neon-cyan); color: var(--mx-ink); }}
.mx-chip--verified {{ background: var(--mx-neon-lime); color: var(--mx-ink); }}
.mx-chip--unverified {{ border-color: var(--mx-border); color: var(--mx-muted); }}
.mx-badge--blocked {{ display: inline-flex; align-items: center; gap: var(--mx-space-1); padding: 2px var(--mx-space-3); border-radius: var(--mx-radius-chip); font-size: var(--mx-font-size-xs); font-weight: 700; border: 2px solid var(--mx-neon-magenta); color: var(--mx-magenta-ink); background: var(--mx-magenta-50); }}
.mx-glow--ai {{ box-shadow: var(--mx-shadow-raised), var(--mx-shadow-glow-ai); }}
.mx-ring--verified {{ box-shadow: var(--mx-shadow-raised), var(--mx-shadow-ring-lime); }}
.mx-ring--verified.is-myelinating {{ animation: var(--mx-motion-myelinate); }}
@keyframes myelinate {{ from {{ box-shadow: var(--mx-shadow-raised), 0 0 0 0 var(--mx-neon-lime); }} to {{ box-shadow: var(--mx-shadow-raised), var(--mx-shadow-ring-lime); }} }}

/* ---- Domain Orb ---- */
.mx-orb {{ width: 72px; height: 72px; border-radius: 50%; display: grid; place-items: center; background: var(--mx-surface); box-shadow: var(--mx-shadow-raised-sm); border: 3px solid var(--mx-border); font-weight: 800; color: var(--mx-ink); cursor: pointer; }}
.mx-orb[data-accent="violet"] {{ border-color: var(--mx-violet-600); box-shadow: var(--mx-shadow-raised-sm), 0 0 24px var(--mx-violet-50); }}
.mx-orb[data-accent="lime"] {{ border-color: var(--mx-neon-lime); box-shadow: var(--mx-shadow-raised-sm), 0 0 24px var(--mx-neon-lime); }}
.mx-orb[data-accent="cyan"] {{ border-color: var(--mx-neon-cyan); box-shadow: var(--mx-shadow-raised-sm), 0 0 24px var(--mx-neon-cyan); }}
.mx-orb[data-accent="magenta"] {{ border-color: var(--mx-neon-magenta); box-shadow: var(--mx-shadow-raised-sm), 0 0 24px var(--mx-neon-magenta); }}

/* ---- Review Row ---- */
.mx-review-row {{ display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: var(--mx-space-4); padding: var(--mx-space-3) var(--mx-space-4); border-bottom: 1px solid var(--mx-border); }}
.mx-review-row__title {{ font-weight: 600; }}
.mx-review-row__meta {{ color: var(--mx-muted); font-size: var(--mx-font-size-sm); }}

/* ---- table ---- */
.mx-table {{ width: 100%; border-collapse: collapse; }}
.mx-table th {{ text-align: left; background: var(--mx-surface-2); color: var(--mx-muted); font-size: var(--mx-font-size-sm); padding: var(--mx-space-2) var(--mx-space-3); }}
.mx-table td {{ padding: var(--mx-space-2) var(--mx-space-3); border-bottom: 1px solid var(--mx-border); }}
"""


def gen_tailwind(data: dict[str, Any]) -> str:
    colors = {name: f"var(--mx-{name})" for name in data["color"]}
    shadows = {name: f"var(--mx-shadow-{name})" for name in data["shadow"]}
    radius = {name: f"var(--mx-radius-{name})" for name in data["radius"]}
    spacing = {name: f"var(--mx-space-{name})" for name in data.get("space", {})}
    fonts = {
        "sans": ["var(--mx-font-sans)"],
        "mono": ["var(--mx-font-mono)"],
    }
    preset = {
        "theme": {
            "extend": {
                "colors": {"mx": colors},
                "boxShadow": {f"mx-{k}": v for k, v in shadows.items()},
                "borderRadius": {f"mx-{k}": v for k, v in radius.items()},
                "spacing": {f"mx-{k}": v for k, v in spacing.items()},
                "fontFamily": fonts,
            }
        }
    }
    body = json.dumps(preset, indent=2, ensure_ascii=False)
    return (
        f"// {GENERATED_MARK} · v{data['version']}\n"
        "// Tailwind preset: every value is a CSS variable from emboss.css, so no color is ever hard-coded in TSX.\n"
        f"module.exports = {body};\n"
    )


def gen_theme(data: dict[str, Any]) -> str:
    vars_block = "\n".join(f"  {k}: {v};" for k, v in flat_vars(data))
    return f"""/* {GENERATED_MARK} · v{data["version"]}
   MYELIN Emboss — Obsidian theme (light only; dark is out of scope for v1.0, §8.3 guardrail 5). */
.theme-light, .theme-dark {{
{vars_block}
  --background-primary: var(--mx-surface);
  --background-primary-alt: var(--mx-surface-2);
  --background-secondary: var(--mx-surface);
  --background-secondary-alt: var(--mx-surface-2);
  --background-modifier-border: var(--mx-border);
  --text-normal: var(--mx-ink);
  --text-muted: var(--mx-muted);
  --text-faint: var(--mx-muted);
  --text-accent: var(--mx-violet-600);
  --text-accent-hover: var(--mx-violet-600);
  --text-on-accent: var(--mx-on-violet);
  --interactive-accent: var(--mx-violet-600);
  --interactive-accent-hover: var(--mx-violet-600);
  --link-color: var(--mx-violet-600);
  --tag-background: var(--mx-violet-50);
  --tag-color: var(--mx-violet-600);
  --font-text: var(--mx-font-sans);
  --font-monospace: var(--mx-font-mono);
  --radius-s: var(--mx-radius-control);
  --radius-m: var(--mx-radius-control);
  --radius-l: var(--mx-radius-card);
  --shadow-s: var(--mx-shadow-raised-sm);
  --shadow-l: var(--mx-shadow-raised);
}}
/* status identity (frontmatter via cssclasses or Dataview) — §8.2 */
.theme-light .mx-status-verified, .theme-dark .mx-status-verified {{ box-shadow: var(--mx-shadow-ring-lime); }}
.theme-light .mx-status-ai-draft, .theme-dark .mx-status-ai-draft {{ box-shadow: var(--mx-shadow-glow-ai); }}
/* emboss surfaces for cards/callouts */
.theme-light .callout, .theme-dark .callout {{ background: var(--mx-surface); border-radius: var(--mx-radius-control); box-shadow: var(--mx-shadow-raised-sm); border: 1px solid var(--mx-border); }}
.theme-light .markdown-source-view.mod-cm6 .cm-content, .theme-dark .markdown-source-view.mod-cm6 .cm-content {{ caret-color: var(--mx-violet-600); }}
.theme-light input[type="text"], .theme-light input[type="search"], .theme-dark input[type="text"], .theme-dark input[type="search"] {{ box-shadow: var(--mx-shadow-inset); border: 1px solid var(--mx-border); border-radius: var(--mx-radius-control); }}
.theme-light input:focus-visible, .theme-dark input:focus-visible {{ outline: var(--mx-focus-ring); outline-offset: var(--mx-focus-offset); }}
"""


OUTPUTS: dict[Path, Any] = {CSS_OUT: gen_css, TW_OUT: gen_tailwind, THEME_OUT: gen_theme}


def build(data: dict[str, Any]) -> list[Path]:
    written = []
    for path, fn in OUTPUTS.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(fn(data), encoding="utf-8")
        written.append(path)
    return written


def check(data: dict[str, Any]) -> list[str]:
    stale = []
    for path, fn in OUTPUTS.items():
        if not path.exists() or path.read_text(encoding="utf-8") != fn(data):
            stale.append(str(path.relative_to(ROOT)))
    return stale


# ------------------------------------------------------------------------------- a11y
def _hex(data: dict[str, Any], ref: str) -> str:
    group, name = ref.split(".", 1)
    tok = data[group][name]
    value = str(tok.get("hex") or tok["value"])
    if not value.startswith("#"):
        raise SystemExit(
            f"{ref}: contrast needs an opaque hex value (got {value!r}); add a `hex` field"
        )
    return value


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(fg: str, bg: str) -> float:
    lf, lb = luminance(fg), luminance(bg)
    hi, lo = max(lf, lb), min(lf, lb)
    return (hi + 0.05) / (lo + 0.05)


def a11y(data: dict[str, Any], files: list[Path] | None = None) -> list[str]:
    """Return a list of violations (empty = pass)."""
    problems: list[str] = []
    minimum = float(data["a11y"]["min-text-contrast"])
    for pair in data["a11y"]["text-pairs"]:
        fg, bg = _hex(data, pair["fg"]), _hex(data, pair["bg"])
        ratio = contrast(fg, bg)
        line = f"{pair['fg']} on {pair['bg']} ({pair.get('use', '')}): {ratio:.2f}:1"
        if ratio < minimum:
            problems.append(f"CONTRAST {line} < {minimum}")
        else:
            print(f"ok   {line}")
    # neon-as-text rule: generated CSS / gallery / hub must never use a neon token as `color:`
    for f in files if files is not None else _lint_files():
        for n, raw in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if NEON_TEXT_RE.search(raw):
                problems.append(f"NEON-AS-TEXT {_rel(f)}:{n}: {raw.strip()}")
    return problems


# ------------------------------------------------------------------------------- lint
def _lint_files(paths: list[str] | None = None) -> list[Path]:
    globs = paths or list(LINT_GLOBS)
    files: list[Path] = []
    for g in globs:
        p = ROOT / g
        if p.is_file():
            files.append(p)
        else:
            files.extend(sorted(x for x in ROOT.glob(g) if x.is_file()))
    return files


def lint(paths: list[str] | None = None) -> list[str]:
    """Raw colors (#hex / rgb()) are allowed only inside the generated `:root`/theme var block."""
    problems: list[str] = []
    for f in _lint_files(paths):
        text = f.read_text(encoding="utf-8")
        generated = GENERATED_MARK in text
        in_var_block = False
        for n, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if generated and (
                line.startswith(":root {") or line.startswith(".theme-light, .theme-dark {")
            ):
                in_var_block = True
                continue
            if in_var_block and line == "}":
                in_var_block = False
                continue
            if in_var_block and line.startswith("--mx-"):
                continue  # token definitions are the one place a literal is allowed
            if HEX_RE.search(raw) or RGB_RE.search(raw):
                if "<!-- token-literal-ok -->" in raw or "/* token-literal-ok */" in raw:
                    continue
                problems.append(f"{_rel(f)}:{n}: raw color literal — use var(--mx-*): {line[:90]}")
    return problems


# ------------------------------------------------------------------------------- cli
def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in ("build", "check", "a11y", "lint"):
        print(__doc__)
        return 2
    cmd = argv[1]
    data = load_tokens()
    if cmd == "build":
        for written in build(data):
            print(f"wrote {written.relative_to(ROOT)}")
        return 0
    if cmd == "check":
        stale = check(data)
        if stale:
            print(f"STALE generated files: {stale} — run `make emboss`", file=sys.stderr)
            return 1
        print(f"{len(OUTPUTS)} generated files in sync with design/tokens.json v{data['version']}")
        return 0
    if cmd == "a11y":
        problems = a11y(data)
        for msg in problems:
            print(f"FAIL {msg}", file=sys.stderr)
        if not problems:
            print(
                f"a11y: {len(data['a11y']['text-pairs'])} text pairs ≥ {data['a11y']['min-text-contrast']}:1, no neon-as-text"
            )
        return 1 if problems else 0
    problems = lint(argv[2:] or None)
    for msg in problems:
        print(f"FAIL {msg}", file=sys.stderr)
    if not problems:
        print(f"lint: 0 raw color literals in {len(_lint_files(argv[2:] or None))} files")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
