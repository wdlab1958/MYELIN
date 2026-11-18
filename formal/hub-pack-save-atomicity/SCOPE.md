# Scope: hub-pack-save-atomicity
- Project / Module: MYELIN / Hub — `myelin-hub/api` `HubService.save_pack()` (`PUT /api/packs/<name>`)
- Verification Level Target: **L2 (TLA+/TLC)**
- Concern (한 문장): 개인 Pack 저장이 다른 쓰기와 달리 직렬화되지 않고 실패 시 되돌리지도 않아, 겹친 두 저장이 서로를 실패시키거나 거부된 Pack 을 디스크에 남기고, commit 이 거부되면 "쓰였지만 커밋되지 않은" 상태가 된다.
- Rank: blast radius **M** (활성 Pack 의 pack.yaml 이 로더 거부 상태로 남으면 Hub 의 Domain 화면·doctor 가 PackError) × concurrency **M** (더블 클릭, 두 탭)
- Workflow: W1

## In scope
- `save_pack()` 의 파일 단계: 임시 파일 쓰기 → 백업 읽기 → move → `load_pack` → (복원 | commit)
- 같은 Pack 을 저장하는 요청 2개의 인터리빙 (FastAPI 는 동기 핸들러를 스레드풀에서 실행)
- commit 실패(pre-commit 장치 거부, git 오류)

## Abstracted (버그를 숨길 수 있는 추상화 명시)
- **A1 텍스트 3종.** pack.yaml 내용을 `O`(기존)·`A`·`B` 로만 구분. 로더 판정은 텍스트의 함수(모든 조합 탐색).
- **A2 한 action = 파일시스템 단계 하나.** 단계 내부(예: `write_text` 의 truncate→write)는 원자적으로 본다.
- **A3 sidecar 복사(`copy_from`)는 모델 밖.** 코드에서는 복사한 파일 목록을 기록해 실패 시 지운다(테스트 `test_pack_copy.py` 가 정상 경로를 덮음). 실패 경로의 sidecar 정리는 모델·재현 테스트 모두에 없다.
- **A4 commit 은 pack.yaml 한 파일의 스냅샷.** `.gitignore` 최초 생성, staging 세부는 생략.
- **A5 다른 프로세스(CLI, 편집기)가 같은 pack.yaml 을 쓰는 경우는 모델 밖** — `_write_lock` 은 Hub 프로세스 안에서만 유효.

## Out of scope
- `commons_publish()` 도 `@_serialised` 가 아니다(Commons clone 저장소에 commit/push). 반례를 만들지 않았으므로 수정하지 않고 후보로만 기록(CANDIDATES.md).
- `load_pack` 자체의 정확성.

## Tool choice & rationale
스레드 인터리빙 + 실패 경로 → TLA+. 상태 공간이 유한하고 작아 Lean 승격 불필요.

## Bounds
`Reqs={r1,r2}`, 제출 텍스트 ∈ {A,B} 모든 조합, 로더 판정 모든 조합, commit 실패 허용 — 364 states / depth 9.
