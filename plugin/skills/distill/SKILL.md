---
name: distill
description: Inbox의 노트(literature·fleeting·메모)를 원자 단위 evergreen 노트 초안들로 분해해 00_Inbox/ai-drafts 에 만든다. 원본은 고치지 않는다. 사용자가 /myelin:distill 로 호출할 때만 쓴다.
argument-hint: "<Inbox 노트 경로>"
disable-model-invocation: true
---
<!-- myelin:min-level 1 -->

# /myelin:distill — 하나의 개념 = 하나의 노트

대상: $ARGUMENTS

## 0. 사전 점검
1. `myelin.yaml` 의 `level` 이 **1 미만**이면 쓰지 말고 알린 뒤 멈춘다.
2. 대상 노트를 읽는다. **원본은 절대 수정하지 않는다.**

## 1. 분해
- 대상에서 독립적으로 설 수 있는 주장·개념을 찾는다 (보통 1~5개).
- 각 후보마다 기존 노트와 겹치는지 확인한다:
  `10_Domains/**` 에서 제목·핵심어를 Grep/Glob으로 찾는다.
  - 거의 같은 노트가 있으면 새로 만들지 말고 보고에 "기존 [[노트]] 보강 후보"로 적는다.
- 제목은 **주장형 문장**으로 (예: "WCET 예산은 추론 지연을 포함해야 한다").
- 용어는 `90_System/taxonomy.md` 를 따른다. 사전에 없는 핵심 용어는 보고에 "taxonomy 제안"으로 적는다.

## 2. 쓰기 — 후보마다 노트 하나
- 경로: `00_Inbox/ai-drafts/<주장형 제목>.md`
- `source` 에 원본 노트를 wikilink로 넣는다. 본문에서 원본과 관련 노트를 링크한다.
- id 규칙: `YYYYMMDD-HHmm-<영문 키워드>` (ingest와 같음). 노트마다 달라야 한다.

<!-- myelin:output path="00_Inbox/ai-drafts/{{title}}.md" -->
```markdown
---
id: {{id}}
type: evergreen
domain: [{{domain}}]
status: draft
origin: claude
confidence: medium
classification: internal
share: false
source: ["[[{{note}}]]"]
created: {{date}}
tags: []
---
# {{title}}

## 핵심 주장 (1~3문장)

## 근거 / 메커니즘

## 적용 · 사례

## 반론 · 한계

## 연결
- 원본: [[{{note}}]]
```
<!-- /myelin:output -->

## 3. 보고
- 만든 노트 목록(경로), 건너뛴 중복 후보, taxonomy 제안.
- "검토 후 verified로 승격하고 10_Domains 로 옮기는 것은 사람이 합니다."
