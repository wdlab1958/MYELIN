"""Pack 버전과 `requires` 제약 (예: ``myelin.core>=1.0,<2``).

외부 의존성 없이 필요한 만큼만 구현한다: 숫자 3단 버전, 연산자 >= > <= < == !=.
"""

from __future__ import annotations

import operator
import re
from collections.abc import Callable
from dataclasses import dataclass

VersionTuple = tuple[int, int, int]

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_PARTIAL_RE = re.compile(r"^\d+(?:\.\d+){0,2}$")
_REQ_RE = re.compile(
    r"^\s*(?P<name>[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)+)\s*(?P<spec>.*?)\s*$"
)
_CLAUSE_RE = re.compile(r"^(>=|<=|==|!=|>|<)\s*(\S+)$")
_OPS: dict[str, Callable[[VersionTuple, VersionTuple], bool]] = {
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
}


def parse_version(text: str) -> VersionTuple:
    """엄격한 MAJOR.MINOR.PATCH."""
    m = _SEMVER_RE.match(text.strip())
    if not m:
        raise ValueError(f"version must be MAJOR.MINOR.PATCH: {text!r}")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _parse_partial(text: str) -> VersionTuple:
    if not _PARTIAL_RE.match(text):
        raise ValueError(f"invalid version in constraint: {text!r}")
    nums = [int(x) for x in text.split(".")] + [0, 0]
    return (nums[0], nums[1], nums[2])


@dataclass(frozen=True)
class Requirement:
    name: str
    clauses: tuple[tuple[str, VersionTuple], ...]

    def satisfied_by(self, version: VersionTuple) -> bool:
        return all(_OPS[op](version, bound) for op, bound in self.clauses)

    def __str__(self) -> str:
        spec = ",".join(f"{op}{'.'.join(map(str, v))}" for op, v in self.clauses)
        return f"{self.name}{spec}"


def parse_requirement(text: str) -> Requirement:
    m = _REQ_RE.match(text)
    if not m:
        raise ValueError(f"invalid requirement: {text!r}")
    clauses: list[tuple[str, VersionTuple]] = []
    spec = m.group("spec")
    if spec:
        for raw in spec.split(","):
            cm = _CLAUSE_RE.match(raw.strip())
            if not cm:
                raise ValueError(f"invalid constraint {raw.strip()!r} in {text!r}")
            clauses.append((cm.group(1), _parse_partial(cm.group(2))))
    return Requirement(name=m.group("name"), clauses=tuple(clauses))
