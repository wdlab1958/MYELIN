"""갤러리 스크린샷 — Playwright(Chromium)로 design/gallery/index.html 을 찍는다 (P5).

실행: python3 scripts/shoot_gallery.py   (playwright 와 chromium 이 있는 Python)
결과: docs/reports/P5/gallery.png + gallery.sha256
      (찍을 때의 갤러리·CSS 해시 — Gate가 최신 여부 확인)
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
GALLERY = ROOT / "design" / "gallery" / "index.html"
OUT = ROOT / "docs" / "reports" / "P5"
HASHED = ("design/gallery/index.html", "design/dist/tokens.css", "design/src/components.css")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
        page.goto(GALLERY.as_uri())
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(OUT / "gallery.png"), full_page=True)
        # 대비 실측: 렌더된 KPI 숫자색이 토큰 *-ink 인지 (네온이 글자로 쓰이지 않았는지)
        colors = page.eval_on_selector_all(
            ".mx-kpi__value", "els => els.map(e => getComputedStyle(e).color)"
        )
        browser.close()
    h = hashlib.sha256()
    for rel in HASHED:
        h.update((ROOT / rel).read_bytes())
    (OUT / "gallery.sha256").write_text(h.hexdigest() + "\n", encoding="utf-8")
    print(f"gallery.png written · KPI colors: {colors}")


if __name__ == "__main__":
    main()
