"""MYELIN Emboss 생성기 — design/tokens.json 하나에서 모든 산출물을 만든다 (ADR-0007).

  python design/build.py              # 산출물 생성
  python design/build.py --check      # 커밋된 산출물이 tokens.json 과 일치하는지 (Gate)
  python design/build.py --contrast   # 텍스트 조합 WCAG 4.5:1 검사 (Gate)
  python design/build.py --lint       # 손으로 쓴 CSS에 색·그림자 리터럴이 없는지 (Gate)

산출물
  design/dist/tokens.css               :root CSS 변수 (--mx-*)
  design/dist/tokens.resolved.json     참조가 풀린 평면 값 (JS·테스트용)
  design/dist/tailwind.preset.js       Hub(P6)용 Tailwind preset — 모두 var(--mx-*) 참조
  theme/obsidian-myelin-emboss/theme.css   Obsidian 테마 (.theme-light 에 토큰 + 매핑 + 컴포넌트)
표준 라이브러리만 사용한다.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "design"
TOKENS = DESIGN / "tokens.json"
OBSIDIAN_SRC = DESIGN / "src" / "obsidian.css"
COMPONENTS_SRC = DESIGN / "src" / "components.css"
THEME_DIR = ROOT / "theme" / "obsidian-myelin-emboss"
REF = re.compile(r"\{([a-z0-9-]+(?:\.[a-z0-9-]+)+)\}")
GROUPS = (
    "color",
    "glow",
    "accent",
    "status",
    "shadow",
    "radius",
    "space",
    "font",
    "focus",
    "motion",
)
HEADER = (
    "/* 자동 생성 — 직접 고치지 마세요. "
    "원천: design/tokens.json · 생성: python design/build.py */\n"
)

# 손으로 쓰는 CSS에서 금지하는 것 (토큰을 거치지 않은 색)
COLOR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(")
NEON_AS_TEXT = re.compile(
    r"(?<![-\w])color\s*:\s*var\(--mx-(lime|cyan|magenta|amber|slate|glow-[a-z]+|accent-[a-z]+-(fill|glow))\)"
)
LINT_TARGETS = (
    DESIGN / "src",
    DESIGN / "gallery",
    ROOT / "packages" / "myelin-hub" / "web" / "src",
)


# ── 토큰 ─────────────────────────────────────────────────────────────────
def load_tokens(path: Path = TOKENS) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def flatten(tokens: dict[str, Any]) -> dict[str, str]:
    """{'color.ink': '#2D2A3E', 'accent.violet.fill': '{color.violet}', ...}"""
    out: dict[str, str] = {}

    def walk(prefix: str, node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if not k.startswith("$"):
                    walk(f"{prefix}.{k}" if prefix else k, v)
        else:
            out[prefix] = str(node)

    for group in GROUPS:
        walk(group, tokens[group])
    return out


def resolve(flat: dict[str, str]) -> dict[str, str]:
    """참조를 풀어 실제 값으로. 없는 참조·순환은 오류."""
    done: dict[str, str] = {}

    def value(key: str, chain: tuple[str, ...]) -> str:
        if key in done:
            return done[key]
        if key in chain:
            raise ValueError(f"순환 참조: {' -> '.join((*chain, key))}")
        if key not in flat:
            raise ValueError(f"없는 토큰 참조: {key} ({' -> '.join(chain)})")
        result = REF.sub(lambda m: value(m.group(1), (*chain, key)), flat[key])
        done[key] = result
        return result

    for key in flat:
        value(key, ())
    return done


def var_name(key: str) -> str:
    """color.ink → --mx-ink, accent.violet.fill → --mx-accent-violet-fill"""
    group, _, rest = key.partition(".")
    name = rest if group == "color" else f"{group}-{rest}"
    return "--mx-" + name.replace(".", "-")


def css_value(raw: str) -> str:
    """참조는 var() 로 남긴다 — 하위 테마가 원천 하나만 바꿔도 따라오게."""
    return REF.sub(lambda m: f"var({var_name(m.group(1))})", raw)


def css_vars(flat: dict[str, str], indent: str = "  ") -> str:
    return "".join(f"{indent}{var_name(k)}: {css_value(v)};\n" for k, v in flat.items())


# ── 산출물 ───────────────────────────────────────────────────────────────
def render_tokens_css(flat: dict[str, str]) -> str:
    return HEADER + ":root {\n" + css_vars(flat) + "}\n"


def render_resolved_json(resolved: dict[str, str]) -> str:
    return json.dumps(resolved, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_tailwind(flat: dict[str, str]) -> str:
    def group(prefix: str) -> dict[str, str]:
        return {
            k[len(prefix) + 1 :].replace(".", "-"): f"var({var_name(k)})"
            for k in flat
            if k.startswith(prefix + ".")
        }

    preset = {
        "theme": {
            "extend": {
                "colors": {
                    "mx": group("color"),
                    "accent": group("accent"),
                    "status": group("status"),
                },
                "boxShadow": group("shadow"),
                "borderRadius": group("radius"),
                "spacing": {f"mx-{k}": v for k, v in group("space").items()},
                "fontFamily": {
                    "sans": ["var(--mx-font-sans)"],
                    "mono": ["var(--mx-font-mono)"],
                },
            }
        }
    }
    body = json.dumps(preset, ensure_ascii=False, indent=2)
    return (
        "// 자동 생성 — 직접 고치지 마세요. 원천: design/tokens.json\n"
        "// 사용: tailwind.config.js 에서 "
        "presets: [require('<repo>/design/dist/tailwind.preset.js')]\n"
        "// 값은 모두 var(--mx-*) — design/dist/tokens.css 를 함께 로드하세요.\n"
        f"module.exports = {body};\n"
    )


def render_obsidian_theme(flat: dict[str, str]) -> str:
    mapping = OBSIDIAN_SRC.read_text(encoding="utf-8")
    components = COMPONENTS_SRC.read_text(encoding="utf-8")
    return (
        HEADER
        + "/* MYELIN Emboss for Obsidian — 라이트 테마만 바꾼다. "
        + "다크 모드는 Obsidian 기본 (v1.0 범위 밖). */\n"
        + ".theme-light {\n"
        + css_vars(flat)
        + "}\n\n"
        + mapping
        + "\n/* ── 공용 컴포넌트 (Hub와 같음, .mx-* 클래스) ── */\n"
        + components
    )


def outputs() -> dict[Path, str]:
    tokens = load_tokens()
    flat = flatten(tokens)
    resolved = resolve(flat)
    return {
        DESIGN / "dist" / "tokens.css": render_tokens_css(flat),
        DESIGN / "dist" / "tokens.resolved.json": render_resolved_json(resolved),
        DESIGN / "dist" / "tailwind.preset.js": render_tailwind(flat),
        THEME_DIR / "theme.css": render_obsidian_theme(flat),
    }


# ── 검사 ─────────────────────────────────────────────────────────────────
def _channel(c: float) -> float:
    return c / 12.92 if c <= 0.03928 else float(((c + 0.055) / 1.055) ** 2.4)


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ValueError(f"대비 계산은 불투명 #RRGGBB 만 가능합니다: {hex_color}")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    hi, lo = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def contrast_report() -> tuple[list[str], list[str]]:
    tokens = load_tokens()
    resolved = resolve(flatten(tokens))
    lines, failures = [], []
    for fg, bg in tokens["contrast"]["pairs"]:
        ratio = contrast_ratio(resolved[fg], resolved[bg])
        ok = ratio >= 4.5
        lines.append(f"  {'OK  ' if ok else 'FAIL'} {ratio:5.2f}  {fg} on {bg}")
        if not ok:
            failures.append(f"{fg} on {bg} = {ratio:.2f} (< 4.5)")
    surface = resolved["color.surface"]
    for neon in tokens["contrast"]["neon"]:
        ratio = contrast_ratio(resolved[neon], surface)
        lines.append(
            f"  NEON {ratio:5.2f}  {neon} on color.surface — 텍스트 금지 (채움·glow·링 전용)"
        )
    return lines, failures


def lint_paths(paths: list[Path]) -> list[str]:
    problems: list[str] = []
    for base in paths:
        files = [base] if base.is_file() else sorted(base.rglob("*")) if base.exists() else []
        for f in files:
            if f.suffix not in {".css", ".tsx", ".ts", ".jsx", ".js", ".html", ".vue"}:
                continue
            for no, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                code = line.split("//")[0] if f.suffix != ".css" else line
                if COLOR_LITERAL.search(code):
                    problems.append(
                        f"{f.relative_to(ROOT)}:{no}: 색 리터럴 — 토큰(var(--mx-*))을 쓰세요"
                    )
                if NEON_AS_TEXT.search(code):
                    problems.append(
                        f"{f.relative_to(ROOT)}:{no}: 네온 색을 글자색으로 — *-ink 토큰을 쓰세요"
                    )
    return problems


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "--write"
    if mode == "--write":
        for path, text in outputs().items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(path.relative_to(ROOT))
        return 0
    if mode == "--check":
        stale = [
            str(p.relative_to(ROOT))
            for p, text in outputs().items()
            if not p.exists() or p.read_text(encoding="utf-8") != text
        ]
        for s in stale:
            print(f"오래된 산출물: {s} — python design/build.py 를 실행하세요")
        return 1 if stale else 0
    if mode == "--contrast":
        lines, failures = contrast_report()
        print("\n".join(lines))
        return 1 if failures else 0
    if mode == "--lint":
        problems = lint_paths(list(LINT_TARGETS))
        print("\n".join(problems) if problems else "lint OK")
        return 1 if problems else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
