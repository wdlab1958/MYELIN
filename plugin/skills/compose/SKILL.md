---
name: compose
description: 목적·독자에 맞춰 MYELIN Vault의 verified 노트를 조합해 산출물 초안(설계서·제안서·보고서·특허 명세 골격)을 80_Outputs/drafts 에 쓴다. 사용자가 /myelin:compose 로 호출할 때만 쓴다.
argument-hint: "<목적> [독자] [노트·Domain]"
disable-model-invocation: true
---
<!-- myelin:min-level 2 -->

# /myelin:compose — 지식의 재투입

요청: $ARGUMENTS

## 0. 사전 점검
1. `myelin.yaml` 의 `level` 이 **2 미만**이면 쓰지 말고 알린 뒤 멈춘다.
2. 목적·독자·분량이 불분명하면 **먼저 한 번** 묻는다.

## 1. 재료 모으기
- 근거는 `status: verified` 노트만 쓴다. 초안(draft)을 쓰려면 사용자의 허락을 받고 표시한다.
- 노트 목록을 먼저 보여주고 동의를 받은 뒤 쓴다.
- `40_IP/` 와 confidential 노트는 읽지 않는다 (Guard가 막는다). 특허 관련은 `/myelin:ip-scan` 을 쓴다.

## 2. 쓰기
- 경로: `80_Outputs/drafts/YYYYMMDD-<영문-키워드>.md`
- 주장마다 근거 노트를 `[[노트]]` 로 단다. 근거 없는 주장은 `(근거 필요)` 로 표시한다.
- 노트에 없는 사실을 지어내지 않는다.

<!-- myelin:output path="80_Outputs/drafts/{{slug}}.md" -->
```markdown
# {{title}}

> 초안 · `/myelin:compose` · {{date}} · 독자: (예: 팀 리더) · 근거: verified 노트 N개

## 요약

## 본문
- 주장 — 근거 [[{{note}}]]

## 근거 노트
- [[{{note}}]]

## 열린 질문 · 근거 필요
```
<!-- /myelin:output -->

## 3. 보고
- 경로, 사용한 근거 노트 수, "(근거 필요)" 개수.
