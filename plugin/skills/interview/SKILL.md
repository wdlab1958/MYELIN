---
name: interview
description: Pack 질문 은행으로 사용자의 암묵지를 끌어내는 짧은 인터뷰를 진행하고 lesson 초안을 00_Inbox/ai-drafts 에 만든다. Level ≥ 1.
argument-hint: "[--domain D2] [질문 id]"
allowed-tools: Read, Glob, Grep, Bash(myelin *), Bash(git add *), Bash(git commit *), Write
---

# /interview — 암묵지 추출 인터뷰 → lesson 초안

공통 규약: `plugin/skills/_COMMON.md`. 최소 Level **1** · 쓰기 범위 **`00_Inbox/ai-drafts/`**.

## 절차
1. `myelin interview-bank --json [--domain D]` 로 질문 은행을 가져온다(Bash, 읽기 전용). 비어 있으면 "이 Vault 의 Pack 에는 질문 은행이 없습니다" 라고 보고하고 멈춘다.
2. 질문 하나를 고른다: 사용자가 id 를 주면 그것, 아니면 **최근 2주 `50_Journal`·`00_Inbox` 에 언급된 Sub-MOC** 와 겹치는 질문을 우선, 없으면 Domain 의 첫 질문. 선택 이유를 한 줄로 말한다.
3. 질문을 **한 번에 하나씩** 묻는다. 답을 받으면 `follow_ups` 중 답에 비어 있는 부분을 채우는 것 1~2개만 이어 묻는다. 총 4문항을 넘기지 않는다. 사용자가 "그만" 하면 즉시 정리 단계로.
4. 답을 사용자의 **1인칭 표현을 유지**하며 정리한다. 추측으로 채우지 않는다 — 비어 있는 칸은 `(미답)` 으로 남긴다.
5. 질문의 `yields`(기본 lesson) 템플릿으로 `00_Inbox/ai-drafts/<교훈 한 문장>.md` 를 만든다. `domain` 은 질문의 Domain, `tags` 에 `interview` 와 질문 id, `source` 에 `"interview:<질문 id>"`.
6. `myelin doctor` → error 0 → 보고. 고객명·시스템명·IP 가 답에 있으면 노트에는 쓰지 않고 `(비식별)` 로 치환했음을 알린다.

## 출력 노트 형식 (lesson)
```markdown
---
id: 20261018-1600-deadline-miss-wcet-assumption
type: lesson
domain: [D2]
status: draft
origin: claude
confidence: medium
classification: internal
share: false
source: ["interview:d2-deadline-miss"]
created: 2026-10-18
tags: [lesson, interview, d2-deadline-miss]
---
# 데드라인 미스의 원인은 측정이 아니라 가정에 있었다

## 상황
(사용자 답 요약, 1인칭)

## 무엇을 했고, 무엇이 일어났나

## 교훈 (다음에 다르게 할 것)

## 적용 조건 · 한계
```
