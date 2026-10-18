"""Review Gate 핵심 로직 — 승격·반려는 좁게, 판단 불가는 거부."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from myelin_core.doctor import run_doctor
from myelin_core.note import parse_note
from myelin_core.review import (
    ReviewError,
    apply_change,
    commit_message,
    is_ai_draft,
    plan_promote,
    plan_reject,
    read_note,
    revert_change,
    review_queue,
    set_fields,
)

Put = Callable[[str, str], str]
TODAY = date(2026, 10, 18)
AI = "00_Inbox/ai-drafts/WCET 예산.md"


def draft(
    note_id: str = "20261018-0900-wcet",
    *,
    status: str = "draft",
    origin: str = "claude",
    domain: str = "[AI-ML-AX]",
    body: str = "# WCET 예산\n\n본문 그대로.\n",
    extra: str = "",
) -> str:
    return (
        "---\n"
        f"id: {note_id}  # 불변\n"
        "type: evergreen\n"
        f"domain: {domain}\n"
        f"status: {status}\n"
        f"origin: {origin}\n"
        "created: 2026-10-17\n"
        f"{extra}"
        "tags: [rtos]\n"
        "---\n"
        f"{body}"
    )


def _code(exc: pytest.ExceptionInfo[ReviewError]) -> str:
    return exc.value.issues[0].code


def test_queue_orders_ai_first(vault: Path, put: Put) -> None:
    put("20_Projects/human.md", draft("20261016-0900-human", origin="human"))
    put(AI, draft())
    put("20_Projects/done.md", draft("20261016-0901-done", status="verified", origin="human"))
    queue = review_queue(vault)
    assert [i.path for i in queue] == [AI, "20_Projects/human.md"]
    assert queue[0].ai and not queue[1].ai
    assert queue[0].domain == ["AI-ML-AX"] and queue[0].status == "draft"


def test_promote_moves_ai_draft_into_domain(vault: Path, put: Put) -> None:
    original = draft(body="# WCET 예산\n\n본문 그대로.\n\n- [[없는 링크]]\n")
    put(AI, original)
    change = plan_promote(vault, AI, "20261018-0900-wcet", TODAY)
    assert change.dst == "10_Domains/AI-ML-AX/WCET 예산.md"
    apply_change(vault, change)
    assert not (vault / AI).exists()
    new = (vault / change.dst).read_text(encoding="utf-8")
    note = parse_note(new)
    assert note.frontmatter.status.value == "verified"
    assert note.frontmatter.reviewed == TODAY
    assert note.frontmatter.origin.value == "claude"  # 출처 유지
    assert new.split("---\n", 2)[2] == original.split("---\n", 2)[2]  # 본문 바이트 동일
    assert "# 불변" in new  # 주석 보존
    assert new.index("status:") < new.index("tags:")  # 키 순서 보존
    assert set(change.paths) == {AI, change.dst}
    assert "promote 20261018-0900-wcet" in commit_message(change)
    assert is_ai_draft(AI) and not is_ai_draft(change.dst)


def test_promote_in_place_outside_inbox(vault: Path, put: Put) -> None:
    rel = put("20_Projects/p.md", draft("20261016-0900-proj", origin="human"))
    change = plan_promote(vault, rel, "20261016-0900-proj", TODAY)
    assert change.src == change.dst == rel
    apply_change(vault, change)
    assert parse_note((vault / rel).read_text(encoding="utf-8")).frontmatter.status.value == (
        "verified"
    )
    assert not any(p.name.endswith("myelin-tmp") for p in (vault / "20_Projects").iterdir())


def test_reject_archives_as_deprecated(vault: Path, put: Put) -> None:
    put(AI, draft())
    change = plan_reject(vault, AI, "20261018-0900-wcet", TODAY)
    assert change.dst == "99_Archive/rejected/WCET 예산.md"
    apply_change(vault, change)
    fm = parse_note((vault / change.dst).read_text(encoding="utf-8")).frontmatter
    assert fm.status.value == "deprecated" and fm.reviewed == TODAY
    assert "reject" in commit_message(change)


def test_promoted_vault_stays_doctor_clean(vault: Path, put: Put) -> None:
    put(AI, draft(body="# WCET\n\n[[_MOC]]\n"))
    apply_change(vault, plan_promote(vault, AI, "20261018-0900-wcet", TODAY))
    errors = [f for f in run_doctor(vault, TODAY, check_location=False) if f.severity == "error"]
    assert errors == []


@pytest.mark.parametrize(
    ("rel", "code"),
    [
        ("", "bad_path"),
        ("/etc/passwd", "bad_path"),
        ("../outside.md", "bad_path"),
        ("00_Inbox/../myelin.yaml", "bad_path"),
        ("myelin.yaml", "bad_path"),
        ("90_System/taxonomy.md", "bad_path"),
        ("50_Journal/x.md", "bad_path"),
        ("00_Inbox\\ai-drafts\\x.md", "bad_path"),
        ("00_Inbox/ai-drafts/missing.md", "not_found"),
    ],
)
def test_rejects_bad_paths(vault: Path, rel: str, code: str) -> None:
    with pytest.raises(ReviewError) as exc:
        plan_promote(vault, rel, "20261018-0900-wcet", TODAY)
    assert _code(exc) == code


def test_rejects_symlink(vault: Path, put: Put, tmp_path: Path) -> None:
    outside = tmp_path / "secret.md"
    outside.write_text(draft(), encoding="utf-8")
    os.symlink(outside, vault / "00_Inbox/ai-drafts/link.md")
    with pytest.raises(ReviewError) as exc:
        plan_promote(vault, "00_Inbox/ai-drafts/link.md", "20261018-0900-wcet", TODAY)
    assert _code(exc) == "symlink"


@pytest.mark.parametrize(
    ("text", "expected_id", "today", "code"),
    [
        (draft(), "20261018-0900-other", TODAY, "id_mismatch"),
        (draft(status="verified"), "20261018-0900-wcet", TODAY, "not_reviewable"),
        (draft(status="deprecated"), "20261018-0900-wcet", TODAY, "not_reviewable"),
        (draft(), "20261018-0900-wcet", date(2026, 10, 1), "invalid"),
        (draft(domain="[NOPE]"), "20261018-0900-wcet", TODAY, "invalid"),
        (draft(domain="[]"), "20261018-0900-wcet", TODAY, "invalid"),
        (
            draft(extra="classification: confidential\nshare: true\n"),
            "20261018-0900-wcet",
            TODAY,
            "share_confidential",
        ),
        ("no frontmatter\n", "x", TODAY, "missing_frontmatter"),
        ("---\nid: [broken\n---\n", "x", TODAY, "yaml_syntax"),
    ],
)
def test_promote_refuses(
    vault: Path, put: Put, text: str, expected_id: str, today: date, code: str
) -> None:
    put(AI, text)
    with pytest.raises(ReviewError) as exc:
        plan_promote(vault, AI, expected_id, today)
    if code != "invalid":
        assert code in {i.code for i in exc.value.issues}


def test_promote_refuses_link_to_unverified_ai(vault: Path, put: Put) -> None:
    put("00_Inbox/ai-drafts/other.md", draft("20261018-0901-other"))
    put(AI, draft(body="# A\n\n[[other]]\n"))
    with pytest.raises(ReviewError) as exc:
        plan_promote(vault, AI, "20261018-0900-wcet", TODAY)
    assert _code(exc) == "links_unverified_ai"


def test_refuses_existing_destination(vault: Path, put: Put) -> None:
    put(AI, draft())
    put("10_Domains/AI-ML-AX/WCET 예산.md", "사용자 파일\n")
    with pytest.raises(ReviewError) as exc:
        plan_promote(vault, AI, "20261018-0900-wcet", TODAY)
    assert _code(exc) == "exists"
    put("99_Archive/rejected/WCET 예산.md", "사용자 파일\n")
    with pytest.raises(ReviewError):
        plan_reject(vault, AI, "20261018-0900-wcet", TODAY)
    assert (vault / "10_Domains/AI-ML-AX/WCET 예산.md").read_text(
        encoding="utf-8"
    ) == "사용자 파일\n"


def test_missing_domain_folder(vault: Path, put: Put) -> None:
    put(AI, draft(domain="[ROBOTICS-LEARNING]"))
    (vault / "10_Domains/ROBOTICS-LEARNING/_MOC.md").unlink()
    (vault / "10_Domains/ROBOTICS-LEARNING").rmdir()
    with pytest.raises(ReviewError) as exc:
        plan_promote(vault, AI, "20261018-0900-wcet", TODAY)
    assert _code(exc) == "missing_dir"


def test_stale_plan_and_revert(vault: Path, put: Put) -> None:
    put(AI, draft())
    change = plan_promote(vault, AI, "20261018-0900-wcet", TODAY)
    put(AI, draft(body="# 사용자가 그새 고침\n"))
    with pytest.raises(ReviewError) as exc:
        apply_change(vault, change)
    assert _code(exc) == "stale"
    put(AI, draft())
    apply_change(vault, change)
    revert_change(vault, change)
    assert (vault / AI).read_text(encoding="utf-8") == draft()
    assert not (vault / change.dst).exists()


def test_set_fields_crlf_and_bom(vault: Path) -> None:
    text = "\ufeff" + draft().replace("\n", "\r\n")
    new = set_fields(text, "x.md", {"status": "verified"})
    assert new.startswith("\ufeff---\r\nid:") and "status: verified\r\n" in new
    assert "\n" not in new.replace("\r\n", "")  # 줄바꿈 방식 유지
    assert new.endswith("---\r\n# WCET 예산\r\n\r\n본문 그대로.\r\n")
    with pytest.raises(ReviewError):
        set_fields("---\nid: x\n", "x.md", {"status": "verified"})


def test_promote_keeps_crlf_bytes(vault: Path) -> None:
    rel = "20_Projects/crlf.md"
    raw = draft("20261016-0900-crlf", origin="human").replace("\n", "\r\n").encode()
    (vault / rel).write_bytes(raw)
    change = plan_promote(vault, rel, "20261016-0900-crlf", TODAY)
    apply_change(vault, change)
    new = (vault / rel).read_bytes()
    assert new.count(b"\r\n") == raw.count(b"\r\n") + 1  # reviewed 줄만 추가
    assert new.split(b"---\r\n", 2)[2] == raw.split(b"---\r\n", 2)[2]
    revert_change(vault, change)
    assert (vault / rel).read_bytes() == raw


def test_planted_tmp_symlink_not_followed(vault: Path, put: Put, tmp_path: Path) -> None:
    rel = put("20_Projects/t.md", draft("20261016-0900-tmp", origin="human"))
    victim = tmp_path / "victim.txt"
    victim.write_text("원래 내용", encoding="utf-8")
    os.symlink(victim, vault / "20_Projects/.t.md.myelin-tmp")
    apply_change(vault, plan_promote(vault, rel, "20261016-0900-tmp", TODAY))
    assert victim.read_text(encoding="utf-8") == "원래 내용"
    assert not (vault / rel).is_symlink() and "verified" in (vault / rel).read_text("utf-8")
    leftovers = [p.name for p in (vault / "20_Projects").iterdir() if "myelin-tmp" in p.name]
    assert leftovers == [".t.md.myelin-tmp"]  # 심어 둔 링크만 남고 우리 임시 파일은 없다


def test_symlinked_destination_refused(vault: Path, put: Put, tmp_path: Path) -> None:
    put(AI, draft())
    outside = tmp_path / "outside"
    outside.mkdir()
    folder = vault / "10_Domains/AI-ML-AX"
    for f in folder.iterdir():
        f.unlink()
    folder.rmdir()
    os.symlink(outside, folder)
    with pytest.raises(ReviewError) as exc:
        plan_promote(vault, AI, "20261018-0900-wcet", TODAY)
    assert _code(exc) == "symlink"
    os.symlink(outside, vault / "99_Archive/rejected")
    with pytest.raises(ReviewError) as exc:
        plan_reject(vault, AI, "20261018-0900-wcet", TODAY)
    assert _code(exc) == "symlink"
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("name", ["a\nb.md", "a\x1fb.md", "a\x7fb.md"])
def test_control_chars_refused(vault: Path, name: str) -> None:
    with pytest.raises(ReviewError) as exc:
        plan_promote(vault, f"00_Inbox/ai-drafts/{name}", "x", TODAY)
    assert _code(exc) == "bad_path"


def test_read_note_non_utf8(vault: Path) -> None:
    (vault / AI).write_bytes(b"---\nid: \xff\n---\n")
    with pytest.raises(ReviewError):
        read_note(vault, AI)
