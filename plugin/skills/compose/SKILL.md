---
name: compose
description: 목적·독자를 받아 Vault 의 verified 노트만 재료로 산출물 초안(설계서·제안서·보고서·특허 초안)을 80_Outputs/drafts 에 만든다. Level ≥ 2.
argument-hint: "<산출물 종류> --for <독자> [--domain D1,D2]"
allowed-tools: Read, Glob, Grep, Bash(myelin *), Bash(git add *), Bash(git commit *), Write
---

# /compose — Vault → 산출물 초안

공통 규약: `plugin/skills/_COMMON.md`. 최소 Level **2** · 쓰기 범위 **`80_Outputs/drafts/`**.

## 절차
1. 목적(산출물 종류)·독자·Domain 을 확인한다. Pack 의 `compose_targets`(MOC 상단 "산출물 목표") 와 맞으면 그 형식을 따른다.
2. **재료는 `status: verified` 노트만** 쓴다. unverified/draft 를 쓰려면 사용자에게 명시 허용을 받고, 본문에 `(미검증: [[…]])` 로 표시한다. `classification: confidential` 노트는 독자가 사내가 아니면 제외하고 그 사실을 알린다.
3. 개요 → 각 절에 근거 노트 링크(`[[제목]]`)를 달며 작성한다. 노트에 없는 주장은 만들지 않는다 — 빈 곳은 `(TODO: 근거 노트 필요)`.
4. `80_Outputs/drafts/<산출물명> v0.md` 로 만든다. frontmatter: `type: evergreen`, `domain` 은 재료 노트 Domain 합집합, `origin: claude`, `status: draft`, `classification` 은 재료 중 가장 높은 등급, `source` 에 재료 노트 링크 전부, `tags: [output, <종류>]`.
5. 산출물 끝에 `## 환류 후보` 절을 둔다 — 작성 중 재료 노트에 **없어서** 새로 정리한 주장·교훈·결정을 한 줄씩(출처 절 번호와 함께) 적는다. 없으면 "없음". 이 절은 `/distill <산출물 경로>` 가 원자 노트 초안으로 되돌리는 입력이다(환류).
6. 보고: 사용한 노트 수·제외한 노트(사유)·TODO 개수·환류 후보 수. 완성본 승격·`80_Outputs/` 이동은 사람이 한다. 환류 후보가 있으면 `/distill <산출물 경로>` 를 안내한다.
