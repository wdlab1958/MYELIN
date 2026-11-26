"""Customer-information guard — a deterministic pre-write check (ADR-0017, WBS 2.5.5).

MYELIN is an internal knowledge tool whose skills run through an external LLM session, so three
things must never be recorded in a Vault: customer identifiers, customer code and credentials
(`docs/guides/knowledge-management-policy.md`). This module is the device behind that rule. It is
plain pattern matching — no model is consulted — and it is called by every path that stores a
note outside `00_Inbox` or creates a draft on behalf of another tool:

- Hub Review Gate promote (00_Inbox → 10_Domains) and patch apply
- MCP `write_draft`, the One Cycle findings importer (`myelin onecycle import-findings`)
- Commons publish (on top of the de-identification scan), `myelin doctor --staged` (pre-commit)
- `myelin guard scan` for an on-demand check

Two severities:

- **block** — a credential, a resident registration number or a name on the customer denylist.
  The write is refused; the human rewrites the note.
- **flag**  — something a human must look at before it leaves the Inbox: a long code block
  (possibly customer code), an IP address, an internal URL. The write needs an explicit
  acknowledgement.

Policy sources (all optional; the built-in rules always apply):

- `<Vault>/90_System/infoguard.yaml` — thresholds, extra patterns, `names_file`
- customer names, one per line (`#` comments): `<Vault>/.myelin/customer-names.txt` (the runtime
  directory is git-ignored: the denylist is itself customer information and must not be committed
  or shared), the file named by `names_file`, and `$MYELIN_CUSTOMER_NAMES`
- `<Vault>/90_System/deid.yaml` `terms:` (the Commons de-identification list is reused)

Fail-closed: an unreadable or invalid policy raises `GuardError`; callers refuse the write.
Hit excerpts are masked so that a report or log never repeats the secret it found.
"""

from __future__ import annotations

import io
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

POLICY_FILE = "90_System/infoguard.yaml"
DEID_FILE = "90_System/deid.yaml"
LOCAL_NAMES_FILE = ".myelin/customer-names.txt"
NAMES_ENV = "MYELIN_CUSTOMER_NAMES"
DEFAULT_MAX_CODE_LINES = 30
MIN_TERM_LEN = 2

BLOCK = "block"
FLAG = "flag"

_PLACEHOLDER = (
    r"(?!(?:true|false|none|null|nil|required|optional|redacted|masked|changeme|example)\b)"
)
SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "private-key": re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "slack-token": re.compile(r"\bxox[abeprs]-[A-Za-z0-9-]{10,}"),
    "api-key-prefix": re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "bearer-token": re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+[A-Za-z0-9._~+/-]{16,}"),
    "url-credentials": re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@<>{}$]+:[^\s:/@<>{}$*]{3,}@"),
    # key = value with a literal value; placeholders (<…>, {{…}}, $VAR, ****) do not match
    "credential-assignment": re.compile(
        r"(?i)\b(?:api[_-]?key|secret(?:[_-]?key)?|password|passwd|pwd|access[_-]?key|"
        r"auth[_-]?token|token|비밀번호|패스워드)\b[\"']?\s*[:=]\s*[\"']?"
        + _PLACEHOLDER
        + r"[^\s\"'<>{}$*`|\[\]()]{6,}"
    ),
}
PERSONAL_PATTERNS: dict[str, re.Pattern[str]] = {
    "resident-number": re.compile(r"\b\d{6}-[1-4]\d{6}\b"),
}
FLAG_PATTERNS: dict[str, re.Pattern[str]] = {
    "ip-address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "internal-url": re.compile(r"https?://[^\s)]*\.(?:internal|local|corp|lan|intra)\b[^\s)]*"),
}
# never an identifier: unspecified/loopback/broadcast and the RFC 5737 documentation ranges
_IP_IGNORE = ("0.", "127.", "255.", "192.0.2.", "198.51.100.", "203.0.113.")
_FENCE_RE = re.compile(r"^\s{0,3}(```+|~~~+)")
_ALLOWED_KEYS = {"max_code_block_lines", "block_patterns", "flag_patterns", "names_file", "terms"}


class GuardError(ValueError):
    """The guard policy cannot be read — callers must refuse the write (fail-closed)."""


@dataclass(frozen=True)
class GuardHit:
    rule: str
    severity: str  # BLOCK | FLAG
    line: int
    excerpt: str  # masked — never the full secret or customer name

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "line": self.line,
            "excerpt": self.excerpt,
        }


@dataclass
class GuardReport:
    hits: list[GuardHit] = field(default_factory=list)

    @property
    def blocks(self) -> list[GuardHit]:
        return [h for h in self.hits if h.severity == BLOCK]

    @property
    def flags(self) -> list[GuardHit]:
        return [h for h in self.hits if h.severity == FLAG]

    @property
    def blocked(self) -> bool:
        return bool(self.blocks)

    @property
    def flagged(self) -> bool:
        return bool(self.flags)

    @property
    def clean(self) -> bool:
        return not self.hits

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocked": self.blocked,
            "flagged": self.flagged,
            "hits": [h.to_dict() for h in self.hits],
        }

    def summary(self, limit: int = 5) -> str:
        parts = [f"{h.rule} (line {h.line}: {h.excerpt})" for h in self.hits[:limit]]
        more = len(self.hits) - limit
        return "; ".join(parts) + (f"; … +{more}" if more > 0 else "")


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s).casefold()


def _mask(s: str, keep: int = 4) -> str:
    s = s.strip()
    if len(s) <= keep:
        return s[:1] + "***"
    return s[:keep] + "***"


