"""안전한 YAML 로딩 (ADR-0003: ruamel.yaml, YAML 1.2, safe, 중복 키 금지)."""

from __future__ import annotations

from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import MarkedYAMLError, YAMLError

from myelin_core.errors import Issue, MyelinError


def load_yaml(text: str, source: str, error_cls: type[MyelinError]) -> Any:
    """YAML 텍스트를 파이썬 객체로 읽는다. 실패하면 `error_cls` 로 구조화된 오류를 던진다.

    `source` 는 오류 위치 표시에 쓰는 이름이다 (예: ``pack.yaml``).
    """
    yaml = YAML(typ="safe", pure=True)
    yaml.allow_duplicate_keys = False
    try:
        return yaml.load(text)
    except MarkedYAMLError as exc:
        mark = exc.problem_mark or exc.context_mark
        loc = f"{source}:{mark.line + 1}:{mark.column + 1}" if mark is not None else source
        problem = exc.problem or exc.context or "invalid YAML"
        raise error_cls(f"YAML 문법 오류: {source}", [Issue(loc, problem, "yaml_syntax")]) from exc
    except YAMLError as exc:
        raise error_cls(f"YAML 오류: {source}", [Issue(source, str(exc), "yaml_error")]) from exc
