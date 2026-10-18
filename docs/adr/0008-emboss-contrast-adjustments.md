# ADR-0008: Emboss 토큰 — 대비 기준(4.5:1)에 따른 값 조정

- 상태: Accepted · 일자: 2026-10-18 · Phase: P5
- 근거: 정본 §8.1 Design Tokens, §8.3 접근성 가드레일 2 "텍스트 대비 4.5:1 이상 — P5 Gate 에서 스크립트로 검증", 가드레일 1 "네온은 채움·glow·링 전용, 숫자 강조는 네온의 어두운 변형"

## 맥락

`scripts/emboss.py a11y` 로 정본 §8.1 값의 텍스트/배경 쌍을 계산하면 세 쌍이 4.5:1 에 미달한다.

| 쌍 | 정본 값 | 대비 | 판정 |
|---|---|---|---|
| `--muted` / `--surface` | #6B6F85 / #EEF0F6 | 4.35 | 미달 |
| `--lime-ink` / `--surface` | #4D7C0F / #EEF0F6 | 4.38 | 미달 |
| `--cyan-ink` / `--surface` | #0891B2 / #EEF0F6 | 3.23 | 미달 |

## 결정

정본의 **기준(4.5:1)** 을 **값** 보다 우선한다. 세 토큰을 같은 색조에서 어둡게 조정하고 `tokens.json` 에 `spec` 필드로 원값을 보존한다.

| 토큰 | 조정 값 | 대비(/surface) |
|---|---|---|
| `--muted` | **#5F6378** | 5.20 |
| `--lime-ink` | **#3F6A0A** | 5.62 |
| `--cyan-ink` | **#0E7490** | 4.70 |

추가 결정:
- `--border` 를 #E2E5EE → **#DADEE9** 로 소폭 어둡게(입력창 경계가 surface 위에서 보이도록; 텍스트가 아니므로 대비 기준 대상은 아님).
- `--surface-2`(#E6E9F2), `--on-violet`(#FFFFFF), `--raised-sm`, `--ring-lime`, `space.*`, `font.*`, `motion.myelinate` 토큰을 추가한다. 정본 §8 에 없던 보조 토큰이며 색 하드코딩 금지 규칙(CLAUDE.md)을 갤러리·Hub 가 지킬 수 있게 하기 위한 최소 집합.
- `ink` on `neon-magenta` 는 4.48 로 미달이지만 Magenta 는 **외곽선·배지 전용**(§8.2 blocked = Magenta 외곽선 배지, 텍스트는 `--magenta-ink` on `--magenta-50`)이므로 텍스트 쌍으로 등록하지 않는다. 채움 Magenta 위 텍스트는 금지.
- 검사 대상 쌍은 `tokens.json a11y.text-pairs` 가 정본이다. 새 UI 가 다른 쌍을 쓰면 먼저 쌍을 추가해야 Gate 를 통과한다.

## 결과

- Hub(P6)·Obsidian Theme 모두 조정 값을 쓴다. 정본 §8.1 표는 Rev 2.1 개정 시 이 값으로 갱신 제안.
- 다크 모드는 범위 밖(§8.3 가드레일 5). `modes` 키만 예약.
