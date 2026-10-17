"""JSON Schema export — 에디터 자동완성·외부 도구 검증용.

`python -m myelin_core.schema_export [out_dir]` (기본: ./schemas)
Gate P1은 커밋된 `schemas/*.json` 이 모델과 일치하는지 검사한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import BaseModel

from myelin_core.frontmatter import Frontmatter
from myelin_core.pack import InterviewBank, PackManifest, TaxonomyFile

SCHEMAS: dict[str, type[BaseModel]] = {
    "frontmatter.schema.json": Frontmatter,
    "pack.schema.json": PackManifest,
    "taxonomy.schema.json": TaxonomyFile,
    "interview-bank.schema.json": InterviewBank,
}


def render_schemas() -> dict[str, str]:
    out: dict[str, str] = {}
    for name, model in SCHEMAS.items():
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        out[name] = json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    return out


def write_schemas(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, text in render_schemas().items():
        target = out_dir / name
        target.write_text(text, encoding="utf-8")
        written.append(target)
    return written


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    for path in write_schemas(Path(args[0] if args else "schemas")):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
