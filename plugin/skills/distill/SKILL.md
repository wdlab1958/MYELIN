---
name: distill
description: Inbox 노트를 원자(evergreen) 노트로 분해하고 frontmatter·중복·용어를 정리해 00_Inbox/ai-drafts 에 초안을 만든다. Level ≥ 1.
argument-hint: "<Inbox 노트 경로 | 80_Outputs 산출물 경로(환류) | 비우면 00_Inbox 전체 목록 제시>"
allowed-tools: Read, Glob, Grep, Bash(myelin *), Bash(git add *), Bash(git commit *), Write
---

# /distill — Inbox → 원자 노트 초안

공통 규약: `plugin/skills/_COMMON.md`. 최소 Level **1** · 쓰기 범위 **`00_Inbox/ai-drafts/`**.

## 절차
1. 대상 노트를 Read 한다. 인자가 없으면 `00_Inbox/*.md`(ai-drafts 제외) 목록과 체류일을 보여 주고 어느 것을 분해할지 묻는다.
2. 노트에서 **독립적으로 참이거나 재사용 가능한 주장** 을 1~5개 추출한다. 하나의 주장 = 하나의 evergreen 노트. 제목은 주장 문장(한국어, 40자 이내).
3. **중복 검사** — 각 후보 제목의 핵심 명사로 `Grep`(10_Domains, 30_Resources, 00_Inbox/ai-drafts) 하여 유사 노트가 있으면 새로 만들지 않고 "기존 노트 [[제목]] 에 보강 제안" 으로 보고한다(수정은 하지 않는다).
4. **용어 정규화** — `90_System/taxonomy.md` 의 대표 용어로 바꾼다. 사전에 없는 반복 용어는 본문에 `(용어 제안: …)` 표시.
5. `90_System/templates/evergreen.md` 로 각 노트를 `00_Inbox/ai-drafts/<제목>.md` 에 만든다. `source` 에는 원 Inbox 노트 링크 `"[[원 노트 제목]]"` 를 넣고, 서로 관련된 노트끼리 `## 연결` 에 링크한다. Domain 은 원 노트의 domain 을 상속(없으면 공통 규약 4).
6. 원 Inbox 노트는 **수정하거나 지우지 않는다**. 대신 보고에 "원 노트 처리 제안: 99_Archive 이동" 을 적는다(사람이 수행).
7. `myelin doctor` → error 0 확인 → 생성 파일·중복 판정·용어 제안을 표로 보고.

## 환류 (산출물 → 원자 노트) — "축적이 복리로" 의 되돌아오는 반쪽
인자가 `80_Outputs/` 아래의 산출물(설계서·제안서·보고서·특허 초안)이면 **환류 모드**로 동작한다. 산출물을 쓰면서 새로 알게 된 것은 산출물 안에만 남으면 다시 쓰이지 않는다. 절차 2~7 을 그대로 따르되 다음이 다르다.
- 추출 대상은 산출물의 `## 환류 후보` 절(/compose 가 남긴다)과 본문에서 **재료 노트에 없던 주장·교훈·결정**이다. 이미 `source` 의 노트에 있는 내용은 만들지 않는다(중복 검사 3).
- 노트 유형은 교훈이면 `lesson`, 재사용 가능한 주장이면 `evergreen`, 결정이면 `adr`. `source` 에 산출물 링크 `"[[산출물 제목]]"` 를 넣고 `tags` 에 `refeed` 를 추가한다.
- 보고에 "환류 N건 → Review Gate 에서 승격" 을 적는다. 승격되면 Hub 의 강도(재사용) 지표에 반영된다.

## 출력 노트 형식 (evergreen)
```markdown
---
id: 20261018-1500-wcet-budget-1-5x
type: evergreen
domain: [D2]
status: draft
origin: claude
confidence: medium
classification: internal
share: false
source: ["[[오늘 회의 메모 - 평가 지표]]"]
created: 2026-10-18
tags: [rtos]
---
# WCET 예산은 측정값의 1.5배로 잡는다

> 한 문장 요지: 측정 WCET 는 하한이므로 예산에는 여유율을 둔다.

## 설명
…

## 근거 · 출처
- [[오늘 회의 메모 - 평가 지표]]

## 연결
- 상위: [[_MOC]]
- 관련: [[ISR 안에서 로그를 찍지 않는다]]
```
