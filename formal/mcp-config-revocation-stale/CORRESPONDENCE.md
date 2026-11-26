# Correspondence: mcp-config-revocation-stale

경로는 모두 저장소 루트 기준 전체 경로로 적는다.
액션 경계: 서비스 락 획득, 모든 DB 호출(`index.refresh/search/body`), 파일 I/O, 외부 호출(stdio 응답, git)마다 나눈다. `async` 핸들러(`packages/myelin-mcp/src/myelin_mcp/server.py:47-149`)는 내부에 `await` 가 없고 `_guard` 로 동기 서비스 메서드를 부르므로, 핸들러 진입~락 획득 사이에 별도 경계는 없다.

## 상태 변수

| Model element | Kind | Source (file:line) | Abstraction / assumption |
|---|---|---|---|
| `file[c]` | variable | `<Vault>/myelin.yaml` `mcp.write_draft`, `level`, `mcp.expose_confidential` — 스키마 `packages/myelin-core/src/myelin_core/config.py:121-125,133` | A1: `file["write"] = write_draft ∧ level≥1`, `file["expose"] = expose_confidential`. Init 둘 다 TRUE(동의가 켜진 상태에서 시작) |
| `cache[c]` | variable | `packages/myelin-mcp/src/myelin_mcp/service.py:56` `VaultService.vault` (→ `vault.config`, `packages/myelin-core/src/myelin_core/vault.py:122-124`) | 프로세스 메모리 사본. `write_enabled`(`packages/myelin-mcp/src/myelin_mcp/service.py:84-85`)·`expose_confidential`(`packages/myelin-mcp/src/myelin_mcp/service.py:67-69`)이 읽는 값 |
| `registered` | variable | `packages/myelin-mcp/src/myelin_mcp/server.py:128` `if service.write_enabled:` → `write_draft` 도구 등록 | 기동 시 1회 결정. FALSE 면 클라이언트 호출은 "Unknown tool"(`packages/myelin-mcp/tests/test_mcp_adversarial.py:241-242`) |
| `lock` | variable | `packages/myelin-mcp/src/myelin_mcp/service.py:41-49` `_serialized` (`self._lock`, RLock `packages/myelin-mcp/src/myelin_mcp/service.py:58`) | 한 프로세스 안 호출 직렬화(A7). 재진입은 모델 밖(도구 간 중첩 호출 없음) |
| `pc[r]`, `kind[r]` | variable | 도구 호출 진행 단계·종류 | `kind ∈ {"write","expose"}`(A10) |
| `opened` | variable | `packages/myelin-mcp/src/myelin_mcp/server.py:161-168` `serve()` | 첫 `Open` 전에는 호출 없음 |

## 액션

| Model element | Kind | Source (file:line) | Abstraction / assumption |
|---|---|---|---|
| `Open` (기동·재기동) | action | `packages/myelin-mcp/src/myelin_mcp/server.py:163` `VaultService.open(vault)` → `packages/myelin-mcp/src/myelin_mcp/service.py:60-63` `Vault.open(root)` → `packages/myelin-core/src/myelin_core/config.py:167-180` `load_config`(파일 읽기); `packages/myelin-mcp/src/myelin_mcp/server.py:167` `build_server` → `packages/myelin-mcp/src/myelin_mcp/server.py:128` 등록 판정 | `cache' = file`, `registered' = file["write"]`. 색인 open(`open_index`, DB)은 정책과 무관해 같은 action 에 묶음. 재기동은 진행 중 호출이 없을 때만(`lock = NoCall`) — 프로세스 종료가 호출을 끊는 경우는 반출 없음으로 동등. 공정성 없음(A8) |
| `Revoke(c)` | action | Hub: `packages/myelin-hub/api/src/myelin_hub_api/app.py:518-523` `PUT /api/settings` → `packages/myelin-hub/api/src/myelin_hub_api/service.py:886-921` `save_settings` — 파일 쓰기 `packages/myelin-hub/api/src/myelin_hub_api/service.py:907`, git commit `packages/myelin-hub/api/src/myelin_hub_api/service.py:919`; UI `packages/myelin-hub/web/src/pages/Settings.tsx:25,53-54`. 그 밖에 CLI·편집기의 직접 수정 | `file' = [file EXCEPT ![c] = FALSE]`, 원자적 1 action(A3). 쓰기 시점(834)에 철회가 디스크에 반영된 것으로 본다(commit 846 은 MCP 판단에 영향 없음). 단조(A4) |
| `Begin(r)` | action | `packages/myelin-mcp/src/myelin_mcp/server.py:54-58,63-64,144-148` 핸들러 → `packages/myelin-mcp/src/myelin_mcp/server.py:154-158` `_guard` → `packages/myelin-mcp/src/myelin_mcp/service.py:48` `with self._lock` | 락 획득. `kind[r]` 비결정 선택; `kind = "write"` 는 `registered` 일 때만(미등록이면 호출 불가 = 반출 없음). ghost `revokedAtBegin[r] = ~file[kind[r]]` 기록(A5) |
| `Check(r)` | action | write: `packages/myelin-mcp/src/myelin_mcp/service.py:233-236` `if not self.write_enabled: raise`(→ `packages/myelin-mcp/src/myelin_mcp/service.py:84-85`). expose: `packages/myelin-mcp/src/myelin_mcp/service.py:135` `exclude_confidential=not self.expose_confidential`, `packages/myelin-mcp/src/myelin_mcp/service.py:139,151` `_hidden`(→ `packages/myelin-mcp/src/myelin_mcp/service.py:87-90`, `66-68`) | **FIX=FALSE**: `cache[kind]` 로 판정(현재 코드). **FIX=TRUE**: 호출 진입 시 `myelin.yaml` 바이트를 마지막 적재본과 비교해 다르면 `Vault.open` 재적재(Hub F1 `packages/myelin-hub/api/src/myelin_hub_api/service.py:271-284` 과 같은 방식) → `cache' = file` 후 판정. 재적재가 `ConfigError` 면 fail-closed(권한 FALSE)로 판정한다는 가정(A3). 판정 FALSE → `pc = "denied"`(MCPError 또는 본문 `REDACTED`) |
| `Prepare(r)` | action | write: `packages/myelin-mcp/src/myelin_mcp/service.py:237-282` (`NoteType` 검증, 제목 검증, 템플릿 파일 읽기 `249-255`, `mkdir` `277`, `safe_rel` `279`). expose: `packages/myelin-mcp/src/myelin_mcp/service.py:127` / `142` `self.index.refresh()` (DB), `packages/myelin-mcp/src/myelin_mcp/service.py:144-150` `index.get` (DB) | 정책과 무관한 파일 I/O·DB 호출을 한 경계로 묶음. 여기서 `Revoke` 가 끼어들 수 있으나 A5 에 따라 위반으로 세지 않음. 입력 검증 실패(MCPError)는 반출 없음과 같아 생략 |
| `Release(r)` | action | write: `packages/myelin-mcp/src/myelin_mcp/service.py:284-285` `target.open("x")` + `fh.write(text)`. expose: `packages/myelin-mcp/src/myelin_mcp/service.py:156` `self.index.body(note.path)` (DB) / `packages/myelin-mcp/src/myelin_mcp/service.py:129-136` `index.search(..., exclude_confidential=False)` (DB) | 반출 시점. `released' = released + 1`; `revokedAtBegin[r]` 이면 `leakedW`/`leakedX` 증가. write 후의 `index.refresh`·frontmatter 오류 삭제(`packages/myelin-mcp/src/myelin_mcp/service.py:288-293`)는 범위 밖 |
| `End(r)` | action | `packages/myelin-mcp/src/myelin_mcp/service.py:48-49` 락 해제 → `packages/myelin-mcp/src/myelin_mcp/server.py:54-65,144-148` 반환 → stdio 응답(외부 호출, `packages/myelin-mcp/src/myelin_mcp/server.py:168`) | `lock' = NoCall`, `pc = "done"`. 응답 전송 이후는 범위 밖(A9) |

