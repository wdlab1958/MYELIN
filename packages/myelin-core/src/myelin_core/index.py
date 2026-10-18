"""Vault index — SQLite FTS5 at `<Vault>/.myelin/index.db` (정본 §4.4 색인, P4-T1).

- `VaultIndex.refresh()` is incremental: a note is re-parsed only when (mtime, size) changed;
  deleted files are removed. Parse errors are recorded (so doctor/MCP can report them) and the
  note is dropped from the searchable set.
- Full-text search uses the `trigram` tokenizer (case-insensitive substring match, works for
  Korean without a morphological analyser; queries need ≥ 3 characters).
- The index is a cache of the Markdown 정본 — it can be deleted and rebuilt at any time.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from types import TracebackType
from typing import Any

from myelin_core.note import NoteParseError, parse_note
from myelin_core.schema.frontmatter import Classification
from myelin_core.stats import Stats
from myelin_core.vault import INBOX, OUTPUTS, RUNTIME, Vault

SCHEMA_VERSION = 1
DB_NAME = "index.db"

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notes (
    path TEXT PRIMARY KEY,
    id TEXT NOT NULL,
    title TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    origin TEXT NOT NULL,
    confidence TEXT NOT NULL,
    classification TEXT NOT NULL,
    share INTEGER NOT NULL,
    created TEXT NOT NULL,
    reviewed TEXT,
    domains TEXT NOT NULL,       -- JSON list
    tags TEXT NOT NULL,          -- JSON list
    source TEXT NOT NULL,        -- JSON list
    mtime_ns INTEGER NOT NULL,
    size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    body TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS notes_id ON notes(id);
CREATE INDEX IF NOT EXISTS notes_status ON notes(status);
CREATE INDEX IF NOT EXISTS notes_type ON notes(type);
CREATE TABLE IF NOT EXISTS note_domains (
    path TEXT NOT NULL, domain TEXT NOT NULL, PRIMARY KEY (path, domain));
CREATE INDEX IF NOT EXISTS note_domains_domain ON note_domains(domain);
CREATE TABLE IF NOT EXISTS note_tags (
    path TEXT NOT NULL, tag TEXT NOT NULL, PRIMARY KEY (path, tag));
CREATE TABLE IF NOT EXISTS links (
    src TEXT NOT NULL, target TEXT NOT NULL, PRIMARY KEY (src, target));
CREATE INDEX IF NOT EXISTS links_target ON links(target);
CREATE TABLE IF NOT EXISTS parse_errors (
    path TEXT PRIMARY KEY, message TEXT NOT NULL, mtime_ns INTEGER NOT NULL,
    size INTEGER NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    path UNINDEXED, title, body, tags, tokenize='trigram'
);
INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', '{SCHEMA_VERSION}');
"""


@dataclass(frozen=True)
class IndexedNote:
    path: str
    id: str
    title: str
    type: str
    status: str
    origin: str
    confidence: str
    classification: str
    share: bool
    created: str
    reviewed: str | None
    domains: tuple[str, ...]
    tags: tuple[str, ...]
    source: tuple[str, ...]

    @property
    def is_confidential(self) -> bool:
        return self.classification == Classification.CONFIDENTIAL.value

    def to_dict(self) -> dict[str, Any]:
        d = self.__dict__.copy()
        for k in ("domains", "tags", "source"):
            d[k] = list(d[k])
        return d


@dataclass(frozen=True)
class SearchHit:
    note: IndexedNote
    snippet: str
    rank: float

    def to_dict(self) -> dict[str, Any]:
        return {**self.note.to_dict(), "snippet": self.snippet, "rank": round(self.rank, 4)}


@dataclass(frozen=True)
class RefreshResult:
    added: int
    updated: int
    removed: int
    unchanged: int
    errors: int

    @property
    def changed(self) -> int:
        return self.added + self.updated + self.removed


def _row_to_note(r: sqlite3.Row) -> IndexedNote:
    return IndexedNote(
        path=r["path"],
        id=r["id"],
        title=r["title"],
        type=r["type"],
        status=r["status"],
        origin=r["origin"],
        confidence=r["confidence"],
        classification=r["classification"],
        share=bool(r["share"]),
        created=r["created"],
        reviewed=r["reviewed"],
        domains=tuple(json.loads(r["domains"])),
        tags=tuple(json.loads(r["tags"])),
        source=tuple(json.loads(r["source"])),
    )


