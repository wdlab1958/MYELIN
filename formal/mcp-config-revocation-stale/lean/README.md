# mcp-config-revocation-stale — Lean 4 승격 (S8, 무한 범위)

TLA+ 모델(`../tla/Spec.tla`, `FIX = TRUE`)은 `Calls = {"c1","c2"}` 범위에서 통과했다. 이 Lean 4 프로젝트는 같은 전이 시스템을 **호출(actor) 수와 단계 수에 제한 없이** 증명한다.

- 툴체인: `leanprover/lean4:v4.34.0` (`lean-toolchain` 고정), Mathlib 없음.
- 빌드: `lake build`
- `sorry` 없음, `axiom` 선언 없음, `native_decide` 사용 안 함. `#print axioms` 결과 표준 공리 `propext`, `Quot.sound` 만 쓴다.

## 파일

| 파일 | 내용 |
|---|---|
| `McpConfigRevocation/Spec.lean` | `Spec.tla` 를 옮긴 전이 시스템. `Call` 은 `DecidableEq` 인 임의 타입이라 호출 수에 상한이 없다. `Step fix` 는 `Open`, `Revoke(c)`, `Begin(r)`, `Check(r)`, `Prepare(r)`, `Release(r)`, `End(r)` 를 1:1 로 옮겼다. `Reachable fix` 는 `Init` 에서 유한 번 `Next` 로 갈 수 있는 상태 전체다. |
| `McpConfigRevocation/Proofs.lean` | 귀납 불변식 `Inv`, 보존 정리 `inv_step`, 정리 `P1_noDraftAfterRevoke`, `P2_noConfidentialAfterRevoke` (fix ON). |
| `McpConfigRevocation/BugWitness.lean` | fix OFF(`MC_bug.cfg` 대응) 증거. `Open → Revoke(expose) → Begin → Check(낡은 cache) → Prepare → Release` 경로로 `leakedX = 1` 에 도달한다(`bug_P2_violated`). Lean 모델도 실패할 수 있다는 것을 보인다. |

## 동결 안전 속성 대응

| ID | TLA+ | Lean 정리 | 범위 |
|---|---|---|---|
| P1 | `Inv_NoDraftAfterRevoke == leakedW = 0` | `P1_noDraftAfterRevoke : Reachable true s → InvNoDraftAfterRevoke s` | 임의 `Call` 타입, 임의 길이의 실행 |
| P2 | `Inv_NoConfidentialAfterRevoke == leakedX = 0` | `P2_noConfidentialAfterRevoke : Reachable true s → InvNoConfidentialAfterRevoke s` | 임의 `Call` 타입, 임의 길이의 실행 |

## 귀납 불변식 `Inv`

1. `leakedW = 0`, `leakedX = 0`
2. `checkRev`: `pc r = check` 이고 `revokedAtBegin r` 이면 디스크 값 `file (kind r) = false` 다. 철회는 단조(TRUE→FALSE만, SCOPE A3·A4)라서 `Begin` 과 `Check` 사이에 다른 프로세스가 철회해도 이 성질은 유지된다.
3. `passed`: `pc r ∈ {prepare, release}` 이면 `revokedAtBegin r = false` 다. fix ON 에서는 `Check` 가 디스크 값 `file[kind r]` 로 판정하므로, 통과한 호출은 2번에 따라 시작 시점에 철회되지 않은 호출이다.

`Release` 는 `pc r = release` 에서만 일어나고, 3번에 따라 유출 카운터를 늘리지 않는다.

## 승격하지 않은 것 (not promoted)

- **Liveness 속성**: 이 concern 의 `PROPERTIES.md` 에는 동결된 liveness 속성이 없다. 앞으로 추가되는 liveness/fairness 성질도 TLA+ 수준에 남긴다 (not promoted).
- `TypeOK` (T1, 동결 아님): 변수 치역은 Lean 타입(`Cap → Bool`, `Option Call`, `Call → PC` 등)이 구조적으로 보장한다. 카운터 상한 `0..Cardinality(Calls)` 는 유한 `Calls` 를 전제로 하므로 승격하지 않았다 (not promoted).
- `Sanity_ReleaseThenRevoke` (S1): 도달성 sanity 검사라서 TLA+ 수준에 남긴다 (not promoted). 대신 Lean 쪽 비공허성은 `bug_P2_violated` 가 보인다.
