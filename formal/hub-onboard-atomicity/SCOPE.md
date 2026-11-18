# Scope: hub-onboard-atomicity
- Project / Module: MYELIN / Hub — `myelin-hub/api` `HubService.onboard()` (`POST /api/onboarding`)
- Verification Level Target: **L2 (TLA+/TLC)**
- Concern (한 문장): 온보딩이 중간 단계에서 실패하면 개인 Pack 만 지워지고 myelin.yaml·scaffold·.git 은 남아, "Pack 이 없는 Vault"가 되고 재시도는 409 로 막힌다.
- Rank: blast radius **H** (신규 사용자의 첫 15분. 사내 확산 대상자가 기존 Obsidian 폴더를 지정하면 바로 걸린다) × concurrency **L** (단일 요청의 실패 경로 — 인터리빙이 아니라 모든 실패 지점 전수)
- Workflow: W1

## In scope
- `onboard()` 의 쓰기 4단계(개인 Pack → `init_vault` → welcome/runtime → git init + 첫 commit)와 각 단계 뒤의 실패
- 실패 후 재시도 가능 여부

## Abstracted (버그를 숨길 수 있는 추상화 명시)
- **A1 단계는 원자적.** `init_vault` 가 파일을 쓰다가 중간에 OSError 로 죽는 경우(디스크 가득 등)는 모델 밖이다. 이 경우 scaffold plan 을 받지 못해 Hub 는 그 파일들을 지우지 못한다(코어 `init_vault` 의 원자성 문제 — 후보로 기록).
- **A2 파일 집합을 불리언 4개로.** pack / config / scaffold / repo.
- **A3 "요청이 만든 것만 지운다"는 코드 사실에 의존.** 되돌리기는 scaffold plan 의 파일 목록(`init_vault` 가 exclusive-create 로 만든 것), welcome 초안, 요청 전에 없던 `.myelin/`·`.git/`, 요청 전에 없었고 지금 비어 있는 디렉터리만 지운다. 요청 처리 중(1~2초)에 다른 프로그램이 같은 이름의 파일을 만들었다면 함께 지워질 수 있다.
- **A4 요청 전에 있던 `packs/me.my-domains/pack.yaml` 은 원래 바이트로 복원.**

## Out of scope
- CLI `myelin init` (Hub 범위 밖).
- 기존 폴더의 사용자 노트를 첫 commit 에 넣는 `git add -A` 정책 자체(ADR-0009 §4 와의 관계) — 설계 선택이라 제안으로만 기록.

## Tool choice & rationale
실패 지점 전수 탐색 → TLA+ (작은 순차 모델). Lean 불필요.

## Bounds
요청 1개 + 실패 후 재시도 무제한, `Custom ∈ {TRUE, FALSE}` — 각 19 states / depth 8 (전체 상태 공간).