def fts_query(text: str) -> tuple[str | None, list[str]]:
    """Split free text into (FTS5 MATCH expression | None, short tokens).

    Trigram FTS needs ≥ 3 characters per token; shorter tokens (common for Korean: 예산, 실험)
    are matched with case-insensitive substring LIKE instead. Every FTS token is quoted, so
    user text can never inject FTS syntax. Raises ValueError when nothing searchable remains
    (fail-closed: no accidental "match everything").
    """
    tokens = [t for t in text.split() if t]
    if not tokens:
        raise ValueError("search query must contain at least one token")
    long_ = [t.replace('"', '""') for t in tokens if len(t) >= 3]
    short = [t for t in tokens if len(t) < 3]
    match = " AND ".join(f'"{t}"' for t in long_) if long_ else None
    return match, short


def _like(token: str) -> str:
    esc = token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"


class _LockedConnection:
    """sqlite3.Connection facade that serialises every call with an RLock (thread-safe sharing)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = threading.RLock()

    @property
    def row_factory(self) -> Any:
        return self._conn.row_factory

    @row_factory.setter
    def row_factory(self, value: Any) -> None:
        self._conn.row_factory = value

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params or ())

    def executemany(self, sql: str, seq: Iterable[Sequence[Any]]) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.executemany(sql, seq)

    def executescript(self, script: str) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.executescript(script)

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> _LockedConnection:
        self._lock.acquire()
        self._conn.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            self._conn.__exit__(exc_type, exc, tb)
        finally:
            self._lock.release()


class VaultIndex:
    def __init__(self, vault: Vault, db_path: Path | None = None) -> None:
        self.vault = vault
        self.db_path = db_path or (vault.root / RUNTIME / DB_NAME)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # MCP servers may call tools from worker threads: one connection behind a re-entrant lock.
        self.conn = _LockedConnection(sqlite3.connect(self.db_path, check_same_thread=False))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(_SCHEMA)
        ver = self.conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if ver is None or int(ver["value"]) != SCHEMA_VERSION:
            self.rebuild()

    # ------------------------------------------------------------------ lifecycle
    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> VaultIndex:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def rebuild(self) -> RefreshResult:
        with self.conn:
            for t in ("notes", "note_domains", "note_tags", "links", "parse_errors", "notes_fts"):
                self.conn.execute(f"DELETE FROM {t}")
            self.conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
        return self.refresh()

    # ------------------------------------------------------------------ refresh
    def refresh(self) -> RefreshResult:
        known: dict[str, tuple[int, int]] = {
            r["path"]: (r["mtime_ns"], r["size"])
            for r in self.conn.execute("SELECT path, mtime_ns, size FROM notes")
        }
        known_err: dict[str, tuple[int, int]] = {
            r["path"]: (r["mtime_ns"], r["size"])
            for r in self.conn.execute("SELECT path, mtime_ns, size FROM parse_errors")
        }
        seen: set[str] = set()
        added = updated = unchanged = errors = 0
        with self.conn:
            for p in self.vault.iter_note_paths():
                rel = self.vault.rel(p)
                seen.add(rel)
                st = p.stat()
                sig = (st.st_mtime_ns, st.st_size)
                if known.get(rel) == sig or known_err.get(rel) == sig:
                    unchanged += 1
                    continue
                existed = rel in known or rel in known_err
                try:
                    self._upsert(p, rel, sig)
                except NoteParseError as exc:
                    self._delete(rel)
                    self.conn.execute(
                        "INSERT OR REPLACE INTO parse_errors(path, message, mtime_ns, size) "
                        "VALUES (?,?,?,?)",
                        (rel, str(exc).split(": ", 1)[-1], sig[0], sig[1]),
                    )
                    errors += 1
                    continue
                if existed:
                    updated += 1
                else:
                    added += 1
            removed = 0
            for rel in set(known) | set(known_err):
                if rel not in seen:
                    self._delete(rel)
                    removed += 1
        return RefreshResult(added, updated, removed, unchanged, errors)

    def _delete(self, rel: str) -> None:
        for t in ("notes", "note_domains", "note_tags", "parse_errors", "notes_fts"):
            self.conn.execute(f"DELETE FROM {t} WHERE path=?", (rel,))
        self.conn.execute("DELETE FROM links WHERE src=?", (rel,))

    def _upsert(self, path: Path, rel: str, sig: tuple[int, int]) -> None:
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise NoteParseError(f"not UTF-8: {exc}", path) from None
        note = parse_note(text, path=path)
        fm = note.frontmatter
        self._delete(rel)
        self.conn.execute(
            "INSERT INTO notes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rel,
                fm.id,
                note.title,
                fm.type.value,
                fm.status.value,
                fm.origin.value,
                fm.confidence.value,
                fm.classification.value,
                int(fm.share),
                fm.created.isoformat(),
                fm.reviewed.isoformat() if fm.reviewed else None,
                json.dumps(fm.domain),
                json.dumps(fm.tags),
                json.dumps(fm.source, ensure_ascii=False),
                sig[0],
                sig[1],
                hashlib.sha256(raw).hexdigest(),
                note.body,
            ),
        )
        self.conn.executemany(
            "INSERT OR IGNORE INTO note_domains VALUES (?,?)", [(rel, d) for d in fm.domain]
        )
        self.conn.executemany(
            "INSERT OR IGNORE INTO note_tags VALUES (?,?)", [(rel, t) for t in fm.tags]
        )
        self.conn.executemany(
            "INSERT OR IGNORE INTO links VALUES (?,?)", [(rel, lk.target) for lk in note.links]
        )
        self.conn.execute(
            "INSERT INTO notes_fts(path, title, body, tags) VALUES (?,?,?,?)",
            (rel, note.title, note.body, " ".join(fm.tags)),
        )

    # ------------------------------------------------------------------ queries
    def count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0])

    def parse_errors(self) -> list[tuple[str, str]]:
        return [
            (r["path"], r["message"])
            for r in self.conn.execute("SELECT path, message FROM parse_errors ORDER BY path")
        ]

    def get(self, ref: str) -> IndexedNote | None:
        """Look up by Vault-relative path (with or without .md) or by note id."""
        for sql, arg in (
            ("SELECT * FROM notes WHERE path=?", ref),
            ("SELECT * FROM notes WHERE path=?", ref + ".md"),
            ("SELECT * FROM notes WHERE id=?", ref),
        ):
            r = self.conn.execute(sql, (arg,)).fetchone()
            if r is not None:
                return _row_to_note(r)
        return None

    def body(self, path: str) -> str | None:
        r = self.conn.execute("SELECT body FROM notes WHERE path=?", (path,)).fetchone()
        return None if r is None else str(r["body"])

    def _filters(
        self,
        *,
        domain: str | None = None,
        status: str | None = None,
        type_: str | None = None,
        origin: str | None = None,
        classification: str | None = None,
        tag: str | None = None,
        share: bool | None = None,
        exclude_confidential: bool = False,
        created_from: str | None = None,
        created_to: str | None = None,
        reviewed_from: str | None = None,
        reviewed_to: str | None = None,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        args: list[Any] = []
        for col, val in (
            ("status", status),
            ("type", type_),
            ("origin", origin),
            ("classification", classification),
        ):
            if val is not None:
                clauses.append(f"n.{col}=?")
                args.append(val)
        if share is not None:
            clauses.append("n.share=?")
            args.append(int(share))
        if exclude_confidential:
            clauses.append("n.classification<>'confidential'")
        if domain is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM note_domains d WHERE d.path=n.path AND d.domain=?)"
            )
            args.append(domain)
        if tag is not None:
            clauses.append("EXISTS (SELECT 1 FROM note_tags t WHERE t.path=n.path AND t.tag=?)")
            args.append(tag)
        for col, lo, hi in (
            ("created", created_from, created_to),
            ("reviewed", reviewed_from, reviewed_to),
        ):
            if lo is not None:
                clauses.append(f"n.{col}>=?")
                args.append(lo)
            if hi is not None:
                clauses.append(f"n.{col}<=?")
                args.append(hi)
        return (" AND ".join(clauses) if clauses else "1=1"), args

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        domain: str | None = None,
        status: str | None = None,
        type_: str | None = None,
        exclude_confidential: bool = False,
    ) -> list[SearchHit]:
        match, short = fts_query(query)
        where, args = self._filters(
            domain=domain, status=status, type_=type_, exclude_confidential=exclude_confidential
        )
        limit = max(1, min(int(limit), 200))
        like_sql = ""
        like_args: list[Any] = []
        for t in short:
            like_sql += " AND (n.title LIKE ? ESCAPE '\\' OR n.body LIKE ? ESCAPE '\\')"
            like_args += [_like(t), _like(t)]
        if match is not None:
            rows = self.conn.execute(
                f"""
                SELECT n.*, snippet(notes_fts, 2, '[', ']', '…', 12) AS snip,
                       bm25(notes_fts, 4.0, 1.0, 2.0) AS rank
                FROM notes_fts JOIN notes n ON n.path = notes_fts.path
                WHERE notes_fts MATCH ? AND {where}{like_sql}
                ORDER BY rank LIMIT ?
                """,
                [match, *args, *like_args, limit],
            ).fetchall()
            return [SearchHit(_row_to_note(r), r["snip"], float(r["rank"])) for r in rows]
        rows = self.conn.execute(
            f"SELECT n.*, substr(n.body, 1, 120) AS snip, 0.0 AS rank FROM notes n "
            f"WHERE {where}{like_sql} ORDER BY n.reviewed DESC, n.created DESC LIMIT ?",
            [*args, *like_args, limit],
        ).fetchall()
        return [SearchHit(_row_to_note(r), r["snip"].replace("\n", " "), 0.0) for r in rows]

    def query(
        self, *, limit: int = 100, order: str = "created", **filters: Any
    ) -> list[IndexedNote]:
        where, args = self._filters(**filters)
        if order not in ("created", "reviewed", "title", "path"):
            raise ValueError(f"unsupported order {order!r}")
        limit = max(1, min(int(limit), 1000))
        rows = self.conn.execute(
            f"SELECT * FROM notes n WHERE {where} ORDER BY n.{order} DESC, n.path LIMIT ?",
            [*args, limit],
        ).fetchall()
        return [_row_to_note(r) for r in rows]

    def domains(self) -> dict[str, int]:
        return {
            r["domain"]: int(r["c"])
            for r in self.conn.execute(
                "SELECT domain, COUNT(*) c FROM note_domains GROUP BY domain ORDER BY domain"
            )
        }

    def backlinks(self, title_or_stem: str) -> list[str]:
        return [
            r["src"]
            for r in self.conn.execute(
                "SELECT src FROM links WHERE target=? ORDER BY src", (title_or_stem,)
            )
        ]

    # ------------------------------------------------------------------ stats (index-based §11.1)
    def stats(self, today: date) -> Stats:
        rows = self.conn.execute(
            "SELECT path, status, origin, type, created, reviewed, domains FROM notes"
        ).fetchall()
        total = len(rows)
        stems = {Path(r["path"]).stem for r in rows}
        inbound: Counter[str] = Counter()
        outgoing: Counter[str] = Counter()
        for lk in self.conn.execute("SELECT src, target FROM links"):
            outgoing[lk["src"]] += 1
            if lk["target"] in stems:
                inbound[lk["target"]] += 1
        inbox = [r for r in rows if r["path"].startswith(INBOX + "/")]
        dwell = (
            sum((today - date.fromisoformat(r["created"])).days for r in inbox) / len(inbox)
            if inbox
            else None
        )
        week_ago = (today - timedelta(days=7)).isoformat()
        verified_week = sum(
            1
            for r in rows
            if r["status"] == "verified"
            and r["reviewed"]
            and week_ago < r["reviewed"] <= today.isoformat()
        )
        ai = [r for r in rows if r["origin"] in ("claude", "mixed")]
        promo = (sum(1 for r in ai if r["status"] == "verified") / len(ai)) if ai else None
        orphans = sum(
            1 for r in rows if outgoing[r["path"]] == 0 and inbound[Path(r["path"]).stem] == 0
        )
        cross = sum(1 for r in rows if len(json.loads(r["domains"])) >= 2)
        month_ago = (today - timedelta(days=30)).isoformat()
        outputs = sum(
            1
            for r in rows
            if r["path"].startswith(OUTPUTS + "/") and month_ago < r["created"] <= today.isoformat()
        )
        return Stats(
            as_of=today.isoformat(),
            notes=total,
            inbox_dwell_days=round(dwell, 2) if dwell is not None else None,
            verified_per_week=verified_week,
            ai_promotion_rate=round(promo, 3) if promo is not None else None,
            orphan_ratio=round(orphans / total, 3) if total else 0.0,
            cross_domain_ratio=round(cross / total, 3) if total else 0.0,
            outputs_per_month=outputs,
            by_status=dict(sorted(Counter(r["status"] for r in rows).items())),
            by_origin=dict(sorted(Counter(r["origin"] for r in rows).items())),
            by_type=dict(sorted(Counter(r["type"] for r in rows).items())),
            by_domain=self.domains(),
            parse_errors=len(self.parse_errors()),
        )


def open_index(vault: Vault, *, refresh: bool = True) -> VaultIndex:
    idx = VaultIndex(vault)
    if refresh:
        idx.refresh()
    return idx


def iter_chunks(items: Sequence[str], n: int) -> Iterable[Sequence[str]]:
    for i in range(0, len(items), n):
        yield items[i : i + n]


__all__ = [
    "DB_NAME",
    "IndexedNote",
    "RefreshResult",
    "SearchHit",
    "VaultIndex",
    "fts_query",
    "open_index",
]
_ = os  # keep os for potential platform tweaks (documented no-op)
