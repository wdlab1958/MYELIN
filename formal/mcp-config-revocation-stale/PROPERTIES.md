# Properties: mcp-config-revocation-stale

반출 시점과 선형화 기준은 `SCOPE.md` A5·A9 를 따른다. "철회 후 시작된 호출" = 해당 권한의 철회가 `myelin.yaml` 에 기록된 뒤 서비스 락을 잡은(`Begin`) 도구 호출.

| ID | Property | Kind | Source | Frozen |
|---|---|---|---|---|
| P1 | `Inv_NoDraftAfterRevoke` — `mcp.write_draft: false` 또는 `level: 0` 이 디스크에 기록된 뒤 시작된 도구 호출은 `00_Inbox/ai-drafts/` 에 파일을 만들지 않는다. TLA+: `leakedW = 0` (ghost: 호출 시작 시 `file["write"] = FALSE` 였던 호출의 `Release` 횟수) | safety (invariant) | `docs/adr/0007-mcp-policy.md:9` ("`write_draft` 는 `mcp.write_draft: true` **그리고** `level >= 1` 일 때만"); `docs/spec/MYELIN_Rev2.0.md:604` ("Level ≥ 1 + 설정에서 명시 허용 시"); `docs/spec/MYELIN_Rev2.0.md:1020`; `packages/myelin-mcp/src/myelin_mcp/service.py:9-10` (모듈 docstring); `packages/myelin-mcp/src/myelin_mcp/service.py:233-236` (거부 메시지 "disabled (myelin.yaml mcp.write_draft: false or level 0)"); `docs/guides/mcp-setup.md:43,48`; `packages/myelin-hub/web/src/pages/Settings.tsx:53` (Hub 의 철회 UI); `PHASE_STATE.md:64`; 테스트 `packages/myelin-mcp/tests/test_mcp_adversarial.py:235-251`, `packages/myelin-mcp/tests/test_service.py:108-123` | ✅ |
| P2 | `Inv_NoConfidentialAfterRevoke` — `mcp.expose_confidential: false` 가 디스크에 기록된 뒤 시작된 도구 호출은 confidential/`40_IP/**` 노트의 본문을 응답에 넣지 않는다(검색 결과 포함). TLA+: `leakedX = 0` (ghost: 호출 시작 시 `file["expose"] = FALSE` 였던 호출의 `Release` 횟수) | safety (invariant) | `docs/adr/0007-mcp-policy.md:10` ("`false`(기본) 이면 … 검색 결과에서 제외 … 본문은 `[confidential — body withheld …]`"); `docs/adr/0011-confidential-routing-devices.md:41`; `docs/spec/MYELIN_Rev2.0.md:601` ("confidential은 local 클라이언트만"); `packages/myelin-mcp/src/myelin_mcp/service.py:5-8` (모듈 docstring); `packages/myelin-mcp/src/myelin_mcp/service.py:31` (`REDACTED`); `docs/guides/mcp-setup.md:49-51`; `packages/myelin-hub/web/src/pages/Settings.tsx:54`; `CLAUDE.md` Engineering Rules "Fail-closed"; 테스트 `packages/myelin-mcp/tests/test_service.py:16-48` | ✅ |
| T1 | `TypeOK` — 변수 치역(`file`, `cache ∈ [Caps → BOOLEAN]`, `registered ∈ BOOLEAN`, `lock ∈ Calls ∪ {NoCall}`, `pc`, `kind`, `revokedAtBegin`, 카운터 `∈ 0..Cardinality(Calls)`) | type invariant | `tla/Spec.tla` (작성 예정) | — |
| S1 | `Sanity_ReleaseThenRevoke == ~(released >= 1 /\ \E c \in Caps : ~file[c])` — **반드시 FAIL**: 반출과 철회가 한 실행 안에서 모두 도달 가능함을 보인다(모델이 공허하지 않음) | sanity (reachability) | 패턴 `consent-revocation/tla/Properties.tla` | — |

## 비고
- P1·P2 는 패턴 P06-1 `Inv_NoReleaseAfterRevoke` 를 권한별로 나눈 것이다. 차이는 A5: 패턴은 반출 순간의 권한을 보지만, 여기서는 호출 시작(락 획득) 순간의 디스크 권한을 본다. 설정 파일 읽기와 SQLite 읽기를 프로세스 간 원자적으로 묶을 수 없어서이며, 이 완화는 수 ms 창만 허용하고 C1 의 시간~일 단위 창은 그대로 잡는다.
- ADR-0007:9 의 "호출 시 거부가 아니라 도구 자체가 없다" 는 기동 시점 등록에 관한 문구다. 동결 속성은 **쓰기/반출이 일어나지 않음**만 요구하고, 철회 뒤 도구가 목록에 남는지는 요구하지 않는다(SCOPE Out of scope, side finding 후보).
