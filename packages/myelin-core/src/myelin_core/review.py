"""Review Gate — 사람이 노트를 verified 로 승격하거나 반려한다 (명세 §3 HITL, ADR-0008).

이 모듈은 '노트는 절대 수정하지 않는다'(ADR-0005)의 **유일한 예외**다. 그래서 범위를 좁게 둔다:
- frontmatter의 `status`·`reviewed` 두 키만 바꾼다. 본문은 바이트 그대로 둔다.
- Inbox의 노트는 Domain 폴더로, 반려된 노트는 `99_Archive/rejected/` 로 옮긴다. 대상이 있으면 거부.
- 호출자는 화면에 보여 준 노트의 id를 함께 보낸다 — 다르면 거부 (보지 않은 노트를 승격하지 않는다).
- 판단할 수 없으면 거부한다: 깨진 frontmatter, 심볼릭 링크, Vault 밖 경로,
  미검증 AI 노트를 링크하는 노트.
"""

from __future__ import annotations

import io
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from ruamel.yaml import YAML

from myelin_core.config import load_config
from myelin_core.errors import Issue, MyelinError, NoteParseError
from myelin_core.frontmatter import Origin, Status
from myelin_core.note import Note, parse_note
from myelin_core.vault import AI_DRAFTS, INBOX, build_graph, is_note_path, scan_vault

REJECTED_DIR = "99_Archive/rejected"
REVIEWABLE = (Status.DRAFT, Status.UNVERIFIED)
_BOM = chr(0xFEFF)


class ReviewError(MyelinError):
    """승격·반려를 할 수 없음 (fail-closed)."""


@dataclass(frozen=True)
class ReviewItem:
    path: str
    id: str
    title: str
    type: str
    status: str
    origin: str
    domain: list[str]
    classification: str
    created: str
    ai: bool


@dataclass(frozen=True)
class Change:
    """한 노트에 대한 승격/반려 계획. `src == dst` 이면 제자리 수정."""

    action: str  # "promote" | "reject"
    note_id: str
    title: str
    src: str
    dst: str
    original: str
    text: str

    @property
    def paths(self) -> list[str]:
        return sorted({self.src, self.dst})


def review_queue(vault: Path) -> list[ReviewItem]:
    """검토 대기 노트 (draft·unverified). AI 초안이 먼저, 그다음 오래된 순."""
    items: list[ReviewItem] = []
    for note in scan_vault(vault).notes:
        fm = note.frontmatter
        if fm.status not in REVIEWABLE:
            continue
        items.append(
            ReviewItem(
                path=note.path or "",
                id=fm.id,
                title=note.title,
                type=fm.type.value,
                status=fm.status.value,
                origin=fm.origin.value,
                domain=list(fm.domain),
                classification=fm.classification.value,
                created=fm.created.isoformat(),
                ai=fm.origin is not Origin.HUMAN,
            )
        )
    return sorted(items, key=lambda i: (not i.ai, i.created, i.path))


# ── 경로·읽기 ────────────────────────────────────────────────────────────
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _symlink_free(vault: Path, rel: str) -> None:
    """`rel` 의 경로 구성요소 중 존재하는 것이 하나라도 심볼릭 링크면 거부."""
    probe = vault
    for part in PurePosixPath(rel).parts:
        probe = probe / part
        if probe.is_symlink():
            raise ReviewError("심볼릭 링크는 다루지 않습니다", [Issue("path", rel, "symlink")])


def safe_note_path(vault: Path, rel: str) -> Path:
    """Vault 안의 실제 지식 노트 파일만 허용한다."""
    bad = ReviewError("노트 경로가 올바르지 않습니다", [Issue("path", repr(rel), "bad_path")])
    pure = PurePosixPath(rel)
    if not rel or pure.is_absolute() or ".." in pure.parts or "\\" in rel or _CONTROL.search(rel):
        raise bad
    if not is_note_path(Path(*pure.parts)):
        raise bad
    target = vault / Path(*pure.parts)
    _symlink_free(vault, rel)
    if not target.is_file() or not target.resolve().is_relative_to(vault.resolve()):
        raise ReviewError("노트를 찾을 수 없습니다", [Issue("path", rel, "not_found")])
    return target