## 속성·ghost

| Model element | Kind | Source (file:line) | Abstraction / assumption |
|---|---|---|---|
| `revokedAtBegin[r]` | ghost | — | `Begin` 시점 `~file[kind[r]]` (A5 선형화 기준) |
| `released`, `leakedW`, `leakedX` | ghost | — | 반출 총수, 권한별 철회 후 시작된 호출의 반출 수 |
| `Inv_NoDraftAfterRevoke` (P1) | invariant (frozen) | `docs/adr/0007-mcp-policy.md:9`; `docs/spec/MYELIN_Rev2.0.md:604`; `packages/myelin-mcp/src/myelin_mcp/service.py:9-10,232-235` | `leakedW = 0` |
| `Inv_NoConfidentialAfterRevoke` (P2) | invariant (frozen) | `docs/adr/0007-mcp-policy.md:10`; `docs/adr/0011-confidential-routing-devices.md:41`; `packages/myelin-mcp/src/myelin_mcp/service.py:5-8` | `leakedX = 0`; `is_local_session()` = TRUE 고정(A2, `packages/myelin-core/src/myelin_core/levels.py:66-68`) |
| `TypeOK` | invariant | `tla/Spec.tla` | 변수 치역 |
| `Sanity_ReleaseThenRevoke` | sanity invariant (must FAIL) | 패턴 `consent-revocation` | `~(released >= 1 /\ \E c \in Caps : ~file[c])` |
| `FIX` | constant | 제안 fix (미구현) — 참조 구현 `packages/myelin-hub/api/src/myelin_hub_api/service.py:271-284` | TRUE: `Check` 가 디스크 값으로 판정. FALSE: 기동 시 캐시로 판정 |

## 예상 최소 반례 (FIX = FALSE)
`Open → Revoke("write") → Begin(c1, write) → Check(c1) [cache=TRUE] → Prepare(c1) → Release(c1)` ⇒ `leakedW = 1` (P1 위반). expose 도 같은 모양으로 P2 위반.

## S4 모델 작성 결과 (`tla/Spec.tla`)
- 액션 목록은 계획과 같다: `Open`, `Revoke(c)`, `Begin(r)`, `Check(r)`, `Prepare(r)`, `Release(r)`, `End(r)`.
- 세부 구현: `FIX = TRUE` 의 `Check(r)` 는 판정과 함께 `cache' = file` 로 재적재를 반영한다(FALSE 면 `cache` 불변). `Begin` 은 `opened`(첫 `Open` 이후)와 `lock = NoCall` 일 때만 가능하다. `End` 는 `pc ∈ {"released","denied"}` 에서 락을 놓는다.
- 설정 파일: `MC.cfg`(FIX=TRUE, PASS, 919 distinct states), `MC_bug.cfg`(FIX=FALSE, P1 위반 — 7 상태 반례), `MC_bug_p2.cfg`(FIX=FALSE, P2만, FAIL), `MC_sanity.cfg`(FIX=TRUE, `Sanity_ReleaseThenRevoke` FAIL), `MC_3.cfg`(Calls 3개, PASS, 5531 distinct states).
