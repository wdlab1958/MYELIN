---
name: link
description: 노트 간 링크 후보와 근거를 찾고, MOC·노트 갱신을 _patches 제안 파일로 만든다 (직접 수정하지 않음). Level ≥ 2.
argument-hint: "<노트 경로 | Domain ID>"
allowed-tools: Read, Glob, Grep, Bash(myelin *), Bash(git add *), Bash(git commit *), Write
---

# /link — 링크 제안 → `_patches/`

공통 규약: `plugin/skills/_COMMON.md`. 최소 Level **2** · 쓰기 범위 **`_patches/`** 만. **10_Domains 의 노트·MOC 는 절대 직접 수정하지 않는다.**

## 절차
1. 대상(노트 1개 또는 Domain)의 verified/unverified 노트를 Read·Grep 으로 수집한다. `origin: claude` + `status: draft` 인 ai-drafts 노트는 **링크 대상에서 제외**한다(fail-closed 링크 위반 방지).
2. 링크 후보를 찾는다: 같은 용어(taxonomy 대표 용어)·같은 Sub-MOC·source 공유·제목 명사 겹침. 후보마다 **근거 한 줄**(어느 문장이 어떤 노트와 이어지는지).
3. MOC 누락 검사: Domain 의 verified 노트 중 `_MOC.md` 에서 링크되지 않은 것을 찾는다.
4. 제안을 `_patches/<YYYYMMDD-HHMM>-<slug>.patch.md` 로 만든다(ADR-0006 형식, 아래). 대상 파일 1개당 patch 1개. `kind: append` 를 기본으로, 기존 문장을 바꿔야 하면 `replace`(before 는 대상 파일에 정확히 한 번 존재하는 문자열).
5. 보고: patch 목록 + 각 근거. "Hub Review Gate 에서 승인하면 적용됩니다" 를 덧붙인다.

## patch 파일 형식 (ADR-0006)
```markdown
---
patch: 1
target: 10_Domains/D2/_MOC.md
kind: append
origin: claude
skill: link
created: 2026-10-18
rationale: verified 노트 2건이 D2 MOC 에서 링크되지 않음 (ISR 로그, WCET 예산)
status: proposed
---
## append
- [[ISR 안에서 로그를 찍지 않는다]]
- [[WCET 예산은 측정값의 1.5배로 잡는다]]
```
`replace` 는 `## before` / `## after` 두 섹션, `frontmatter` 는 `## set` 섹션(`key: value` 줄).
