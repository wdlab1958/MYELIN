---
name: ip-scan
description: MYELIN Vault에서 Domain이 둘 이상인 verified 노트를 살펴 특허 가능 아이디어 후보를 40_IP/candidates 에 confidential 초안으로 쓴다. 사용자가 /myelin:ip-scan 으로 호출할 때만 쓴다.
argument-hint: "[Domain ID]"
disable-model-invocation: true
---
<!-- myelin:min-level 3 -->

# /myelin:ip-scan — 특허 후보 찾기

범위: $ARGUMENTS (비어 있으면 전체 Domain)

## 0. 사전 점검
1. `myelin.yaml` 의 `level` 이 **3 미만**이면 쓰지 말고 알린 뒤 멈춘다.
2. `40_IP/` 의 기존 아이디어는 읽을 수 없다 (로컬 LLM 전용). 그러므로 이 Skill의 결과는 **후보**일 뿐이며,
   기존 아이디어와의 중복 확인은 사람이 한다.
3. 직무발명·공개 시점 규정은 소속 조직의 정책을 따른다. 후보를 외부로 보내지 않는다.

## 1. 찾기
- `10_Domains/**` 에서 `status: verified` 이고 `domain` 이 2개 이상인 노트를 찾는다.
- 노트 조합에서: 해결하는 문제 → 기존 방식의 한계 → 새로운 구성 → 효과 순으로 후보를 세운다.
- 후보마다 신규성 근거를 한 줄로. 약하면 버린다. 최대 3개.

## 2. 쓰기 — 후보마다 하나
- 경로: `40_IP/candidates/YYYYMMDD-<영문-키워드>.md`
- 반드시 `classification: confidential`, `share: false`.

<!-- myelin:output path="40_IP/candidates/{{slug}}.md" -->
```markdown
---
id: {{id}}
type: idea-ip
domain: [{{domain}}]
status: draft
origin: claude
confidence: low
classification: confidential
share: false
source: ["[[{{note}}]]"]
created: {{date}}
tags: [ip, candidate]
---
# 후보: {{title}}

## 해결하려는 문제

## 기존 방식의 한계

## 핵심 구성 (청구항 후보)
1. 

## 효과

## 근거 노트 (verified)
- [[{{note}}]]

## 사람이 확인할 것
- [ ] 40_IP 기존 아이디어와 중복 여부
- [ ] 선행기술 조사
```
<!-- /myelin:output -->

## 3. 보고
- 후보 수와 경로만 알린다. 후보 내용을 대화에 길게 반복하지 않는다.
