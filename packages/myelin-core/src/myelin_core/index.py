"""Vault 검색 색인 — SQLite FTS5 trigram (ADR-0006).

- 위치: `<vault>/.myelin/index.db` (Vault .gitignore 대상, 공유되지 않음)
- 범위: doctor와 같은 '지식 노트' (`vault.is_note_path`)
- 보호 노트(ReadPolicy)는 **내용을 저장하지 않는다** — 경로·변경 시각만 기록해 재검사를 피한다.
- 증분 갱신: (mtime_ns, size) 가 바뀐 파일만 다시 읽는다. 정책이 바뀌면 전부 다시 만든다.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from myelin_core.errors import NoteParseError
from myelin_core.note import parse_note_file
from myelin_core.policy import ReadPolicy
from myelin_core.vault import is_note_path, iter_files

INDEX_FILE = ".myelin/index.db"
SCHEMA_VERSION = "1"
MIN_TRIGRAM = 3
THROTTLE_SECONDS = 2.0

DDL = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notes(
    rowid INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    mtime_ns INTEGER NOT NULL,
    size INTEGER NOT NULL,
    indexed INTEGER NOT NULL,          -- 1 = 검색 가능, 0 = 보호 노트·파싱 실패 (내용 없음)
    reason TEXT,
    id TEXT, title TEXT, type TEXT, status TEXT, origin TEXT, classification TEXT,
    domains TEXT, tags TEXT, created TEXT, frontmatter TEXT, body TEXT
);
CREATE INDEX IF NOT EXISTS notes_id ON notes(id);
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(title, body, tags, tokenize='trigram');
"""

SUMMARY_COLUMNS = "n.path, n.title, n.id, n.type, n.status, n.origin, n.domains, n.created"


@dataclass(frozen=True)
class RefreshStats:
    added: int = 0
    updated: int = 0
    removed: int = 0
    protected: int = 0
    invalid: int = 0
    skipped_refresh: bool = False


def _summary(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "path": row["path"],
        "title": row["title"],
        "id": row["id"],
        "type": row["type"],
        "status": row["status"],
        "origin": row["origin"],
        "domain": json.loads(row["domains"]),
        "created": row["created"],
    }


def _snippet(text: str, needle: str, width: int = 60) -> str:
    pos = text.lower().find(needle.lower())
    if pos < 0:
        return text[: width * 2].replace("\n", " ").strip()
    start, end = max(0, pos - width), min(len(text), pos + len(needle) + width)
    body = text[start:end].replace("\n", " ").strip()
    return ("…" if start else "") + body + ("…" if end < len(text) else "")


