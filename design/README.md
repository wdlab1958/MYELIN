# design/ — MYELIN Emboss

백색 엠보 + Violet/Neon 강조 디자인 시스템 (명세 §8, ADR-0007).

| 파일 | 역할 |
|---|---|
| `tokens.json` | **단일 원천** — 색·accent·status·그림자·반경·간격·글꼴 |
| `src/components.css` | `.mx-*` 컴포넌트 (Card, KPI, Button, Input, Nav, Chip, Orb, Review Row) — 토큰 변수만 사용 |
| `src/obsidian.css` | Obsidian 변수 매핑 + 엠보 적용 규칙 |
| `build.py` | 생성기 · 검사기 (표준 라이브러리) |
| `dist/` | 생성물: `tokens.css`, `tokens.resolved.json`, `tailwind.preset.js` |
| `gallery/index.html` | 컴포넌트 갤러리 — 스크린샷: `docs/reports/P5/gallery.png` |

```bash
python design/build.py             # 산출물 생성 (tokens.json 을 고친 뒤)
python design/build.py --contrast  # WCAG 4.5:1
python design/build.py --lint      # 색 리터럴·네온 글자색 금지
python design/build.py --check     # 산출물 최신 여부
python3 scripts/shoot_gallery.py   # 갤러리 스크린샷 (Playwright 필요)
```
