"""JSON Schema export for Frontmatter v2, Pack, Taxonomy, InterviewBank.

정본 §4.1 L0 Definition — "무엇을 어떻게 기록할지 선언".
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from myelin_core.schema.frontmatter import Frontmatter
from myelin_core.schema.pack import InterviewBank, Pack, Taxonomy

SCHEMAS: dict[str, type[BaseModel]] = {
    "frontmatter.schema.json": Frontmatter,
    "pack.schema.json": Pack,
    "taxonomy.schema.json": Taxonomy,
    "interviews.schema.json": InterviewBank,
}


def json_schema(model: type[BaseModel]) -> dict[str, object]:
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://myelin.wdlab/schema/{model.__name__.lower()}.json"
    return schema


def export_json_schemas(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, model in SCHEMAS.items():
        path = out_dir / filename
        path.write_text(
            json.dumps(json_schema(model), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        written.append(path)
    return written
