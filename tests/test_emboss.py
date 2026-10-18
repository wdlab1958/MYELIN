"""P5 — Emboss toolchain: tokens schema, generated files in sync, contrast ≥ 4.5, no raw colors."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import emboss  # type: ignore[import-not-found]  # noqa: E402


@pytest.fixture(scope="module")
def tokens() -> dict[str, Any]:
    data: dict[str, Any] = emboss.load_tokens()
    return data


def test_tokens_match_schema(tokens: dict[str, Any]) -> None:
    """Structural check against design/tokens.schema.json (no jsonschema dependency)."""
    schema = json.loads((ROOT / "design/tokens.schema.json").read_text(encoding="utf-8"))
    for req in schema["required"]:
        assert req in tokens, req
    assert set(tokens) <= set(schema["properties"]), set(tokens) - set(schema["properties"])
    color_pat = re.compile(schema["$defs"]["colorToken"]["properties"]["value"]["pattern"])
    for name, tok in tokens["color"].items():
        assert color_pat.match(tok["value"]), (name, tok["value"])
        assert set(tok) <= {"value", "hex", "spec", "role"}, name
    assert re.match(r"^\d+\.\d+\.\d+$", tokens["version"])
    assert tokens["a11y"]["neon-as-text"] is False and tokens["a11y"]["min-text-contrast"] >= 4.5


def test_spec_values_preserved_or_recorded(tokens: dict[str, Any]) -> None:
    """정본 §8.1 values are used verbatim or kept in `spec` beside the adjusted value (ADR-0008)."""
    spec = {
        "surface": "#EEF0F6",
        "shadow-light": "#FFFFFF",
        "ink": "#2D2A3E",
        "muted": "#6B6F85",
        "violet-600": "#7C3AED",
        "violet-50": "#F3F0FF",
        "neon-lime": "#B6FF3B",
        "lime-ink": "#4D7C0F",
        "neon-cyan": "#22E4FF",
        "cyan-ink": "#0891B2",
        "neon-magenta": "#FF3DCB",
    }
    for name, value in spec.items():
        tok = tokens["color"][name]
        assert tok["value"].upper() == value or tok.get("spec", "").upper() == value, (name, tok)
    assert tokens["radius"] == {
        "card": {"value": "28px"},
        "control": {"value": "20px"},
        "chip": {"value": "999px"},
    }
    assert emboss.resolve(tokens, tokens["shadow"]["raised"]["value"]).startswith(
        "12px 12px 24px rgba(163,177,198"
    )


def test_references_resolve_and_vars_prefixed(tokens: dict[str, Any]) -> None:
    for group in ("shadow", "focus", "motion"):
        for tok in tokens[group].values():
            assert "{" not in emboss.resolve(tokens, tok["value"])
    names = [k for k, _ in emboss.flat_vars(tokens)]
    assert all(n.startswith("--mx-") for n in names) and len(names) == len(set(names))
    assert {
        "--mx-surface",
        "--mx-ink",
        "--mx-shadow-raised",
        "--mx-shadow-inset",
        "--mx-radius-card",
    } <= set(names)


def test_generated_outputs_in_sync(tokens: dict[str, Any]) -> None:
    assert emboss.check(tokens) == [], "run `make emboss`"
    css = (ROOT / "design/dist/emboss.css").read_text(encoding="utf-8")
    assert emboss.GENERATED_MARK in css and ":root {" in css
    for cls in (
        ".mx-card",
        ".mx-btn-primary",
        ".mx-btn",
        ".mx-input",
        ".mx-nav-item",
        ".mx-chip--verified",
        ".mx-chip--ai",
        ".mx-badge--blocked",
        ".mx-orb",
        ".mx-review-row",
        ".mx-glow--ai",
    ):
        assert cls in css, cls
    tw = (ROOT / "design/dist/tailwind.preset.cjs").read_text(encoding="utf-8")
    assert '"mx-raised": "var(--mx-shadow-raised)"' in tw and '"surface": "var(--mx-surface)"' in tw
    theme = (ROOT / "theme/obsidian-myelin-emboss/theme.css").read_text(encoding="utf-8")
    assert (
        "--background-primary: var(--mx-surface)" in theme
        and "--text-accent: var(--mx-violet-600)" in theme
    )
    manifest = json.loads(
        (ROOT / "theme/obsidian-myelin-emboss/manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["name"] == "MYELIN Emboss"


def test_contrast_all_pairs(tokens: dict[str, Any]) -> None:
    problems = emboss.a11y(tokens, files=[])
    assert problems == []
    assert emboss.contrast("#000000", "#FFFFFF") == pytest.approx(21.0, abs=0.01)
    assert emboss.contrast("#6B6F85", "#EEF0F6") < 4.5  # the spec value that ADR-0008 replaced
    assert (
        emboss.contrast(tokens["color"]["muted"]["value"], tokens["color"]["surface"]["value"])
        >= 4.5
    )


def test_neon_as_text_detected(tmp_path: Path, tokens: dict[str, Any]) -> None:
    bad = tmp_path / "bad.css"
    bad.write_text(
        ".x { color: var(--mx-neon-lime); }\n.y { background: var(--mx-neon-lime); }\n",
        encoding="utf-8",
    )
    problems = emboss.a11y(tokens, files=[bad])
    assert len(problems) == 1 and "NEON-AS-TEXT" in problems[0] and "bad.css:1" in problems[0]


def test_lint_no_raw_colors_in_ui() -> None:
    assert emboss.lint() == []


def test_lint_flags_literals(tmp_path: Path) -> None:
    f = tmp_path / "x.css"
    f.write_text(
        ".a { color: #123456; }\n.b { background: rgb(1,2,3); }\n.c { color: var(--mx-ink); }\n",
        encoding="utf-8",
    )
    problems = emboss.lint([str(f)])
    assert len(problems) == 2
    g = tmp_path / "gen.css"
    g.write_text(
        f"/* {emboss.GENERATED_MARK} */\n:root {{\n  --mx-ink: #2D2A3E;\n}}\n"
        ".a { color: #fff; }\n",
        encoding="utf-8",
    )
    problems = emboss.lint([str(g)])
    assert len(problems) == 1 and "gen.css:5" in problems[0]


def test_gallery_uses_only_tokens_and_labels_states() -> None:
    html = (ROOT / "design/gallery/index.html").read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="../dist/emboss.css">' in html
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", re.sub(r'href="#[^"]*"|id="[^"]*"', "", html))
    # every chip/badge carries a text label (guardrail 4)
    for m in re.finditer(
        r'<span class="mx-(?:chip mx-chip--\w+|badge--blocked)">([^<]*)</span>', html
    ):
        assert m.group(1).strip(), m.group(0)
    assert html.count("mx-btn-primary") == 1  # Primary 는 화면당 1개
