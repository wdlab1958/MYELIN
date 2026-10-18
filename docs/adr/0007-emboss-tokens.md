# ADR-0007: MYELIN Emboss 토큰과 생성 파이프라인

- 상태: Accepted
- 일자: 2026-10-18
- Phase: P5

## 맥락
명세 §8은 백색 엠보 + Violet/Neon 디자인과 접근성 가드레일(텍스트 4.5:1, 네온은 글자색 금지)을 정했다.
Hub(P6)와 Obsidian 테마가 같은 디자인을 써야 하고, 가드레일은 문서가 아니라 **검사**로 지켜져야 한다.

## 결정
### 단일 원천
- `design/tokens.json` 하나. 참조 문법 `{color.violet}`. 생성기 `design/build.py`(표준 라이브러리)가 만든다:
  `design/dist/tokens.css`(`--mx-*`), `tokens.resolved.json`, `tailwind.preset.js`(모두 `var()` 참조), Obsidian `theme.css`.
- CSS 변수에서 참조는 `var()` 로 남긴다 — 하위 테마가 원천 변수 하나만 바꿔도 파생 값이 따라온다.
- 변수 접두사 `--mx-` (명세의 `--surface` 등은 Obsidian·Tailwind 변수와 충돌하므로 접두사를 붙였다).

### 명세 §8.1 값 조정 (실측 대비가 기준 미달)
| 토큰 | 명세 | 대비(배경 #EEF0F6) | 확정 | 대비 |
|---|---|---|---|---|
| muted | #6B6F85 | 4.35 | **#5D6178** | 5.35 |
| lime-ink | #4D7C0F | 4.38 | **#3F6212** | 6.21 |
| cyan-ink | #0891B2 | 3.23 | **#0E7490** | 4.70 |
| ink on magenta | — | 4.48 | 사용 금지 → 차단 배지는 magenta-ink on magenta-50 | 5.00 |

명세 값을 그대로 쓰면 명세 자신의 가드레일(4.5:1)을 어긴다. 가드레일이 우선이다.

### 추가 토큰
- accent `amber`·`slate` 값 정의 (ADR-0004의 6종 accent 완성). 각 accent = fill · ink · soft · glow.
- `status.{verified, ai, draft, blocked}` = bg · fg · line — 칩·배지는 이것만 쓴다.
- `surface-well`, `line`, `focus.ring`, `motion`.

### 가드레일을 검사로
- `--contrast`: 텍스트 조합 18쌍 WCAG ≥ 4.5 (실패 시 Gate FAIL). 네온 5종은 표면 위 대비를 보고하며 "텍스트 금지"로 표시.
- `--lint`: 손으로 쓰는 CSS·Hub 소스·갤러리에서 색 리터럴(#hex, rgb(), hsl()) 금지,
  `color: var(--mx-lime|cyan|magenta|amber|slate|glow-*|accent-*-fill)` 금지 (네온을 글자색으로).
- `--check`: 커밋된 산출물이 원천과 일치.
- 갤러리 스크린샷은 Playwright로 찍고, 찍을 때의 HTML·CSS 해시를 기록해 Gate가 "현재 디자인의 사진인지" 확인한다.

### 범위
- Obsidian 테마는 `.theme-light` 만. 다크 모드는 v1.0 범위 밖 (토큰 구조는 대비해 둠).

## 결과
- Hub(P6)는 `tailwind.preset.js` + `tokens.css` + `components.css` 만으로 Emboss를 쓴다. 새 색이 필요하면 tokens.json에 먼저 추가한다.
- 실제 Obsidian에서의 모습은 Brian 수동 점검 (P3 e2e 체크리스트와 함께).
