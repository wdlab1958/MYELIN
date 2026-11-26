# Scope: mcp-config-revocation-stale

- Project / Module: MYELIN / `packages/myelin-mcp` (`VaultService`, `build_server`, `serve`) ↔ 설정 철회 주체(Hub `PUT /api/settings` → `HubService.save_settings`, CLI·편집기의 `myelin.yaml` 수정)
- Candidate: **C1** (`formal/candidates.json`) · 출발 패턴: **consent-revocation (P06)**
- Verification Level Target: **L2** (TLA+/TLC bounded model check)

## Concern (한 문장)
MCP 서버 프로세스가 기동 시 읽은 `myelin.yaml` 사본으로 `write_draft` 허용과 confidential 본문 노출을 판정하기 때문에, 다른 프로세스가 `mcp.write_draft`·`level`·`mcp.expose_confidential` 철회를 디스크에 커밋한 **뒤에 시작된** 도구 호출이 여전히 초안 파일을 만들거나 confidential 본문을 돌려준다.

## In scope
- 행위자 2 종류:
  - **설정 철회 주체**(Hub Settings 저장, CLI·편집기) — `Revoke(c)`: 권한 `c ∈ {"write", "expose"}` 를 디스크에서 FALSE 로 만든다(원자적 1 action).
  - **MCP 서버 프로세스 1개** — `Open`(기동/재기동: 설정 적재 + 도구 등록), 그리고 도구 호출 `r ∈ Calls` 마다 `Begin(r)`(서비스 락 획득·도구 종류 선택) → `Check(r)`(정책 판정) → `Prepare(r)`(색인 refresh·템플릿 읽기 등 DB/파일 I/O) → `Release(r)`(반출 시점) → `End(r)`(락 해제·stdio 응답).
- 공유 상태: 디스크의 권한 값 `file[c]`, MCP 프로세스의 설정 사본 `cache[c]`, 기동 시 결정되는 도구 등록 여부 `registered`, 서비스 락 `lock`.
- 반출 시점(release point) 정의:
  - write: `target.open("x")` 로 `00_Inbox/ai-drafts/<title>.md` 를 만드는 순간(`packages/myelin-mcp/src/myelin_mcp/service.py:284-285`).
  - expose: confidential 노트의 본문이 색인에서 읽혀 응답 dict 에 들어가는 순간(`get_note` `packages/myelin-mcp/src/myelin_mcp/service.py:156`, `search_notes` 의 `exclude_confidential=False` 질의 `packages/myelin-mcp/src/myelin_mcp/service.py:129-136`).
- 속성: **P1** `Inv_NoDraftAfterRevoke` · **P2** `Inv_NoConfidentialAfterRevoke` (동결) · `TypeOK` · Sanity `Sanity_ReleaseThenRevoke`.
- fix 토글 `FIX`:
  - `FALSE` = 현재 코드: `Check` 가 `cache` 를 본다.
  - `TRUE` = 제안 fix: 도구 호출마다(서비스 락 안에서) `myelin.yaml` 바이트가 마지막 적재본과 다르면 다시 읽는다 — Hub F1 `_reload_if_changed`(`packages/myelin-hub/api/src/myelin_hub_api/service.py:271-284`)와 같은 방식. `Check` 가 디스크 값을 본다.

