import json
from pathlib import Path

import pytest

from myelin_core.schema_export import SCHEMAS, main, render_schemas, write_schemas

ROOT = Path(__file__).resolve().parents[3]


def test_render_is_valid_json_and_deterministic() -> None:
    first, second = render_schemas(), render_schemas()
    assert first == second and set(first) == set(SCHEMAS)
    fm = json.loads(first["frontmatter.schema.json"])
    assert set(fm["required"]) == {"id", "type", "status", "origin", "created"}


def test_committed_schemas_are_current() -> None:
    for name, text in render_schemas().items():
        assert (ROOT / "schemas" / name).read_text(encoding="utf-8") == text, name


def test_write_and_main(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    written = write_schemas(tmp_path / "out")
    assert len(written) == len(SCHEMAS)
    assert main([str(tmp_path / "cli")]) == 0
    assert "pack.schema.json" in capsys.readouterr().out


def test_errors_str_and_default_issue() -> None:
    from myelin_core.errors import MyelinError

    err = MyelinError("boom")
    assert err.issues[0].loc == "<unknown>" and "boom" in str(err)
