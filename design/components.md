# MYELIN Emboss — 컴포넌트 스펙 (정본 §8.2 · §8.3)

**원칙: 표면은 조용히, 신호는 선명하게.** 대부분의 화면은 그림자(raised/inset)로만 구분되고, 사용자가 주목해야 할 상태에만 Violet/Neon 이 켜진다. 모든 값은 `design/tokens.json` 토큰(`var(--mx-*)`)만 사용한다 — 색 하드코딩은 `scripts/emboss.py lint` 가 막는다.

## 색의 의미 체계 (§8.2)

| 상태 | 시각 표현 | 클래스 | 규칙 |
|---|---|---|---|
| draft (사람) | Violet 외곽선 칩, violet-50 배경 | `.mx-chip--draft` | 진행 중 |
| ai-draft | Cyan 채움 칩 + 카드 Cyan glow | `.mx-chip--ai`, `.mx-glow--ai` | AI 생성물은 항상 Cyan — 사람 것과 섞이지 않게 |
| verified | Lime 채움 칩 + Lime ring | `.mx-chip--verified`, `.mx-ring--verified` (+`.is-myelinating`) | 승격 순간 "myelinated" 링 애니메이션 |
| unverified | 경계선 칩, muted 텍스트 | `.mx-chip--unverified` | 사람 작성·미검토 |
| blocked / 위반 | Magenta 외곽선 배지, magenta-50 배경, magenta-ink 텍스트 | `.mx-badge--blocked` | Guard 차단, doctor 위반 |
| Domain 정체성 | Pack 의 accent 토큰 → Orb 테두리 glow | `.mx-orb[data-accent=violet|lime|cyan|magenta]` | Domain Map, 클릭 시 MOC |

네온 위 텍스트는 항상 `--mx-ink`. 네온 색을 텍스트 색으로 쓰지 않는다(a11y 검사가 `color: var(--mx-neon-*)` 를 거부). 숫자 강조는 어두운 변형(`--mx-lime-ink`, `--mx-cyan-ink`, `--mx-magenta-ink`).

## 컴포넌트 (§8.3)

| 컴포넌트 | 형태 | 클래스 | 접근성 |
|---|---|---|---|
| Card / KPI Tile | Raised, radius-card(28px), padding space-5 | `.mx-card`, `.mx-kpi` + `__value(--verified/--ai/--blocked)`, `__label` | 숫자는 상태 색(어두운 변형), 라벨은 muted(≥4.5:1) |
| Primary Button | Violet 채움 + Violet glow, radius-control(20px) | `.mx-btn-primary` | **화면당 1개**. 텍스트 on-violet(5.70:1). focus ring 2px violet |
| Secondary Button | Raised → 누르면/`aria-pressed` Inset | `.mx-btn` (+`.mx-btn-promote` Lime 채움) | 1px border 병행. 눌림은 그림자 + aria-pressed |
| Input / Search | Inset + 1px border | `.mx-input` | Focus 시 2px Violet ring (그림자만으로 focus 표현 금지) |
| Nav Item | 평면 → 활성 시 Inset + Violet 텍스트 | `.mx-nav-item` (`.is-active` 또는 `aria-current="page"`) | 활성은 색 + 함몰 두 신호 |
| Status Chip | Pill, 상태 색 채움 + ink 텍스트 | `.mx-chip--*` | **항상 텍스트 라벨**(verified, ai-draft …). 색만으로 전달 금지 |
| Domain Orb | 원형 Raised-sm + accent glow | `.mx-orb[data-accent]` | 안에 Domain ID 텍스트. `<button>` 으로 렌더 |
| Review Row | 평면 리스트 + 좌측 상태 칩 + 우측 Promote(Lime)/Reject | `.mx-review-row` | Promote 는 `.mx-btn.mx-btn-promote`, Reject 는 `.mx-btn` |
| Table | 헤더 surface-2, 행 경계 border | `.mx-table` | 헤더 muted on surface-2 ≥ 4.5:1 |

## 접근성 가드레일 (§8.3) → 검사 방법

1. 네온은 채움·glow·링 전용 → `emboss.py a11y` 의 NEON-AS-TEXT 규칙.
2. 텍스트 대비 4.5:1 → `tokens.json a11y.text-pairs` 전수 계산(ADR-0008 로 세 토큰 조정).
3. 경계가 중요한 요소는 그림자 외 **1px border 또는 focus ring** → `.mx-input`, `.mx-btn`, `.mx-orb` 는 border 포함; focus ring 은 `.mx` 범위 전역.
4. 상태는 색만으로 전달하지 않는다 → 칩/배지는 텍스트 라벨 필수(갤러리·Hub 리뷰 항목).
5. 다크 모드 v1.0 범위 밖 → tokens `modes` 예약, theme.css 는 `.theme-dark` 에도 light 값을 적용(깨지지 않게).

## 사용 규약 (Hub · Theme)
- Hub(React/Tailwind) 는 `design/dist/tailwind.preset.cjs` 를 preset 으로 쓰고 `mx-*` 유틸(`bg-mx-surface`, `shadow-mx-raised`, `rounded-mx-card` …) 또는 `emboss.css` 클래스만 사용한다.
- Obsidian Theme 는 `theme/obsidian-myelin-emboss/theme.css`(생성물). 노트 상태 표시는 `cssclasses: [mx-status-verified]` 또는 Dataview 로 부여.
- 토큰 변경 → `make emboss` → `make a11y` → `make emboss-lint` → 갤러리 스크린샷 갱신(`make gallery`).
