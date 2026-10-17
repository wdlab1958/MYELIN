"""T6 — JSON Schema export."""

from __future__ import annotations

import json
from pathlib import Path

from myelin_core.schema.export import SCHEMAS, export_json_schemas, json_schema
from myelin_core.schema.frontmatter import Frontmatter


def test_frontmatter_schema_shape() -> None:
    s = json_schema(Frontmatter)
    assert s["$schema"].startswith("https://json-schema.org/")
    assert set(s["required"]) == {"id", "type", "created"}
    props = s["properties"]
    assert set(props) == {
        "id",
        "type",
        "domain",
        "status",
        "origin",
        "confidence",
        "classification",
        "share",
        "source",
        "created",
        "reviewed",
        "tags",
    }
    assert s["additionalProperties"] is True  # ADR-0003 §2


def test_export_writes_all(tmp_path: Path) -> None:
    written = export_json_schemas(tmp_path / "schema")
    assert {p.name for p in written} == set(SCHEMAS)
    for p in written:
        data = json.loads(p.read_text(encoding="utf-8"))
        assert "$id" in data and "properties" in data
    pack = json.loads((tmp_path / "schema/pack.schema.json").read_text(encoding="utf-8"))
    assert pack["additionalProperties"] is False  # ADR-0003 §3
