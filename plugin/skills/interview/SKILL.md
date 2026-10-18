---
name: interview
description: Vault의 질문 은행(90_System/interviews.md)으로 사용자의 경험을 한 질문씩 묻고, 답을 바탕으로 lesson 노트 초안을 00_Inbox/ai-drafts 에 만든다. 암묵지를 명시지로 바꾸는 인터뷰. 사용자가 /myelin:interview 로 호출할 때만 쓴다.
argument-hint: "<Domain ID> [질문 id]"
disable-model-invocation: true
---
<!-- myelin:min-level 1 -->

# /myelin:interview — 경험을 lesson 노트로

대상: $ARGUMENTS

## 0. 사전 점검
1. `myelin.yaml` 의 `level` 이 **1 미만**이면 쓰지 말고 알린 뒤 멈춘다.
2. `90_System/interviews.md` 에서 해당 Domain의 질문을 찾는다. Domain을 안 주면 `myelin.yaml` 의 domains 를 보여주고 고르게 한다.

## 1. 인터뷰 — 대화로 진행
- **한 번에 한 질문만** 한다. 답을 기다린다. 사용자를 대신해 답을 지어내지 않는다.
- 답이 짧으면 follow-up 질문이나 "그때 구체적으로 무엇이 일어났나요?" 로 한 번 더 묻는다.
- 3~5개 질문이 끝나거나 사용자가 그만하자고 하면 멈춘다.

## 2. 쓰기 — 사건 하나당 lesson 노트 하나
- 사용자의 말을 **그대로** 살린다. 정리·구조화만 하고 내용을 더하지 않는다.
- `origin: mixed` (사람의 경험 + Claude의 구조화). `era` 에 그 경험의 시기를 적는다 (사용자가 말한 대로).
- 경로: `00_Inbox/ai-drafts/Lesson - <교훈 한 문장>.md`
- 고객명·개인 식별 정보가 나오면 일반화해서 적고, 그렇게 했다고 보고한다.

<!-- myelin:output path="00_Inbox/ai-drafts/Lesson - {{title}}.md" -->
```markdown
---
id: {{id}}
type: lesson
domain: [{{domain}}]
era: "1980s"
status: draft
origin: mixed
confidence: medium
classification: internal
created: {{date}}
tags: [lesson, interview]
---
# Lesson - {{title}}

## 상황 (Context)

## 무엇이 일어났나 (Event)

## 원인 (Root Cause)

## 원칙화 (Principle) — 지금도 유효한 규칙

## 현대 스택 매핑 (Then → Now)

## 인터뷰 기록
- Q: 
- A: (사용자의 말 그대로)
```
<!-- /myelin:output -->

## 3. 보고
- 만든 노트와, 다음 인터뷰 때 이어 물을 질문 1~2개.
