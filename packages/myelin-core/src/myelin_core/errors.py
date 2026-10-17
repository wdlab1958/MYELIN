"""구조화된 오류 모델.

모든 검증 오류는 `Issue(loc, msg, code)` 목록으로 표현한다.
`loc` 은 사람이 읽을 수 있는 필드 경로다: ``domains[0].id``, ``pack.yaml:3:5``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from pydantic import ValidationError


@dataclass(frozen=True)
class Issue:
    loc: str
    msg: str
    code: str = "invalid"

    def __str__(self) -> str:
        return f"{self.loc}: {self.msg}"


class MyelinError(Exception):
    """MYELIN 오류의 공통 기반. 항상 하나 이상의 Issue를 가진다."""

    def __init__(self, message: str, issues: Sequence[Issue] = ()) -> None:
        super().__init__(message)
        self.message = message
        self.issues: list[Issue] = list(issues) or [Issue("<unknown>", message)]

    def __str__(self) -> str:
        lines = [self.message, *(f"  - {issue}" for issue in self.issues)]
        return "\n".join(lines)


class NoteParseError(MyelinError):
    """노트를 읽거나 frontmatter를 검증할 수 없음."""


class PackError(MyelinError):
    """Domain Pack을 읽거나 검증·해석할 수 없음."""


def format_loc(parts: Iterable[str | int]) -> str:
    """('domains', 0, 'id') -> 'domains[0].id'"""
    out = ""
    for part in parts:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else str(part)
    return out or "<root>"


def issues_from_validation(err: ValidationError, prefix: str = "") -> list[Issue]:
    issues: list[Issue] = []
    for e in err.errors():
        loc = format_loc(e["loc"])
        if prefix:
            loc = prefix if loc == "<root>" else f"{prefix}.{loc}"
        issues.append(Issue(loc=loc, msg=e["msg"], code=e["type"]))
    return issues
