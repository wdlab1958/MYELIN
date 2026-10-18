---
name: link
description: MYELIN Vault 노트나 Domain에 대해 연결할 노트와 MOC 갱신을 찾아 _patches 에 변경 제안(patch)으로 쓴다. 대상 노트는 직접 고치지 않는다. 사용자가 /myelin:link 로 호출할 때만 쓴다.
argument-hint: "<노트 경로 | Domain ID>"
disable-model-invocation: true
---
<!-- myelin:min-level 2 -->

# /myelin:link — 연결 제안 (patch)

대상: $ARGUMENTS

## 0. 사전 점검
1. `myelin.yaml` 의 `level` 이 **2 미만**이면 쓰지 말고 알린 뒤 멈춘다.
2. **어떤 노트도 직접 고치지 않는다.** 결과는 patch 파일 하나다. 적용은 사람이 한다.

## 1. 후보 찾기
- 대상 노트(또는 Domain의 `10_Domains/<ID>/` 노트들)의 핵심어로 Vault를 Grep한다.
- 링크 후보마다 근거를 **한 줄**로: 공통 개념 · 인과 · 대조 · 사례 중 하나.
- `status: verified` 가 아닌 노트는 MOC에 넣자고 제안하지 않는다.
- AI 초안(`origin: claude`, 미검증)을 verified 노트에서 링크하자고 제안하지 않는다 (doctor `failclosed_link`).
- 서로 다른 Domain을 잇는 후보는 따로 표시한다 — 가장 가치가 큰 연결이다.

## 2. 쓰기
- 경로: `_patches/YYYYMMDD-link-<영문-키워드>.md`

<!-- myelin:output path="_patches/{{slug}}-link.md" -->
```markdown
# Patch: 링크 제안 — [[{{note}}]]

> 생성: {{date}} · `/myelin:link` · 적용은 사람이 한다. 적용 후 이 파일은 지운다.

## 1. `{{note}}` 에 추가
- [ ] `## 연결` 아래에 `- 관련: [[...]] — <근거 한 줄>`

## 2. MOC 갱신
- [ ] `10_Domains/{{domain}}/_MOC.md` `## 핵심 Evergreen` 에 `- [[...]]`

## Cross-domain
- [ ] 

## 제안하지 않은 것 (이유)
- 
```
<!-- /myelin:output -->

## 3. 보고
- patch 경로, 제안 개수, Cross-domain 후보 수.
