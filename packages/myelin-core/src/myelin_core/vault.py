"""Vault 스캔과 링크 그래프 — doctor·stats 공용. 파일은 읽기만 한다."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from myelin_core.errors import NoteParseError
from myelin_core.note import Note, WikiLink, parse_note_file

# 지식 노트로 검사하는 폴더 (ADR-0005 §6, P3 보정).
# 제외: 90_System(템플릿·사전), _patches, 50_Journal(일일·리뷰 노트), 80_Outputs(산출물 문서),
#       00_Inbox/clips(웹 클리핑 원문), 숨김 폴더 — 이들은 노트 스키마를 따르지 않는다.
CONTENT_DIRS = (
    "00_Inbox",
    "10_Domains",
    "20_Projects",
    "30_Resources",
    "40_IP",
    "99_Archive",
)
SKIP_PREFIXES = ("00_Inbox/clips/",)
INBOX = "00_Inbox/"
AI_DRAFTS = "00_Inbox/ai-drafts/"


@dataclass
class VaultScan:
    root: Path
    notes: list[Note] = field(default_factory=list)
    errors: list[tuple[str, NoteParseError]] = field(default_factory=list)
    raw_captures: list[str] = field(default_factory=list)  # frontmatter 없는 Inbox 메모
    files: set[str] = field(default_factory=set)  # 모든 비숨김 파일의 이름(소문자)


def _is_raw_capture(rel: str, err: NoteParseError) -> bool:
    """Inbox에 frontmatter 없이 빠르게 적은 메모는 오류가 아니라 '처리 전 원료'다.

    단 Claude가 쓰는 ai-drafts 는 항상 스키마를 지켜야 한다.
    """
    return (
        rel.startswith(INBOX)
        and not rel.startswith(AI_DRAFTS)
        and err.issues[0].code == "missing_frontmatter"
    )


@dataclass
class LinkGraph:
    outgoing: dict[str, set[str]] = field(default_factory=dict)  # 노트 path -> 대상 노트 path
    incoming: dict[str, set[str]] = field(default_factory=dict)
    broken: dict[str, list[WikiLink]] = field(default_factory=dict)


def _hidden(rel: Path) -> bool:
    return any(part.startswith(".") for part in rel.parts)


def scan_vault(root: Path) -> VaultScan:
    scan = VaultScan(root=root)
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if not path.is_file() or _hidden(rel):
            continue
        scan.files.add(path.name.lower())
        posix = rel.as_posix()
        if (
            path.suffix != ".md"
            or rel.parts[0] not in CONTENT_DIRS
            or posix.startswith(SKIP_PREFIXES)
        ):
            continue
        try:
            scan.notes.append(parse_note_file(path, root=root))
        except NoteParseError as err:
            if _is_raw_capture(posix, err):
                scan.raw_captures.append(posix)
            else:
                scan.errors.append((posix, err))
    return scan


def _note_keys(note: Note) -> list[str]:
    assert note.path is not None
    no_ext = note.path.removesuffix(".md").lower()
    return [no_ext, Path(no_ext).name]


def build_graph(scan: VaultScan) -> LinkGraph:
    index: dict[str, list[str]] = {}
    for note in scan.notes:
        for key in _note_keys(note):
            index.setdefault(key, []).append(note.path or "")
    graph = LinkGraph()
    for note in scan.notes:
        src = note.path or ""
        graph.outgoing.setdefault(src, set())
        graph.incoming.setdefault(src, set())
    for note in scan.notes:
        src = note.path or ""
        for link in note.all_links:
            key = link.target.removesuffix(".md").lower()
            targets = index.get(key)
            if targets:
                # Obsidian처럼 경로가 같은 이름이 여럿이면 가장 짧은 경로를 고른다
                dst = sorted(targets, key=lambda p: (len(p), p))[0]
                if dst != src:
                    graph.outgoing[src].add(dst)
                    graph.incoming[dst].add(src)
            elif Path(link.target).suffix and Path(link.target).name.lower() in scan.files:
                continue  # 첨부 파일 링크
            else:
                graph.broken.setdefault(src, []).append(link)
    return graph
