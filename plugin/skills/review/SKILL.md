---
name: review
description: 주간 품질 보고서 — myelin doctor 와 stats 결과를 해석해 50_Journal 에 리뷰 노트를 만든다. Level ≥ 1.
argument-hint: "[--week 2026-W42]"
allowed-tools: Read, Glob, Grep, Bash(myelin *), Bash(git add *), Bash(git commit *), Bash(git log *), Write
---

# /review — 주간 품질 보고서

공통 규약: `plugin/skills/_COMMON.md`. 최소 Level **1** · 쓰기 범위 **`50_Journal/`**.

## 절차
1. `myelin doctor --json` 과 `myelin stats --json` 을 실행한다(읽기 전용). `git log --since=7.days --oneline` 로 최근 변경을 본다.
2. 지표를 정본 §11.1 목표와 비교해 **빨강/노랑/초록** 으로 판정한다. 승격률이 0.7 을 넘으면 "검토 부실 신호" 를 명시한다.
3. doctor 결과를 규칙별로 묶어 **사람이 할 일 체크리스트** 로 바꾼다 (예: "고아 노트 3건 — 각 노트에 상위 MOC 링크 추가"). 수정은 하지 않는다.
4. Inbox 체류 7일 초과 노트 목록을 적고, 각 노트에 `/distill` 또는 `99_Archive` 중 하나를 제안한다.
5. **환류 점검** — 최근 30일 `80_Outputs/**` 산출물 중 `## 환류 후보` 가 비어 있지 않은데 그 산출물을 `source` 로 가진 ai-drafts/verified 노트가 없는 것을 찾아 "환류 대기" 목록으로 적고 `/distill <경로>` 를 제안한다. `myelin stats` 의 `reuse_ratio`·`reuse_lag_days` 가 목표를 벗어나면 "지식이 재투입되지 않고 있다" 를 명시한다.
6. `50_Journal/<YYYY>-W<ww> 주간 리뷰.md` 를 `fleeting` 템플릿 기반으로 만든다(`origin: claude`, `status: draft`, `tags: [weekly, review]`). 같은 주 파일이 있으면 ` (2)` 를 붙인다 — 덮어쓰지 않는다.
7. 보고: 판정 표 + 체크리스트 요약 + 환류 대기 목록. MOC 갱신이 필요하면 "Level 2 에서 `/link` 로 patch 제안 가능" 을 안내한다.

## 출력 노트 골격
```markdown
---
id: 20261018-1800-weekly-w42
type: fleeting
domain: []
status: draft
origin: claude
confidence: high
classification: internal
share: false
source: []
created: 2026-10-18
tags: [weekly, review]
---
# 2026-W42 주간 리뷰

## 지표 (정본 §11.1)
| KPI | 값 | 목표 | 판정 |
|---|---|---|---|

## doctor → 할 일
- [ ] …

## Inbox 7일 초과
- [[…]] → /distill

## 환류 대기 (산출물 → 원자 노트)
- [[산출물]] → /distill 80_Outputs/…

## 이번 주 verified
```