@dataclass
class GuardPolicy:
    customer_terms: list[str] = field(default_factory=list)
    max_code_block_lines: int = DEFAULT_MAX_CODE_LINES
    block_patterns: dict[str, re.Pattern[str]] = field(default_factory=dict)
    flag_patterns: dict[str, re.Pattern[str]] = field(default_factory=dict)

    @classmethod
    def default(cls) -> GuardPolicy:
        return cls()

    @classmethod
    def load(cls, vault_root: Path | None, *, env: dict[str, str] | None = None) -> GuardPolicy:
        """Policy for a Vault (built-ins when nothing is configured). Raises GuardError."""
        policy = cls()
        environ = os.environ if env is None else env
        names_files: list[Path] = []
        if vault_root is not None:
            root = Path(vault_root)
            data = _load_yaml(root / POLICY_FILE)
            unknown = sorted(set(data) - _ALLOWED_KEYS)
            if unknown:
                raise GuardError(f"{POLICY_FILE}: unknown key(s) {unknown}")
            if "max_code_block_lines" in data:
                n = data["max_code_block_lines"]
                if not isinstance(n, int) or isinstance(n, bool) or n < 1:
                    raise GuardError(f"{POLICY_FILE}: max_code_block_lines must be an integer ≥ 1")
                policy.max_code_block_lines = n
            for key, target in (
                ("block_patterns", policy.block_patterns),
                ("flag_patterns", policy.flag_patterns),
            ):
                for i, pat in enumerate(_str_list(data.get(key), key)):
                    try:
                        target[f"custom-{key.split('_')[0]}-{i}"] = re.compile(pat)
                    except re.error as exc:
                        raise GuardError(f"{POLICY_FILE}: bad pattern {pat!r}: {exc}") from None
            policy.customer_terms += _str_list(data.get("terms"), "terms")
            if data.get("names_file"):
                nf = Path(str(data["names_file"])).expanduser()
                nf = nf if nf.is_absolute() else root / nf
                if (
                    not nf.is_file()
                ):  # configured but missing → the denylist would silently be empty
                    raise GuardError(f"{POLICY_FILE}: names_file not found: {nf}")
                names_files.append(nf)
            names_files.append(root / LOCAL_NAMES_FILE)
            deid = _load_yaml(root / DEID_FILE)
            policy.customer_terms += _str_list(deid.get("terms"), f"{DEID_FILE} terms")
        if environ.get(NAMES_ENV):
            envf = Path(environ[NAMES_ENV]).expanduser()
            if not envf.is_file():
                raise GuardError(f"${NAMES_ENV} points to a missing file: {envf}")
            names_files.append(envf)
        for f in names_files:
            policy.customer_terms += _read_names(f)
        seen: dict[str, str] = {}
        for t in policy.customer_terms:
            t = t.strip()
            if len(t) >= MIN_TERM_LEN:
                seen.setdefault(_norm(t), t)
        policy.customer_terms = list(seen.values())
        return policy


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = YAML(typ="safe").load(io.StringIO(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, YAMLError) as exc:
        raise GuardError(f"{path.name}: cannot be read: {exc}") from None
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise GuardError(f"{path.name}: must be a mapping")
    return {str(k): v for k, v in data.items()}


def _str_list(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise GuardError(f"{label} must be a list of strings")
    return list(value)


def _read_names(path: Path) -> list[str]:
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise GuardError(f"{path}: cannot be read: {exc}") from None
    return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def scan_text(text: str, policy: GuardPolicy | None = None) -> GuardReport:
    """Scan one note (frontmatter included). Deterministic; never raises on content."""
    policy = policy or GuardPolicy.default()
    hits: list[GuardHit] = []
    block_rules = {**SECRET_PATTERNS, **PERSONAL_PATTERNS, **policy.block_patterns}
    flag_rules = {**FLAG_PATTERNS, **policy.flag_patterns}
    terms = [(_norm(t), t) for t in policy.customer_terms]
    fence: str | None = None
    fence_start = 0
    fence_lines = 0
    lines = text.splitlines()
    for n, line in enumerate(lines, 1):
        for rule, pat in block_rules.items():
            for m in pat.finditer(line):
                hits.append(GuardHit(rule, BLOCK, n, _mask(m.group(0))))
        if terms:
            folded = _norm(line)
            for key, original in terms:
                if key in folded:
                    hits.append(GuardHit("customer-name", BLOCK, n, _mask(original, 1)))
        for rule, pat in flag_rules.items():
            for m in pat.finditer(line):
                if rule == "ip-address" and (
                    m.group(0).startswith(_IP_IGNORE)
                    or any(int(p) > 255 for p in m.group(0).split("."))
                ):
                    continue
                hits.append(GuardHit(rule, FLAG, n, _mask(m.group(0), 6)))
        fm = _FENCE_RE.match(line)
        if fm:
            marker = fm.group(1)
            if fence is None:
                fence, fence_start, fence_lines = marker[0], n, 0
            elif marker[0] == fence:
                if fence_lines > policy.max_code_block_lines:
                    hits.append(_code_hit(fence_start, fence_lines, policy))
                fence = None
        elif fence is not None:
            fence_lines += 1
    if fence is not None and fence_lines > policy.max_code_block_lines:  # unterminated block
        hits.append(_code_hit(fence_start, fence_lines, policy))
    return GuardReport(hits)


def _code_hit(start: int, count: int, policy: GuardPolicy) -> GuardHit:
    return GuardHit(
        "large-code-block",
        FLAG,
        start,
        f"{count} lines > {policy.max_code_block_lines} — customer code must not be recorded",
    )


def scan_vault_text(vault_root: Path, text: str) -> GuardReport:
    """Convenience for call sites: load the Vault policy (fail-closed) and scan."""
    return scan_text(text, GuardPolicy.load(vault_root))
