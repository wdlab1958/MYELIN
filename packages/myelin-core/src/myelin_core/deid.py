"""비식별 검사 — Commons로 나가기 전에 고객명·개인정보·기밀 흔적을 찾는다 (명세 §9.1, ADR-0009).

자동 검사는 사람 검토를 대신하지 않는다. 찾은 것은 모두 **차단**(fail-closed)이며,
오탐은 Commons 저장소의 `policy/deid.yaml` `allow` 목록(챔피언이 관리)으로만 풀 수 있다.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from myelin_core.errors import Issue, MyelinError, issues_from_validation
from myelin_core.yamlio import load_yaml

POLICY_FILE = "policy/deid.yaml"


class DeidPolicyError(MyelinError):
    """비식별 정책 파일을 읽을 수 없음."""


class DeidPolicy(BaseModel):
    """Commons 저장소가 정하는 조직 정책. `deny` 는 고객명·내부 코드명 등 (대소문자 무시)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    deid: int = 1
    deny: list[Annotated[str, Field(min_length=2, max_length=200)]] = Field(default_factory=list)
    allow: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(default_factory=list)
    internal_domains: list[str] = Field(default_factory=list)  # 예: corp.example.com


def load_policy(commons: Path) -> DeidPolicy:
    path = commons / POLICY_FILE
    if not path.is_file():
        return DeidPolicy()
    data = load_yaml(path.read_text(encoding="utf-8"), POLICY_FILE, DeidPolicyError)
    try:
        return DeidPolicy.model_validate(data or {})
    except ValidationError as exc:
        raise DeidPolicyError(
            "비식별 정책 검증 실패", issues_from_validation(exc, prefix=POLICY_FILE)
        ) from exc


@dataclass(frozen=True)
class Finding:
    kind: str
    line: int
    excerpt: str  # 화면 표시용 — 값의 일부만 (가린 형태)

    def issue(self) -> Issue:
        return Issue(f"line {self.line}", f"{self.kind}: {self.excerpt}", f"deid_{self.kind}")


@dataclass
class DeidReport:
    findings: list[Finding] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.findings


def _mask(value: str) -> str:
    """찾은 값을 화면에 그대로 다시 노출하지 않는다."""
    v = value.strip()
    if len(v) <= 4:
        return "*" * len(v)
    return f"{v[:2]}{'*' * min(len(v) - 4, 8)}{v[-2:]}"


_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_IPV6 = re.compile(r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![0-9A-Fa-f:])")
_RRN = re.compile(r"(?<!\d)\d{6}-?[1-8]\d{6}(?!\d)")  # 주민등록번호·외국인등록번호
_PHONE = re.compile(
    r"(?<!\d)(?:\+82[- ]?)?0(?:1[016789]|2|[3-6][1-5])[- .]?\d{3,4}[- .]?\d{4}(?!\d)"
)
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_AWS_KEY = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
_TOKEN = re.compile(
    r"\b(?:ghp|gho|ghs|github_pat|xox[abpr]|sk|sk-ant|glpat)[-_][A-Za-z0-9_\-]{16,}"
)
_SECRET_ASSIGN = re.compile(
    r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?key|token|비밀번호)\b"
    r"\s*[:=]\s*['\"]?([^\s'\"]{6,})"
)
_URL_HOST = re.compile(r"https?://([^/\s:)\]>]+)")
_INTERNAL_TLDS = (".local", ".internal", ".corp", ".lan", ".intranet", ".home.arpa")


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _is_ip(text: str) -> bool:
    try:
        ipaddress.ip_address(text)
    except ValueError:
        return False
    return True


def _allowed(value: str, policy: DeidPolicy) -> bool:
    low = value.lower()
    return any(a.lower() in low for a in policy.allow)


def _scan_line(line: str, policy: DeidPolicy) -> Iterable[tuple[str, str]]:
    for m in _PRIVATE_KEY.finditer(line):
        yield "private_key", m.group(0)
    for m in _AWS_KEY.finditer(line):
        yield "cloud_key", m.group(0)
    for m in _TOKEN.finditer(line):
        yield "token", m.group(0)
    for m in _SECRET_ASSIGN.finditer(line):
        yield "secret", m.group(1)
    for m in _RRN.finditer(line):
        yield "rrn", m.group(0)
    for m in _CARD.finditer(line):
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn(digits):
            yield "card", m.group(0)
    for m in _PHONE.finditer(line):
        yield "phone", m.group(0)
    for m in _EMAIL.finditer(line):
        yield "email", m.group(0)
    for m in _IPV4.finditer(line):
        if _is_ip(m.group(0)):
            yield "ip", m.group(0)
    for m in _IPV6.finditer(line):
        if len(m.group(0)) >= 6 and _is_ip(m.group(0)):
            yield "ip", m.group(0)
    for m in _URL_HOST.finditer(line):
        host = m.group(1).lower()
        internal = host.endswith(_INTERNAL_TLDS) or any(
            host == d or host.endswith("." + d) for d in policy.internal_domains
        )
        if internal or host in ("localhost",):
            yield "internal_url", m.group(0)
    low = line.lower()
    for term in policy.deny:
        if term.lower() in low:
            yield "deny_term", term


def scan_text(text: str, policy: DeidPolicy | None = None) -> DeidReport:
    """frontmatter·본문 전체를 줄 단위로 검사한다."""
    policy = policy or DeidPolicy()
    report = DeidReport()
    seen: set[tuple[str, int, str]] = set()
    for no, line in enumerate(text.splitlines(), 1):
        for kind, value in _scan_line(line, policy):
            if kind != "deny_term" and _allowed(value, policy):
                continue
            key = (kind, no, value)
            if key in seen:
                continue
            seen.add(key)
            excerpt = value if kind == "deny_term" else _mask(value)
            report.findings.append(Finding(kind, no, excerpt))
    return report


# 사람이 직접 확인해야 하는 항목 — 자동 검사가 놓칠 수 있는 것 (Hub·PR 템플릿 공용)
MANUAL_CHECKLIST: dict[str, str] = {
    "no_customer": "고객사·기관 이름, 프로젝트 코드명이 없다 (돌려 말한 표현 포함)",
    "no_confidential": "진단 결과·취약점 세부·내부 설정 등 기밀 내용이 없다",
    "no_personal": "개인을 특정할 수 있는 정보(이름·연락처·사번)가 없다",
    "no_ip_invention": "직무발명·특허 출원 전 아이디어가 아니다",
    "ownership": "이 노트를 조직 공용 지식으로 공개하는 데 동의한다 (작성자·원 id 표기)",
}
