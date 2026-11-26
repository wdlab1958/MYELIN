"""Team mode for the Hub (ADR-0016, WBS 2.5.5) — optional; Personal mode is the default.

Personal mode (no auth file): the Hub binds to loopback only and behaves exactly as before.

Team mode (an auth file is given): the owner shares a *review channel* to their Vault.

- Every `/api/*` request needs `Authorization: Bearer <token>`. Only the SHA-256 of each token is
  stored; the comparison is constant-time and looks at every user (no early exit).
- Roles: `read` (GET of the allow-listed routes) and `write` (also the review actions —
  promote / reject a draft, apply / reject a patch). Owner operations (settings, packs, domains,
  onboarding, commons, obsidian, git, doctor, guard log) are not on the team channel at all.
- Confidential notes (`classification: confidential`, anything under `40_IP/`) are never served
  in team mode — the same rule the MCP server applies to an external session (ADR-0011 §3).
  Hidden notes answer 404, exactly like notes that do not exist.
- Every `/api/*` request is appended to `<Vault>/.myelin/hub-access.log` (JSON lines).
- No CORS headers are ever sent; Host and Origin must be loopback or listed in `allowed_hosts`.
  Authentication is a header, not a cookie, so a cross-site page cannot ride a session (CSRF).

Auth file (YAML, must not be readable by group/others):

```yaml
allowed_hosts: [hub.team.example]     # Host names / IPs clients use (loopback is always allowed)
users:
  - { name: alice, role: write, token_sha256: <64 hex> }
  - { name: bob,   role: read,  token_sha256: <64 hex> }
```
Create an entry with `myelin-hub --new-token alice --role write` (the token is shown once).
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import re
import secrets
import stat
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from myelin_core.schema.frontmatter import Classification
from myelin_core.vault import IP, RUNTIME

ROLE_READ = "read"
ROLE_WRITE = "write"
ROLES = (ROLE_READ, ROLE_WRITE)
AUTH_ENV = "MYELIN_HUB_AUTH_FILE"
ACCESS_LOG = f"{RUNTIME}/hub-access.log"
ACCESS_LOG_MAX_BYTES = 5 * 1024 * 1024
LOOPBACK_BINDS = ("127.0.0.1", "localhost", "::1")
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_HOST_RE = re.compile(r"^[A-Za-z0-9.:\[\]-]{1,253}$")
MIN_TOKEN_CHARS = 32
FAIL_WINDOW_S = 300.0
FAIL_LIMIT = 20

# (method, path regex, minimum role). Anything not listed is refused in team mode (403).
TEAM_ROUTES: tuple[tuple[str, re.Pattern[str], str], ...] = tuple(
    (m, re.compile(p), r)
    for m, p, r in (
        ("GET", r"^/api/vault$", ROLE_READ),
        ("GET", r"^/api/stats$", ROLE_READ),
        ("GET", r"^/api/domains$", ROLE_READ),
        ("GET", r"^/api/notes$", ROLE_READ),
        ("GET", r"^/api/notes/.+$", ROLE_READ),
        ("GET", r"^/api/search$", ROLE_READ),
        ("GET", r"^/api/review$", ROLE_READ),
        ("GET", r"^/api/packs$", ROLE_READ),
        ("GET", r"^/api/packs/[^/]+$", ROLE_READ),
        ("POST", r"^/api/packs/validate$", ROLE_READ),
        ("GET", r"^/api/patches$", ROLE_READ),
        ("GET", r"^/api/patches/[^/]+/preview$", ROLE_READ),
        ("GET", r"^/api/assistant/status$", ROLE_READ),
        ("POST", r"^/api/assistant/chat$", ROLE_READ),
        ("GET", r"^/api/team/me$", ROLE_READ),
        ("POST", r"^/api/review/promote/.+$", ROLE_WRITE),
        ("POST", r"^/api/review/reject/.+$", ROLE_WRITE),
        ("POST", r"^/api/patches/[^/]+/apply$", ROLE_WRITE),
        ("POST", r"^/api/patches/[^/]+/reject$", ROLE_WRITE),
    )
)


class TeamConfigError(ValueError):
    """The auth file is missing, unsafe or invalid — the Hub must not start."""


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token() -> tuple[str, str]:
    """A fresh random token (256 bits) and the hash that goes into the auth file."""
    token = "mxt_" + secrets.token_urlsafe(32)
    return token, token_hash(token)


@dataclass(frozen=True)
class TeamUser:
    name: str
    role: str
    token_sha256: str

    def allows(self, need: str) -> bool:
        return self.role == ROLE_WRITE or need == ROLE_READ


@dataclass(frozen=True)
class TeamAuth:
    users: tuple[TeamUser, ...]
    allowed_hosts: frozenset[str] = frozenset()

    def authenticate(self, token: str | None) -> TeamUser | None:
        """Constant-time: hash the presented token, compare against every user, no early exit."""
        if not token or len(token) < MIN_TOKEN_CHARS or len(token) > 512:
            token = ""  # still do the full comparison work below
        presented = token_hash(token)
        found: TeamUser | None = None
        for u in self.users:
            if hmac.compare_digest(presented, u.token_sha256) and token:
                found = u
        return found

    @classmethod
    def from_mapping(cls, data: Any, where: str = "auth file") -> TeamAuth:
        if not isinstance(data, dict):
            raise TeamConfigError(f"{where}: must be a mapping with `users`")
        unknown = sorted(set(data) - {"users", "allowed_hosts"})
        if unknown:
            raise TeamConfigError(f"{where}: unknown key(s) {unknown}")
        raw_users = data.get("users")
        if not isinstance(raw_users, list) or not raw_users:
            raise TeamConfigError(f"{where}: `users` must list at least one user")
        users: list[TeamUser] = []
        for i, u in enumerate(raw_users):
            if not isinstance(u, dict) or set(u) != {"name", "role", "token_sha256"}:
                raise TeamConfigError(
                    f"{where}: users[{i}] must have exactly name, role, token_sha256"
                )
            name, role, digest = str(u["name"]), str(u["role"]), str(u["token_sha256"]).lower()
            if not _NAME_RE.match(name):
                raise TeamConfigError(f"{where}: users[{i}].name is not a valid user name")
            if role not in ROLES:
                raise TeamConfigError(f"{where}: users[{i}].role must be one of {list(ROLES)}")
            if not _HEX64_RE.match(digest):
                raise TeamConfigError(
                    f"{where}: users[{i}].token_sha256 must be 64 hex chars (a SHA-256, never "
                    "the token itself)"
                )
            users.append(TeamUser(name, role, digest))
        if len({u.name for u in users}) != len(users):
            raise TeamConfigError(f"{where}: duplicate user name")
        if len({u.token_sha256 for u in users}) != len(users):
            raise TeamConfigError(f"{where}: two users share one token")
        hosts = data.get("allowed_hosts") or []
        if not isinstance(hosts, list) or not all(
            isinstance(h, str) and _HOST_RE.match(h) and h != "*" for h in hosts
        ):
            raise TeamConfigError(f"{where}: allowed_hosts must be a list of host names (no '*')")
        return cls(tuple(users), frozenset(h.lower() for h in hosts))

    @classmethod
    def load(cls, path: Path) -> TeamAuth:
        p = Path(path).expanduser()
        try:
            st = p.stat()
        except OSError as exc:
            raise TeamConfigError(f"auth file not readable: {p}: {exc}") from None
        if not stat.S_ISREG(st.st_mode):
            raise TeamConfigError(f"auth file is not a regular file: {p}")
        if os.name == "posix" and st.st_mode & 0o077:
            raise TeamConfigError(
                f"auth file {p} is readable by group/others (mode {st.st_mode & 0o777:o}) — "
                "chmod 600"
            )
        try:
            data = YAML(typ="safe").load(io.StringIO(p.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, YAMLError) as exc:
            raise TeamConfigError(f"auth file {p} cannot be parsed: {exc}") from None
        return cls.from_mapping(data, str(p))


@dataclass
class LiveTeamAuth:
    """The auth file, re-read whenever its bytes change — a token removed from the file stops
    working on the next request, without a restart (the stale-revocation defect class of
    formal/mcp-config-revocation-stale). Fail-closed: when the file becomes unreadable, unsafe
    or invalid, `current()` raises and every request is refused until it is fixed."""

    path: Path
    _bytes: bytes | None = field(default=None, repr=False)
    _auth: TeamAuth | None = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def open(cls, path: Path) -> LiveTeamAuth:
        live = cls(Path(path).expanduser())
        live.current()  # refuse to start on a bad file
        return live

    def current(self) -> TeamAuth:
        with self._lock:
            try:
                raw = self.path.read_bytes()
            except OSError as exc:
                self._bytes = self._auth = None
                raise TeamConfigError(f"auth file not readable: {self.path}: {exc}") from None
            if self._auth is None or raw != self._bytes:
                self._bytes = self._auth = None
                self._auth = TeamAuth.load(self.path)  # raises TeamConfigError
                self._bytes = raw
            return self._auth


def is_loopback_bind(host: str) -> bool:
    return host in LOOPBACK_BINDS


def check_bind(
    host: str, auth: TeamAuth | None, *, tls: bool, behind_tls_proxy: bool
) -> str | None:
    """Why this bind must be refused, or None. Secure by default: a non-loopback address needs
    authentication, an explicit Host allow-list and an encrypted channel."""
    if is_loopback_bind(host):
        return None
    if auth is None:
        return (
            "refusing to bind a non-loopback address without authentication — "
            f"give --auth-file (or ${AUTH_ENV}); see docs/adr/0016-hub-team-mode.md"
        )
    if not auth.allowed_hosts:
        return "team mode on a non-loopback address needs `allowed_hosts` in the auth file"
    if not (tls or behind_tls_proxy):
        return (
            "team mode on a non-loopback address would send bearer tokens in clear text — give "
            "--tls-cert/--tls-key, or --behind-tls-proxy when a TLS reverse proxy fronts the Hub"
        )
    return None


def restricted(path: str, classification: str | None) -> bool:
    """The confidentiality rule shared with the MCP server (`VaultService._hidden`).

    Fail-closed: an unknown classification (parse error, note not in the index) is restricted."""
    if path.startswith(IP + "/") or path == IP:
        return True
    return classification is None or classification == Classification.CONFIDENTIAL.value


@dataclass
class AccessLog:
    """Append-only JSON-lines audit log in the Vault's runtime directory (git-ignored)."""

    root: Path
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def path(self) -> Path:
        return self.root / ACCESS_LOG

    def write(self, **event: Any) -> None:
        line = json.dumps({"ts": round(time.time(), 3), **event}, ensure_ascii=False)
        with self._lock:
            p = self.path
            p.parent.mkdir(parents=True, exist_ok=True)
            try:
                if p.stat().st_size > ACCESS_LOG_MAX_BYTES:
                    p.replace(p.with_suffix(".log.1"))
            except FileNotFoundError:
                pass
            fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")


@dataclass
class FailureThrottle:
    """Slow down token guessing: too many failed logins from one client → 429 for a while."""

    limit: int = FAIL_LIMIT
    window: float = FAIL_WINDOW_S
    _fails: dict[str, deque[float]] = field(default_factory=dict, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def blocked(self, client: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._fails.get(client)
            if not q:
                return False
            while q and now - q[0] > self.window:
                q.popleft()
            return len(q) >= self.limit

    def record(self, client: str, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        with self._lock:
            if len(self._fails) > 10_000:  # bounded memory
                self._fails.clear()
            self._fails.setdefault(client, deque(maxlen=self.limit)).append(now)


def route_role(method: str, path: str) -> str | None:
    """Minimum role for a team-channel route, or None when the route is not on the channel."""
    for m, pat, role in TEAM_ROUTES:
        if m == method and pat.match(path):
            return role
    return None


def bearer(header: str | None) -> str | None:
    if not header:
        return None
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return value.strip() or None