class VaultIndex:
    def __init__(self, vault: Path, policy: ReadPolicy) -> None:
        self.vault = vault
        self.policy = policy
        self.db_path = vault / INDEX_FILE
        self._last_refresh = 0.0

    # ── 연결 ───────────────────────────────────────────────────────────
    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        try:
            yield con
        finally:
            con.close()

    def _signature(self) -> str:
        return f"{SCHEMA_VERSION}|ip={self.policy.ip_local}|conf={self.policy.confidential_local}"

    def _ensure_schema(self, con: sqlite3.Connection) -> None:
        con.executescript(DDL)
        row = con.execute("SELECT value FROM meta WHERE key='signature'").fetchone()
        if row is None or row["value"] != self._signature():
            # 스키마·정책이 바뀌었다 → 전부 다시 만든다 (기존 내용을 믿을 수 없다)
            con.executescript("DELETE FROM notes; DELETE FROM notes_fts;")
            con.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES('signature', ?)",
                (self._signature(),),
            )
            con.commit()

    # ── 갱신 ───────────────────────────────────────────────────────────
    def refresh(self, force: bool = False) -> RefreshStats:
        now = time.monotonic()
        if not force and now - self._last_refresh < THROTTLE_SECONDS:
            return RefreshStats(skipped_refresh=True)
        current: dict[str, tuple[Path, int, int]] = {}
        for path, rel_path in iter_files(self.vault):
            if is_note_path(rel_path):
                st = path.stat()
                current[rel_path.as_posix()] = (path, st.st_mtime_ns, st.st_size)

        added = updated = removed = protected = invalid = 0
        with self._connect() as con:
            self._ensure_schema(con)
            known = {
                r["path"]: (r["rowid"], r["mtime_ns"], r["size"])
                for r in con.execute("SELECT rowid, path, mtime_ns, size FROM notes")
            }
            for rel, (rowid, _, _) in known.items():
                if rel not in current:
                    con.execute("DELETE FROM notes WHERE rowid=?", (rowid,))
                    con.execute("DELETE FROM notes_fts WHERE rowid=?", (rowid,))
                    removed += 1
            for rel, (path, mtime_ns, size) in current.items():
                old = known.get(rel)
                if old is not None and old[1:] == (mtime_ns, size):
                    continue
                if old is not None:
                    con.execute("DELETE FROM notes WHERE rowid=?", (old[0],))
                    con.execute("DELETE FROM notes_fts WHERE rowid=?", (old[0],))
                    updated += 1
                else:
                    added += 1
                state = self._store(con, rel, path, mtime_ns, size)
                protected += state == "protected"
                invalid += state == "invalid"
            con.commit()
        self._last_refresh = time.monotonic()
        return RefreshStats(added, updated, removed, protected, invalid)

    def _store(
        self, con: sqlite3.Connection, rel: str, path: Path, mtime_ns: int, size: int
    ) -> str:
        def placeholder(reason: str) -> str:
            con.execute(
                "INSERT INTO notes(path, mtime_ns, size, indexed, reason) VALUES(?,?,?,0,?)",
                (rel, mtime_ns, size, reason),
            )
            return reason

        if self.policy.path_blocked(rel):
            return placeholder("protected")
        try:
            note = parse_note_file(path, root=self.vault)
        except NoteParseError:
            return placeholder("invalid")
        fm = note.frontmatter
        if self.policy.blocked(rel, fm.classification):
            return placeholder("protected")
        cur = con.execute(
            "INSERT INTO notes(path, mtime_ns, size, indexed, id, title, type, status, origin,"
            " classification, domains, tags, created, frontmatter, body)"
            " VALUES(?,?,?,1,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rel,
                mtime_ns,
                size,
                fm.id,
                note.title,
                fm.type.value,
                fm.status.value,
                fm.origin.value,
                fm.classification.value,
                json.dumps(fm.domain),
                json.dumps(fm.tags, ensure_ascii=False),
                fm.created.isoformat(),
                fm.model_dump_json(),
                note.body,
            ),
        )
        con.execute(
            "INSERT INTO notes_fts(rowid, title, body, tags) VALUES(?,?,?,?)",
            (cur.lastrowid, note.title, note.body, " ".join(fm.tags)),
        )
        return "indexed"

    # ── 조회 ───────────────────────────────────────────────────────────
    def search(
        self,
        query: str,
        domain: str | None = None,
        note_type: str | None = None,
        status: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        terms = [t.strip("\"'") for t in query.split() if t.strip("\"'")]
        if not terms:
            raise ValueError("검색어가 비어 있습니다")
        long_terms = [t for t in terms if len(t) >= MIN_TRIGRAM]
        short_terms = [t for t in terms if len(t) < MIN_TRIGRAM]

        where = ["n.indexed = 1"]
        params: list[Any] = []
        if long_terms:
            match = " AND ".join('"' + t.replace('"', '""') + '"' for t in long_terms)
            sql = (
                f"SELECT {SUMMARY_COLUMNS}, n.body, bm25(notes_fts) AS score "
                "FROM notes_fts JOIN notes n ON n.rowid = notes_fts.rowid "
            )
            where.append("notes_fts MATCH ?")
            params.append(match)
            order = "score"
        else:
            sql = f"SELECT {SUMMARY_COLUMNS}, n.body, 0.0 AS score FROM notes n "
            order = "n.created DESC, n.path"
        for t in short_terms:
            where.append("(n.title LIKE ? OR n.body LIKE ?)")
            params += [f"%{t}%", f"%{t}%"]
        self._filters(where, params, domain, note_type, status)
        sql += "WHERE " + " AND ".join(where) + f" ORDER BY {order} LIMIT ?"
        params.append(max(1, min(limit, 50)))
        with self._connect() as con:
            self._ensure_schema(con)
            rows = con.execute(sql, params).fetchall()
        out = []
        for r in rows:
            item = _summary(r)
            item["snippet"] = _snippet(r["body"], terms[0])
            item["score"] = round(-float(r["score"]), 3)
            out.append(item)
        return out

    @staticmethod
    def _filters(
        where: list[str],
        params: list[Any],
        domain: str | None,
        note_type: str | None,
        status: str | None,
    ) -> None:
        if domain:
            where.append("n.domains LIKE ?")
            params.append(f'%"{domain}"%')
        if note_type:
            where.append("n.type = ?")
            params.append(note_type)
        if status:
            where.append("n.status = ?")
            params.append(status)

    def query(
        self,
        domain: str | None = None,
        note_type: str | None = None,
        status: str | None = None,
        origin: str | None = None,
        tag: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        where = ["n.indexed = 1"]
        params: list[Any] = []
        self._filters(where, params, domain, note_type, status)
        if origin:
            where.append("n.origin = ?")
            params.append(origin)
        if tag:
            where.append("n.tags LIKE ?")
            params.append(f'%"{tag.lstrip("#")}"%')
        if created_after:
            where.append("n.created >= ?")
            params.append(created_after)
        if created_before:
            where.append("n.created <= ?")
            params.append(created_before)
        sql = (
            f"SELECT {SUMMARY_COLUMNS} FROM notes n WHERE {' AND '.join(where)} "
            "ORDER BY n.created DESC, n.path LIMIT ?"
        )
        params.append(max(1, min(limit, 200)))
        with self._connect() as con:
            self._ensure_schema(con)
            return [_summary(r) for r in con.execute(sql, params)]

    def get(self, path: str | None = None, note_id: str | None = None) -> dict[str, Any] | None:
        if (path is None) == (note_id is None):
            raise ValueError("path 와 id 중 하나만 지정하세요")
        column, value = ("path", path) if path is not None else ("id", note_id)
        with self._connect() as con:
            self._ensure_schema(con)
            rows = con.execute(
                f"SELECT {SUMMARY_COLUMNS}, n.frontmatter, n.body FROM notes n "
                f"WHERE n.indexed = 1 AND n.{column} = ? ORDER BY n.path",
                (value,),
            ).fetchall()
        if not rows:
            return None
        row = rows[0]
        item = _summary(row)
        item["frontmatter"] = json.loads(row["frontmatter"])
        item["body"] = row["body"]
        if len(rows) > 1:
            item["warning"] = f"같은 id를 가진 노트가 {len(rows)}개 있습니다 (myelin doctor 확인)"
        return item

    def domain_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        with self._connect() as con:
            self._ensure_schema(con)
            for (domains,) in con.execute("SELECT domains FROM notes WHERE indexed = 1"):
                for d in json.loads(domains):
                    counts[d] = counts.get(d, 0) + 1
        return counts

    def counts(self) -> dict[str, int]:
        with self._connect() as con:
            self._ensure_schema(con)
            rows = con.execute(
                "SELECT COALESCE(reason, 'indexed') AS k, COUNT(*) AS c FROM notes GROUP BY k"
            ).fetchall()
        return {r["k"]: r["c"] for r in rows}
