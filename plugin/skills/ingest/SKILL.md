---
name: ingest
description: 외부 자료(파일·PDF·URL·붙여넣은 글)를 읽고 MYELIN Vault의 00_Inbox/ai-drafts 에 literature 노트 초안을 만든다. 사용자가 /myelin:ingest 로 호출할 때만 쓴다.
argument-hint: "<파일 경로 | URL | 메모>"
disable-model-invocation: true
---
<!-- myelin:min-level 1 -->

# /myelin:ingest — 자료를 literature 노트 초안으로

대상: $ARGUMENTS

## 0. 사전 점검
1. Vault 루트의 `myelin.yaml` 을 읽는다. `level` 이 **1 미만**이면 아무것도 쓰지 말고
   "Level 1 이상이 필요합니다 — myelin.yaml 의 level 은 사람이 정합니다" 라고 알리고 멈춘다.
2. Vault `CLAUDE.md` 의 Write Policy와 `90_System/taxonomy.md` 의 용어를 따른다.
3. 대상이 `40_IP/` 이거나 confidential 노트면 Guard가 읽기를 막는다. 우회하지 말고 사람에게 알린다.

## 1. 읽기
- 파일·PDF는 Read, URL은 WebFetch로 읽는다. 대상이 없으면 사용자에게 물어본다.
- 자료가 길면 핵심 절만 읽고, 무엇을 읽었는지 적는다.

## 2. 쓰기 — 노트 하나
- 경로: `00_Inbox/ai-drafts/Lit - <짧은 제목>.md` (같은 이름이 있으면 뒤에 ` 2`)
- `domain`: `myelin.yaml` 의 domains 중 맞는 것 1~2개. 없으면 `[]`.
- 핵심 주장은 **자기 말로** 3~7개. 원문 인용은 꼭 필요한 짧은 구절만, 위치(쪽·절·타임스탬프)와 함께.
- 노트 id: `YYYYMMDD-HHmm-<영문 키워드 1~4개, 소문자-하이픈>` (예: `20261018-0930-ros2-executor`). 영문 키워드가 마땅치 않으면 `note` + 초 2자리.

<!-- myelin:output path="00_Inbox/ai-drafts/Lit - {{title}}.md" -->
```markdown
---
id: {{id}}
type: literature
domain: [{{domain}}]
status: draft
origin: claude
confidence: low
classification: internal
source: ["{{source}}"]
created: {{date}}
tags: []
---
# Lit - {{title}}

## 출처
- {{source}} — 읽은 범위: (예: 1~3장)

## 핵심 주장 (자기 말로)
- 

## 인용 위치
- 

## 연결 후보
- [[{{note}}]] — (연결 이유 한 줄)
```
<!-- /myelin:output -->

## 3. 보고
- 만든 파일 경로와 한 줄 요약.
- 다음 단계 제안: `/myelin:distill "<만든 파일>"` 로 원자 노트 분해.
- verified 승격은 사람이 Obsidian(또는 Hub)에서 한다고 알린다.