## Abstracted (버그를 숨길 수 있는 추상화)
- **A1 설정 → 권한 2비트.** `file["write"]` = `mcp.write_draft ∧ level ≥ 1`, `file["expose"]` = `mcp.expose_confidential`. 나머지 필드(domains, packs, commons)는 모델 밖. `level` 철회와 `write_draft` 철회를 한 비트로 합쳤으므로 둘 중 하나만 바뀌는 경우의 차이는 볼 수 없다(판정식이 AND 라 결과는 같다).
- **A2 `is_local_session()` = TRUE 고정.** EXTERNAL 프로세스에서는 `expose_confidential` 이 항상 FALSE(ADR-0011 §3)라 철회 문제가 생기지 않는다. 환경 변수 `MYELIN_LLM` 은 프로세스 수명 동안 바뀌지 않는다고 가정한다.
- **A3 철회는 원자적 1 action.** 실제 `Path.write_text` 는 truncate+write 두 syscall 이다. fix 가 그 사이에 읽으면 빈/부분 파일 → `ConfigError`. fix 는 이 경우 fail-closed(권한 FALSE 로 판정)여야 한다는 가정을 CORRESPONDENCE 에 적는다. 부분 파일 창 자체는 모델 밖이며, fix 가 ConfigError 를 "이전 캐시 유지"로 처리하면 이 추상화가 버그를 숨긴다.
- **A4 철회만, 재허용(grant) 없음.** `file[c]` 는 TRUE → FALSE 단조. 권한 재허용 후 도구가 등록되지 않는 것(재기동 필요)은 안전성이 아니라 가용성 문제라 범위 밖.
- **A5 호출 시작 시점 선형화.** P1/P2 는 "철회가 디스크에 커밋된 뒤 **락을 잡은(Begin)** 호출"만 위반으로 센다. 한 호출 안에서 `Check` 와 `Release` 사이(색인 refresh, 템플릿 읽기 — ms 단위)에 철회가 들어오는 경우는 위반으로 세지 않는다. 설정 파일 읽기와 SQLite 읽기/파일 생성은 프로세스 간 원자적으로 묶을 수 없으므로, 호출 진입 시점의 설정을 그 호출의 정책으로 본다(패턴 README "반출 시점" 정책 결정의 기록).
- **A6 노트 분류 고정.** 반출 대상 confidential 노트 1개, 그 `classification`·경로(`40_IP/`)는 변하지 않는다. 색인 서명 비교 누락(C6)은 모델 밖.
- **A7 MCP 프로세스 1개.** 여러 Claude Code 세션이 각자 MCP 서버를 띄우면 각 프로세스가 독립된 같은 모델이다. 한 프로세스 안의 호출은 `_serialized`(RLock)로 직렬화되므로 `lock` 으로 모델링한다.
- **A8 `Open`(재기동)은 언제든 가능한 환경 action, 공정성 없음.** 사용자가 Claude Code 를 재시작하면 캐시가 갱신된다. 재기동을 강제하지 않으므로 bug 반례가 존재한다.
- **A9 반출 이후는 범위 밖.** 응답이 stdio 로 나가 외부 LLM 컨텍스트에 들어가는 것은 되돌릴 수 없으며, `Release` 이후 단계의 철회는 다루지 않는다.
- **A10 도구 종류.** 반출 경로를 write(초안 생성)·expose(confidential 본문/검색 결과) 두 종류로 축약한다. `query_frontmatter`·역링크(`_hidden_path`)는 expose 와 같은 판정식(`expose_confidential`)을 쓰므로 expose 로 포괄한다.

## Out of scope
- Hub 쪽 설정 캐시(이미 `formal/hub-config-stale-cache` F1 로 수정).
- `write_draft` 도구 목록 등록 자체의 갱신(ADR-0007 §2 "도구 자체가 없다"). fix 후에도 등록 목록은 기동 시 기준이라, 철회 뒤 도구는 보이지만 호출이 거부된다 — 안전성은 유지되나 ADR 문구와의 차이는 side finding 으로 기록한다. MCP `tools/list_changed` 알림은 범위 밖.
- 권한 재허용(A4), 색인 갱신 정확성(C6), Hub add_domain·rollback·Commons 게시(C2–C5, C7, C8).
- `write_draft` 의 제목·경로 검증, frontmatter 오류 시 삭제(`packages/myelin-mcp/src/myelin_mcp/service.py:241-293`의 나머지 분기).

## Tool choice & rationale
- **TLA+/TLC**: 문제는 두 OS 프로세스(Hub/CLI ↔ MCP) 사이의 설정 상태와 캐시의 인터리빙이며, 작은 유한 상태에서 전수 탐색하면 반례(`Open → Revoke(c) → Begin → Check → Prepare → Release`)가 바로 나온다. 데이터 구조 정확성·무한 N 증명은 필요 없으므로 Lean 은 쓰지 않는다. consent-revocation 패턴의 `Revoke / Check / Fetch` 를 `Open`(캐시 적재)·`Begin`·`Prepare` 로 정제하고, ghost `leaked` 를 권한별로 나눈다.

## Bounds
- `MC.cfg`: `Calls = {c1, c2}`, `Caps = {"write", "expose"}`, `FIX = TRUE` → P1·P2·TypeOK PASS 기대.
- `MC_bug.cfg`: 같은 경계, `FIX = FALSE` → P1 또는 P2 위반 기대(최소 반례 6 steps 예상).
- `MC_sanity.cfg`: 같은 경계, `FIX = TRUE`, 불변식 `Sanity_ReleaseThenRevoke` → 위반(반출과 철회가 한 실행에서 모두 도달) 기대.
- 추가 확인(선택): `Calls = {c1, c2, c3}` 로 상태 수 증가만 확인.
- `Open` 횟수는 제한하지 않는다(상태는 유한: `cache`·`registered` 가 불리언).
