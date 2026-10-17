"""`myelin doctor` — Vault 무결성 점검 (명세 §6, P2-T7).

규칙
- error  : config · schema · duplicate_id · unknown_domain · share_confidential · failclosed_link
           · location(vault_in_source)
- warning: broken_link · orphan · inbox_stale · location(vault_in_git, public_remote)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from myelin_core.config import ConfigError, load_config
from myelin_core.frontmatter import NoteType, Origin, Status
from myelin_core.lock import load_lock
from myelin_core.safety import location_issues
from myelin_core.vault import INBOX, build_graph, scan_vault

Severity = Literal["error", "warning"]
INBOX_MAX_DAYS = 7
ORPHAN_EXEMPT = {NoteType.MOC, NoteType.FLEETING}


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    rule: str
    severity: Severity
    msg: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.rule}: {self.path} — {self.msg}"


def run_doctor(
    vault: Path, today: date | None = None, check_location: bool = True
) -> list[Finding]:
    today = today or date.today()
    out: list[Finding] = []

    if check_location:
        for severity, issue in location_issues(vault):
            out.append(Finding(issue.loc, "location", severity, issue.msg))  # type: ignore[arg-type]

    try:
        cfg = load_config(vault)
        lock = load_lock(vault)
    except ConfigError as err:
        out += [Finding(i.loc, "config", "error", i.msg) for i in err.issues]
        return sorted(out)
    known = lock.domain_ids()
    out += [Finding(i.loc, "config", "error", i.msg) for i in cfg.missing_domains(known)]

    scan = scan_vault(vault)
    for rel, parse_err in scan.errors:
        first = parse_err.issues[0]
        n_more = len(parse_err.issues) - 1
        extra = f" (+{n_more})" if n_more else ""
        out.append(Finding(rel, "schema", "error", f"{first}{extra}"))

    by_id: dict[str, list[str]] = {}
    for note in scan.notes:
        by_id.setdefault(note.frontmatter.id, []).append(note.path or "")
    for note_id, paths in by_id.items():
        if len(paths) > 1:
            for p in paths:
                out.append(
                    Finding(
                        p,
                        "duplicate_id",
                        "error",
                        f"id {note_id} 가 {len(paths)}개 노트에 있습니다",
                    )
                )

    graph = build_graph(scan)
    notes_by_path = {n.path or "": n for n in scan.notes}
    stale_before = today - timedelta(days=INBOX_MAX_DAYS)

    for note in scan.notes:
        path = note.path or ""
        fm = note.frontmatter
        for d in fm.domain:
            if d not in known:
                out.append(Finding(path, "unknown_domain", "error", f"설치되지 않은 Domain: {d}"))
        for issue in fm.policy_issues():
            out.append(Finding(path, "share_confidential", "error", issue.msg))
        if fm.status is Status.VERIFIED:
            for dst in sorted(graph.outgoing[path]):
                target = notes_by_path[dst].frontmatter
                if target.origin is Origin.CLAUDE and target.status is not Status.VERIFIED:
                    out.append(
                        Finding(
                            path,
                            "failclosed_link",
                            "error",
                            f"verified 노트가 검증되지 않은 AI 초안을 링크합니다: {dst}",
                        )
                    )
        for link in graph.broken.get(path, []):
            out.append(Finding(path, "broken_link", "warning", f"대상 없음: [[{link.target}]]"))
        in_inbox = path.startswith(INBOX)
        if (
            not in_inbox
            and fm.type not in ORPHAN_EXEMPT
            and not graph.outgoing[path]
            and not graph.incoming[path]
        ):
            out.append(Finding(path, "orphan", "warning", "들어오거나 나가는 링크가 없습니다"))
        if in_inbox and fm.created < stale_before:
            age = (today - fm.created).days
            out.append(
                Finding(
                    path,
                    "inbox_stale",
                    "warning",
                    f"Inbox에 {age}일째 — {INBOX_MAX_DAYS}일 안에 처리하세요",
                )
            )
    return sorted(set(out))
