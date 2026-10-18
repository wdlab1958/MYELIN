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

## 2. 쓰기 — 구조화 patch (Hub에서 사람이 적용)
- **대상 노트 하나 = patch 파일 하나.** 경로: `_patches/YYYYMMDD-HHMM-<영문-키워드>.patch.md`
- `kind` 는 셋 중 하나:
  - `append` — 대상 끝(또는 `under:` 로 지정한 제목 구획의 끝)에 줄을 더한다. MOC 갱신은 이것으로.
  - `replace` — `## before` 가 대상 본문에 **정확히 한 번** 있어야 한다. `## after` 로 바꾼다.
  - `frontmatter` — `## set` 에 `tags`·`source`·`projects`·`aliases`·`confidence` 만. status·origin·classification 은 못 바꾼다.
- `target` 은 Vault 기준 경로. `40_IP/`·confidential 노트는 대상으로 삼지 않는다.
- `rationale` 은 한 줄 근거. Cross-domain 연결이면 `rationale` 앞에 `[cross-domain]` 을 붙인다.

<!-- myelin:output path="_patches/{{slug}}-link.patch.md" -->
```markdown
---
patch: 1
target: 10_Domains/{{domain}}/_MOC.md
kind: append
under: "## 핵심 Evergreen"
origin: claude
skill: link
created: {{date}}
rationale: 같은 개념을 다루는 verified 노트가 MOC에서 빠져 있음
status: proposed
---
## append
- [[{{note}}]]
```
<!-- /myelin:output -->

제안하지 않은 후보와 이유는 patch가 아니라 사용자에게 보고한다.

## 3. 보고
- patch 파일 목록(대상·kind), Cross-domain 후보 수, 제안하지 않은 후보와 이유.
- 적용은 사람이 MYELIN Hub → Review Gate → Patches 에서 diff를 보고 누른다.
