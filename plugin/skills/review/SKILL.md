---
name: review
description: myelin doctor 와 myelin stats 결과로 MYELIN Vault의 주간 리뷰 보고서를 50_Journal/reviews 에 만든다 — 지표, 문제, 검토 대기 AI 초안, 다음 행동. 사용자가 /myelin:review 로 호출할 때만 쓴다.
argument-hint: "[YYYY-Www]"
disable-model-invocation: true
allowed-tools: Bash(myelin doctor *), Bash(myelin stats *)
---
<!-- myelin:min-level 1 -->

# /myelin:review — 주간 리뷰

기간: $ARGUMENTS (비어 있으면 이번 주)

## 0. 사전 점검
1. `myelin.yaml` 의 `level` 이 **1 미만**이면 쓰지 말고 알린 뒤 멈춘다.
2. Vault 루트에서 실행한다: `myelin doctor . --json` 과 `myelin stats . --json`.
   `myelin` 명령이 없으면 사용자에게 설치를 안내하고 멈춘다 (숫자를 추측하지 않는다).

## 1. 해석 — 명세 §11.1 목표와 비교
| 지표 | 목표 |
|---|---|
| inbox_avg_age_days | ≤ 7 |
| verified_last_7d | ≥ 5 (구성원) |
| ai_promotion_rate | 0.4 ~ 0.7 — 너무 높으면 검토가 느슨하다는 신호 |
| orphan_ratio | ≤ 0.10 |
| cross_domain_ratio | ≥ 0.15 |

- doctor의 error는 먼저, warning은 묶어서.
- `00_Inbox/ai-drafts/` 의 검토 대기 초안 목록 (오래된 순).
- domain이 2개 이상인 verified 노트 → `/myelin:ip-scan` 후보로 표시.

## 2. 쓰기
- 경로: `50_Journal/reviews/<YYYY-Www>.md` — 이미 있으면 ` 2` 를 붙인다 (덮어쓰지 않는다).

<!-- myelin:output path="50_Journal/reviews/{{week}}.md" -->
```markdown
# 주간 리뷰 {{week}}

> 생성: {{date}} · `/myelin:review` (origin: claude) — 숫자는 myelin stats/doctor 출력 그대로

## 지표
| 지표 | 값 | 목표 | 상태 |
|---|---|---|---|

## doctor
- 오류: 
- 경고: 

## 검토 대기 AI 초안
- [[{{note}}]]

## 다음 행동 (최대 3개)
1. 
```
<!-- /myelin:output -->

## 3. 보고
- 보고서 경로와 가장 중요한 행동 한 가지.
