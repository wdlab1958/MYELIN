"""Emboss 토큰·생성기 테스트 (P5)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from myelin_core.pack import Accent

ROOT = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("design_build", ROOT / "design" / "build.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


build = _load()


def test_all_references_resolve() -> None:
    resolved = build.resolve(build.flatten(build.load_tokens()))
    assert not any("{" in v for v in resolved.values())
    assert resolved["accent.violet.fill"] == resolved["color.violet"]
    assert "rgba(163, 177, 198, 0.62)" in resolved["shadow.raised"]


@pytest.mark.parametrize(
    ("flat", "needle"),
    [
        ({"a.x": "{a.y}", "a.y": "{a.x}"}, "순환"),
        ({"a.x": "{a.missing}"}, "없는 토큰"),
    ],
)
def test_resolve_errors(flat: dict[str, str], needle: str) -> None:
    with pytest.raises(ValueError, match=needle):
        build.resolve(flat)


def test_var_names_and_css_values() -> None:
    assert build.var_name("color.ink") == "--mx-ink"
    assert build.var_name("accent.violet.fill") == "--mx-accent-violet-fill"
    assert build.css_value("1px {color.ink}") == "1px var(--mx-ink)"


def test_accents_match_pack_schema() -> None:
    """Pack의 accent 값(ADR-0004)마다 토큰이 있어야 한다 — 없으면 Domain Orb가 색을 잃는다."""
    tokens = build.load_tokens()
    assert set(tokens["accent"]) == {a.value for a in Accent}
    assert set(tokens["glow"]) == {a.value for a in Accent}


def test_status_tokens_cover_chips() -> None:
    css = (ROOT / "design/src/components.css").read_text(encoding="utf-8")
    for status in build.load_tokens()["status"]:
        assert f".mx-chip--{status}" in css


def test_generated_outputs_are_current() -> None:
    for path, text in build.outputs().items():
        assert path.read_text(encoding="utf-8") == text, path


def test_contrast_all_pass_and_neon_reported() -> None:
    lines, failures = build.contrast_report()
    assert failures == []
    assert sum("NEON" in line for line in lines) == len(build.load_tokens()["contrast"]["neon"])
    assert build.contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert build.contrast_ratio("#fff", "#000") == pytest.approx(21.0)
    with pytest.raises(ValueError):
        build.luminance("rgba(0,0,0,0.5)")


def test_lint_catches_literals_and_neon_text(tmp_path: Path) -> None:
    bad = tmp_path / "bad.css"
    bad.write_text(
        ".a { color: #ff0000; }\n"
        ".b { background: rgba(0, 0, 0, 0.1); }\n"
        ".c { color: var(--mx-lime); }\n"
        ".d { background-color: var(--mx-lime); border-color: var(--mx-cyan); }\n"
        ".e { color: var(--mx-lime-ink); }\n",
        encoding="utf-8",
    )
    build.ROOT = tmp_path  # 상대경로 출력용
    try:
        problems = build.lint_paths([bad])
    finally:
        build.ROOT = ROOT
    assert [p.split(":")[1] for p in problems] == ["1", "2", "3"]
    assert build.lint_paths([tmp_path / "missing"]) == []


def test_repository_lint_clean() -> None:
    assert build.lint_paths(list(build.LINT_TARGETS)) == []


def test_tailwind_preset_shape() -> None:
    text = (ROOT / "design/dist/tailwind.preset.js").read_text(encoding="utf-8")
    body = text[text.index("{") : text.rindex("}") + 1]
    preset = json.loads(body)
    ext = preset["theme"]["extend"]
    assert ext["colors"]["mx"]["ink"] == "var(--mx-ink)"
    assert ext["boxShadow"]["raised"] == "var(--mx-shadow-raised)"
    assert ext["colors"]["accent"]["violet-fill"] == "var(--mx-accent-violet-fill)"


def test_obsidian_theme() -> None:
    manifest = json.loads(
        (ROOT / "theme/obsidian-myelin-emboss/manifest.json").read_text(encoding="utf-8")
    )
    assert {"name", "version", "minAppVersion", "author"} <= set(manifest)
    css = (ROOT / "theme/obsidian-myelin-emboss/theme.css").read_text(encoding="utf-8")
    assert css.count(".theme-light {") == 2 and ".theme-dark" not in css
    assert "--background-primary: var(--mx-surface)" in css


def test_cli_modes(capsys: pytest.CaptureFixture[str]) -> None:
    assert build.main(["build.py", "--check"]) == 0
    assert build.main(["build.py", "--contrast"]) == 0
    assert build.main(["build.py", "--lint"]) == 0
    assert build.main(["build.py", "--nope"]) == 2
    assert "design/build.py" in capsys.readouterr().out
