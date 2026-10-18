"""P7 Gate e2e — Commons 제안: 자동 검사 + 사람 확인 5항목, push는 별도 확인."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from playwright.sync_api import expect

from myelin_core.commons import init_commons
from myelin_core.gitops import Author
from myelin_core.onboarding import InitRequest, find_packs_dir, load_packs, prepare_init
from myelin_core.scaffold import apply_plan

OK_NOTE = (
    "---\nid: 20261018-0900-share\ntype: evergreen\ndomain: [AI-ML-AX]\nstatus: verified\n"
    "origin: human\nshare: true\ncreated: 2026-10-17\nreviewed: 2026-10-18\n"
    "tags: [control-loop]\n---\n"
    "# 제어 루프 예산의 교훈\n\n추론 p99 지연을 WCET 예산에 포함한다.\n"
)
LEAKY_NOTE = OK_NOTE.replace("20261018-0900-share", "20261018-0901-leak").replace(
    "# 제어 루프 예산의 교훈", "# 고객 서버 메모\n\n대상 10.1.2.3"
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout


def _setup(hub: Any) -> Path:
    req = InitRequest(owner="Brian", packs=("brian.physical-ai",), primary="AI-ML-AX")
    prepared = prepare_init(hub.vault, req, load_packs(find_packs_dir()), date.today())
    apply_plan(hub.vault, prepared.plan)
    repo = hub.vault.parent / "commons"
    init_commons(repo, "Example Org", Author("Admin", "admin@localhost"))
    remote = hub.vault.parent / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    _git(repo, "remote", "add", "origin", str(remote))
    text = (hub.vault / "myelin.yaml").read_text(encoding="utf-8")
    text = text.replace("  enabled: false\n", f"  enabled: true\n  path: {repo}\n", 1)
    (hub.vault / "myelin.yaml").write_text(text, encoding="utf-8")
    (hub.vault / "30_Resources/교훈.md").write_text(OK_NOTE, encoding="utf-8")
    (hub.vault / "30_Resources/메모.md").write_text(LEAKY_NOTE, encoding="utf-8")
    return repo


def test_commons_propose_requires_confirmation(
    page: Any, hub: Any, snapshot: Callable[[Path], dict[str, str]]
) -> None:
    repo = _setup(hub)
    before = snapshot(hub.vault)
    page.goto(f"{hub.url}/#/commons")
    page.reload()  # 로그인 때 열린 화면은 Vault 생성 전 상태다
    page.get_by_test_id("screen-commons").wait_for()
    rows = page.get_by_test_id("commons-row")
    expect(rows).to_have_count(2)

    # 비식별 위반 노트: 차단 표시, 제안 버튼 없음
    rows.filter(has_text="메모").click()
    page.get_by_test_id("commons-blocked").wait_for()
    expect(page.get_by_test_id("commons-propose")).to_have_count(0)

    # 통과 노트: 5항목을 모두 체크해야 버튼이 켜진다
    rows.filter(has_text="교훈").click()
    page.get_by_test_id("commons-content").get_by_text("commons_of: 20261018-0900-share").wait_for()
    button = page.get_by_test_id("commons-propose")
    boxes = page.locator("[data-testid^=confirm-]").filter(
        has_not=page.get_by_test_id("confirm-push")
    )
    n = boxes.count()
    assert n == 5
    for i in range(n - 1):
        boxes.nth(i).check()
        expect(button).to_be_disabled()
    boxes.nth(n - 1).check()
    expect(button).to_be_enabled()
    page.wait_for_load_state("networkidle")
    page.screenshot(path=str(hub.shots / "commons.png"), full_page=True)
    button.click()
    page.get_by_test_id("commons-message").get_by_text(
        "아직 조직 원격으로 보내지 않았습니다"
    ).wait_for()

    assert _git(repo, "branch", "--list", "publish/*").strip() == "publish/20261018-0900-share"
    remote = hub.vault.parent / "remote.git"
    assert _git(remote, "branch", "--list").strip() == ""  # 아직 밖으로 안 나감
    assert snapshot(hub.vault) == before  # Vault 불변

    # 두 번째 확인: push
    page.get_by_role("button", name="조직으로 보내기…").click()
    page.get_by_test_id("confirm-push").click()
    page.get_by_test_id("commons-message").get_by_text("원격으로 보냈습니다").wait_for()
    assert "publish/20261018-0900-share" in _git(remote, "branch", "--list")
    page.wait_for_load_state("networkidle")
    page.screenshot(path=str(hub.shots / "commons-proposed.png"), full_page=True)