def _read_raw(path: Path) -> str:
    """줄바꿈 변환 없이 읽는다 (CRLF·BOM 그대로)."""
    return path.read_bytes().decode("utf-8")


def _write_raw(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def read_note(vault: Path, rel: str) -> tuple[Note, str]:
    path = safe_note_path(vault, rel)
    try:
        text = _read_raw(path)
        note = parse_note(text, source=rel, title=path.stem)
    except (UnicodeDecodeError, NoteParseError) as exc:
        issues = exc.issues if isinstance(exc, NoteParseError) else [Issue(rel, "UTF-8 아님")]
        raise ReviewError("frontmatter가 올바르지 않아 판단할 수 없습니다", issues) from exc
    return note, text


# ── frontmatter 두 키만 바꾸기 ──────────────────────────────────────────
def _rt() -> YAML:
    rt = YAML(typ="rt")
    rt.preserve_quotes = True
    rt.width = 4096
    rt.indent(mapping=2, sequence=4, offset=2)
    return rt


def set_fields(text: str, rel: str, fields: dict[str, Any]) -> str:
    """frontmatter의 `fields` 만 바꾼 새 텍스트.

    본문은 닫는 `---` 줄부터 **원래 문자 그대로** 붙인다 (CRLF·BOM 포함). frontmatter 구획도
    원래 줄바꿈 방식(LF/CRLF)으로 다시 쓴다. 다른 키·순서·주석은 ruamel round-trip으로 보존.
    """
    bom = _BOM if text.startswith(_BOM) else ""
    lines = text[len(bom) :].splitlines(keepends=True)
    close = next((i for i, line in enumerate(lines[1:], 1) if line.strip() in ("---", "...")), None)
    if not lines or lines[0].strip() != "---" or close is None:
        raise ReviewError("frontmatter 구획을 찾을 수 없습니다", [Issue(rel, "---", "no_fm")])
    eol = "\r\n" if lines[0].endswith("\r\n") else "\n"
    rt = _rt()
    data = rt.load("".join(lines[1:close]).replace("\r\n", "\n"))
    for key, value in fields.items():
        data[key] = value
    buf = io.StringIO()
    rt.dump(data, buf)
    tail = "".join(lines[close:])  # 닫는 줄 + 본문, 원문 그대로
    new = bom + lines[0] + buf.getvalue().replace("\n", eol) + tail
    # 결과 검증: 다시 읽히고, id가 같고, 본문 문자열이 원문 그대로여야 한다
    before = parse_note(text, source=rel)
    after = parse_note(new, source=rel)
    if after.frontmatter.id != before.frontmatter.id or not new.endswith(tail):
        raise ReviewError("frontmatter 변경 검증 실패", [Issue(rel, "id/본문 변경", "verify")])
    return new


# ── 계획 ─────────────────────────────────────────────────────────────────
def _common(vault: Path, rel: str, expected_id: str, today: date) -> tuple[Note, str]:
    note, text = read_note(vault, rel)
    fm = note.frontmatter
    if fm.id != expected_id:
        raise ReviewError(
            "화면의 노트와 파일이 다릅니다 — 새로고침 후 다시 확인하세요",
            [Issue("id", f"기대 {expected_id}, 실제 {fm.id}", "id_mismatch")],
        )
    if fm.status not in REVIEWABLE:
        raise ReviewError(
            "검토 대기 상태가 아닙니다", [Issue("status", fm.status.value, "not_reviewable")]
        )
    if today < fm.created:
        raise ReviewError("검토일이 작성일보다 빠릅니다", [Issue("created", str(fm.created))])
    return note, text


def _domain_dest(vault: Path, note: Note, rel: str) -> str:
    cfg = load_config(vault)
    domains = [d for d in note.frontmatter.domain if d in cfg.domains.all()]
    if not domains:
        raise ReviewError(
            "옮길 Domain을 정할 수 없습니다",
            [Issue("domain", f"{rel}: 이 Vault의 Domain({', '.join(cfg.domains.all())})이 없음")],
        )
    folder = f"10_Domains/{domains[0]}"
    _symlink_free(vault, folder)
    if not (vault / folder).is_dir():
        raise ReviewError("Domain 폴더가 없습니다", [Issue(folder, "없음", "missing_dir")])
    return f"{folder}/{PurePosixPath(rel).name}"


def _unverified_ai_targets(vault: Path, rel: str) -> list[str]:
    """승격하면 'verified → 미검증 AI 노트' 링크가 생기는 대상 (doctor fail-closed 규칙)."""
    scan = scan_vault(vault)
    graph = build_graph(scan)
    by_path = {n.path: n for n in scan.notes}
    out: list[str] = []
    for dst in sorted(graph.outgoing.get(rel, set())):
        target = by_path.get(dst)
        if (
            target is not None
            and target.frontmatter.origin is not Origin.HUMAN
            and target.frontmatter.status is not Status.VERIFIED
        ):
            out.append(dst)
    return out


def _check_dest(vault: Path, dst: str) -> None:
    """이동 대상: 경로에 심볼릭 링크가 없고, 같은 이름이 없어야 한다 (덮어쓰기 금지)."""
    _symlink_free(vault, dst)
    target = vault / dst
    if target.exists() or target.is_symlink():
        raise ReviewError(
            "옮길 자리에 같은 이름이 있습니다", [Issue(dst, "덮어쓰지 않음", "exists")]
        )


def plan_promote(vault: Path, rel: str, expected_id: str, today: date) -> Change:
    note, text = _common(vault, rel, expected_id, today)
    policy = note.frontmatter.policy_issues()
    if policy:
        raise ReviewError("정책상 모순이 있는 노트입니다", policy)
    pending = _unverified_ai_targets(vault, rel)
    if pending:
        raise ReviewError(
            "미검증 AI 노트를 링크합니다 — 그 노트를 먼저 검토하세요",
            [Issue(p, "origin≠human, status≠verified", "links_unverified_ai") for p in pending],
        )
    dst = _domain_dest(vault, note, rel) if rel.startswith(INBOX) else rel
    if dst != rel:
        _check_dest(vault, dst)
    new = set_fields(text, rel, {"status": Status.VERIFIED.value, "reviewed": today})
    return Change("promote", note.frontmatter.id, note.title, rel, dst, text, new)


def plan_reject(vault: Path, rel: str, expected_id: str, today: date) -> Change:
    note, text = _common(vault, rel, expected_id, today)
    dst = f"{REJECTED_DIR}/{PurePosixPath(rel).name}"
    _check_dest(vault, dst)
    new = set_fields(text, rel, {"status": Status.DEPRECATED.value, "reviewed": today})
    return Change("reject", note.frontmatter.id, note.title, rel, dst, text, new)


# ── 적용·되돌리기 ───────────────────────────────────────────────────────
def apply_change(vault: Path, change: Change) -> None:
    src = vault / change.src
    _symlink_free(vault, change.src)
    if _read_raw(src) != change.original:
        raise ReviewError("계획 이후 파일이 바뀌었습니다", [Issue(change.src, "변경됨", "stale")])
    data = change.text.encode("utf-8")
    if change.dst == change.src:
        # 임의 이름 + O_EXCL 임시 파일 (미리 심어 둔 링크를 따라가지 않는다)
        fd, tmp = tempfile.mkstemp(dir=src.parent, prefix=f".{src.name}.", suffix=".myelin-tmp")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, src)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return
    _check_dest(vault, change.dst)
    dst = vault / change.dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    _symlink_free(vault, change.dst)  # mkdir 이후 다시 확인
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(dst, flags, 0o644)  # 덮어쓰기 금지 · 링크 따라가지 않음
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    src.unlink()


def revert_change(vault: Path, change: Change) -> None:
    """apply_change 를 되돌린다 (commit 실패 시) — 원래 바이트 그대로."""
    _write_raw(vault / change.src, change.original)
    if change.dst != change.src:
        (vault / change.dst).unlink(missing_ok=True)


def commit_message(change: Change) -> str:
    verb = "promote" if change.action == "promote" else "reject"
    where = change.src if change.src == change.dst else f"{change.src} -> {change.dst}"
    return (
        f"myelin: {verb} {change.note_id} ({change.title})\n\n{where}\nvia MYELIN Hub Review Gate"
    )


def is_ai_draft(rel: str) -> bool:
    return rel.startswith(AI_DRAFTS)
