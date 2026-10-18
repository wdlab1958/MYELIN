"""P6 Gate e2e — 온보딩 → 첫 노트 verified 승격 → git commit, 그리고 사용자 행위 없는 쓰기 0."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from playwright.sync_api import expect

DRAFT = (
    "---\n"
    "id: 20261018-0900-wcet-budget\n"
    "type: evergreen\n"
    "domain: [AI-ML-AX]\n"
    "status: draft\n"
    "origin: claude\n"
    "created: 2026-10-18\n"
    "tags: [rtos, control-loop]\n"
    "---\n"
    "# WCET 예산은 추론 지연을 포함해야 한다\n\n"
    "제어 루프 주기 안에 모델 추론 p99 지연을 예산으로 잡는다.\n\n"
    "상위: [[10_Domains/AI-ML-AX/_MOC]]\n"
)
DRAFT_REL = "00_Inbox/ai-drafts/WCET 예산은 추론 지연을 포함.md"
PROMOTED = "10_Domains/AI-ML-AX/WCET 예산은 추론 지연을 포함.md"


def _claude_writes_draft(vault: Path, rel: str = DRAFT_REL, text: str = DRAFT) -> None:
    """Claude(/distill, Level 1)가 ai-drafts 에 초안을 남긴 상황을 흉내 낸다."""
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(vault: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(vault), *args], capture_output=True, text=True, check=True
    ).stdout


def _onboard(page: Any, hub: Any) -> None:
    page.goto(hub.url)
    page.get_by_test_id("onboarding").wait_for()
    page.fill("#ob-owner", "Brian")
    page.get_by_test_id("next").click()
    page.get_by_test_id("pack-brian.physical-ai").check()
    page.get_by_test_id("next").click()
    page.select_option("#ob-primary", "AI-ML-AX")
    page.select_option("#ob-research", "ROBOTICS-LEARNING")
    page.select_option("#ob-growth", "EMBEDDED-SW")


def _settled(page: Any) -> None:
    page.wait_for_load_state("networkidle")
    # CSP가 eval 을 막으므로 wait_for_function 대신 locator 로 기다린다
    expect(page.get_by_text("불러오는 중")).to_have_count(0)


def _shot(page: Any, hub: Any, name: str) -> None:
    _settled(page)
    page.screenshot(path=str(hub.shots / f"{name}.png"), full_page=True)


def _go(page: Any, screen: str) -> None:
    page.get_by_test_id(f"nav-{screen}").click()
    page.get_by_test_id(f"screen-{screen}").wait_for()
    _settled(page)


def test_onboarding_to_promotion(page: Any, hub: Any) -> None:
    # 1) 신규 사용자 온보딩 (CLI init 과 같은 core 로직)
    _onboard(page, hub)
    _shot(page, hub, "onboarding")
    page.get_by_test_id("next").click()  # → 권한
    page.get_by_test_id("next").click()  # → 확인
    page.get_by_test_id("onboarding-preview").get_by_text("님의 Vault").wait_for()
    assert not hub.vault.exists()  # 미리보기까지는 쓰지 않는다
    page.get_by_test_id("create-vault").click()
    page.get_by_test_id("screen-dashboard").wait_for()
    assert (hub.vault / "myelin.yaml").is_file()
    assert _git(hub.vault, "log", "--format=%s").splitlines() == ["myelin: start vault history"]

    # 2) Claude가 초안을 남긴다 → Review Gate
    _claude_writes_draft(hub.vault)
    page.reload()
    _shot(page, hub, "dashboard")
    _go(page, "review")
    row = page.get_by_test_id("review-row")
    assert row.count() == 1
    row.first.click()
    page.get_by_test_id("note-body").get_by_text("p99").wait_for()
    _shot(page, hub, "review")

    # 3) 사람이 승격 → verified + git commit
    page.get_by_test_id("promote").click()
    result = page.get_by_test_id("review-result")
    result.get_by_text("myelinated").wait_for()
    page.wait_for_timeout(1000)  # 링 애니메이션
    _shot(page, hub, "review-myelinated")

    assert not (hub.vault / DRAFT_REL).exists()
    promoted = (hub.vault / PROMOTED).read_text(encoding="utf-8")
    assert "status: verified" in promoted and "reviewed: " in promoted
    assert "origin: claude" in promoted and promoted.endswith(
        "상위: [[10_Domains/AI-ML-AX/_MOC]]\n"
    )
    head = _git(hub.vault, "log", "-1", "--format=%H%n%s").splitlines()
    assert head[1] == "myelin: promote 20261018-0900-wcet-budget (WCET 예산은 추론 지연을 포함)"
    assert head[0][:7] in result.inner_text()
    changed = _git(hub.vault, "show", "--name-only", "--format=", "-z", "HEAD").split("\0")
    assert PROMOTED in changed
    assert _git(hub.vault, "status", "--porcelain") == ""  # 승격이 남긴 미기록 변경 없음

    # 4) 나머지 화면 (스크린샷)
    _go(page, "dashboard")
    _shot(page, hub, "dashboard")
    _go(page, "domains")
    _shot(page, hub, "domains")
    _go(page, "packs")
    page.get_by_role("button", name="pack.yaml 보기").first.click()
    page.get_by_test_id("validate-pack").click()
    page.get_by_text("valid", exact=True).wait_for()
    _shot(page, hub, "packs")
    _go(page, "settings")
    _shot(page, hub, "settings")


def test_no_passive_writes(page: Any, hub: Any, snapshot: Callable[[Path], dict[str, str]]) -> None:
    """버튼(만들기·승격·반려·저장·추가·git 시작)을 누르지 않는 한 Vault는 바뀌지 않는다."""
    posts: list[str] = []
    page.on("request", lambda r: posts.append(r.url) if r.method == "POST" else None)

    # 온보딩 마법사를 끝까지 보되 만들지 않는다
    _onboard(page, hub)
    page.get_by_test_id("next").click()
    page.get_by_test_id("next").click()
    page.get_by_test_id("onboarding-preview").get_by_text("님의 Vault").wait_for()
    page.reload()
    page.wait_for_load_state("networkidle")
    assert not hub.vault.exists()

    # Vault를 만들고 초안 2개 + 원료 메모를 둔 뒤 상태를 고정
    _onboard(page, hub)
    page.get_by_test_id("next").click()
    page.get_by_test_id("next").click()
    page.get_by_test_id("create-vault").click()
    page.get_by_test_id("screen-dashboard").wait_for()
    _claude_writes_draft(hub.vault)
    _claude_writes_draft(
        hub.vault, "00_Inbox/ai-drafts/other.md", DRAFT.replace("wcet-budget", "other")
    )
    (hub.vault / "00_Inbox/메모.md").write_text("frontmatter 없는 메모\n", encoding="utf-8")
    posts.clear()
    before = snapshot(hub.vault)

    # 모든 화면을 돌아다니고, 노트를 열어 보고, Pack을 검증하고, 새로고침한다
    for _ in range(2):
        for screen in ("dashboard", "domains", "review", "packs", "settings"):
            _go(page, screen)
        rows = page.locator("[data-testid=review-row]")
        _go(page, "review")
        for i in range(rows.count()):
            rows.nth(i).click()
            page.get_by_test_id("note-body").wait_for()
        _go(page, "packs")
        page.get_by_role("button", name="pack.yaml 보기").first.click()
        page.get_by_test_id("validate-pack").click()
        page.get_by_text("valid", exact=True).wait_for()
        page.reload()
        page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    assert snapshot(hub.vault) == before
    assert {p.split("/api/")[1] for p in posts} <= {"packs/validate", "onboarding/preview"}
