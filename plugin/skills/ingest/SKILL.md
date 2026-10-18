---
name: ingest
description: 파일·URL·PDF 를 literature 노트 초안으로 변환해 00_Inbox/ai-drafts 에 만든다 (출처·핵심 주장·인용 위치). Level ≥ 1.
argument-hint: "<파일 경로 | URL> [--domain D1]"
allowed-tools: Read, Glob, Grep, Bash(myelin *), Bash(git add *), Bash(git commit *), Write, WebFetch
---

# /ingest — 외부 자료 → literature 초안

공통 규약: `plugin/skills/_COMMON.md` (Vault·Level 확인 → 쓰기 범위 → Frontmatter v2 → doctor).

- 최소 Level: **1** · 쓰기 범위: **`00_Inbox/ai-drafts/`** 만.

## 절차
1. 입력을 읽는다. 로컬 파일은 Read, URL 은 WebFetch, PDF 는 Read(pages). `40_IP/` 안의 파일이나 `classification: confidential` 자료는 외부 모델로 요약하지 않는다 — 사용자에게 로컬 LLM 사용을 안내하고 멈춘다.
2. 출처 메타데이터를 확정한다: 제목, 저자/기관, 발행일, URL 또는 파일 경로.
3. 핵심 주장을 3~7개 추출한다. 각 주장에 **인용 위치**(페이지/섹션/문단 또는 인용문 20자 이내)를 붙인다.
4. 사용자가 `--domain` 을 주지 않았으면 `myelin.yaml` 의 Domain 중 가장 적합한 1~2개를 고르고 선택 근거를 한 줄로 보고한다. 확신이 없으면 `domain: []` 으로 두고 사람이 채우게 한다.
5. `90_System/templates/literature.md` 를 채워 `00_Inbox/ai-drafts/Lit - <짧은 제목>.md` 로 **새 파일**을 만든다. 같은 이름이 있으면 덮어쓰지 말고 ` (2)` 를 붙인다.
6. `myelin doctor` 실행 → 새 파일 error 0 확인 → 보고.

## 출력 노트 형식 (literature)
```markdown
---
id: 20261018-1430-lit-ros2-executor
type: literature
domain: [D2, D3]
status: draft
origin: claude
confidence: medium
classification: internal
share: false
source: ["https://docs.ros.org/en/rolling/Concepts/Intermediate/About-Executors.html"]
created: 2026-10-18
tags: [ros2, executor]
---
# Lit - ROS2 Executor

## 출처
- ROS 2 Documentation, "About Executors", Rolling (접근 2026-10-18)

## 핵심 주장 (인용 위치 포함)
1. SingleThreadedExecutor 는 콜백을 순차 처리하므로 긴 콜백이 전체 지연을 만든다 — §Executor types, 2문단
2. …

## 내 해석 · 반론
- (AI 초안: 사람이 채운다)

## 파생 원자 노트 후보
- [[Executor 선택은 WCET 예산과 함께 결정한다]]
```

## 하지 않는 것
- 10_Domains 에 직접 쓰기, 기존 노트 수정, verified 표시, Commons 공개.
