# Scope: hub-config-stale-cache
- Project / Module: MYELIN / `packages/myelin-hub/api` (`HubService`) ↔ `packages/myelin-cli` + `myelin_core.scaffold.add_domain` ↔ Hub web `Settings.tsx`
- Verification Level Target: **L2** (TLA+/TLC bounded model check)
- Concern (한 문장): Hub 프로세스가 기동 시 읽은 `<Vault>/myelin.yaml` 의 Domain 목록을 메모리에 캐시한 채, 다른 프로세스(CLI `myelin add-domain`, 편집기)가 파일을 바꾼 뒤에도 옛 값으로 결정(promote 대상 Domain 검증 · Domain 목록 · Settings GET→PUT 되쓰기)을 내린다.
- Rank: blast radius **H** (myelin.yaml = 단일 원천; Domain 이 사라지면 `10_Domains/<D>/` 노트 전체가 doctor "미등록 domain" 오류) × concurrency **H** (CLI·Hub 두 OS 프로세스 + 브라우저가 동기화 없이 공유)
- Backlog 출처: `PHASE_STATE.md:136` "Hub 가 `myelin.yaml` 변경(add-domain)을 재시작 없이 반영하지 못함(설정 캐시) → 설정 파일 변경 감지 또는 요청마다 재로드"

## In scope
- 행위자 3: **CLI**(`CliAddDomain(d)`: Domain 1개를 extra 에 추가하고 파일을 다시 씀), **Hub 서버**(`HubPromote(d)`, `HubRestart`, 그리고 브라우저 요청의 서버측 처리), **브라우저 Settings 페이지**(`BrowserGet` = `fetch("/api/settings")`, `BrowserPut` = `userPut("/api/settings", {...current, level, mcp, commons})`).
- 공유 자원: `myelin.yaml` 의 Domain 집합(`file`), Hub 의 메모리 사본(`cache`), 브라우저의 폼 사본(`form`, `formBase`).
- 속성: **P1** 결정은 파일 기준(stale reject/accept 금지) · **P2** Settings 저장이 Domain 을 지우지 않음(lost update 금지) · **C1** TypeOK. 동결 파일 `tla/Properties.tla`.
- fix 토글 2개: `ReloadOnRequest`(**F1, 구현** — `service.py:159-192`) · `IfMatch`(**F2, 제안만** — 공개 API 변경이라 HITL).

## Abstracted (버그를 숨길 수 있는 추상화)
- A1 `myelin.yaml` 전체 → Domain ID 집합. level/packs/commons/mcp 필드의 lost update 는 같은 메커니즘이지만 모델에 없다(Settings 페이지가 편집하는 level/mcp/commons 는 "의도된 덮어쓰기"이므로 P2 대상이 아니다).
- A2 CLI 의 파일 쓰기는 원자적 1 action. 실제 `Path.write_text` 는 truncate+write 두 syscall — Hub 가 그 사이에 읽으면 빈/부분 파일 → `ConfigError` → 409(fail-closed), 다음 요청에서 회복. 이 창은 모델 밖.
- A3 Hub 의 "현재 파일 읽기"(fix)는 바이트 비교 후 재파싱 1 action. 비교·파싱 사이에 또 바뀌면 다음 `_v()` 가 다시 잡는다(수렴) — 모델은 즉시 일치로 본다.
- A4 primary/research/growth 고정, `extra` 만 변동. CLI 에 Domain **제거** 명령이 없어 추가만 모델링. 사람의 수동 편집(제거 포함)은 `CliAddDomain` 으로 포괄되지 않는다.
- A5 브라우저 1 탭, 폼은 domains 를 편집하지 않음(`Settings.tsx:17-19` 는 `current` 를 spread). 여러 탭/사용자는 미모델.
- A6 git commit · `CLAUDE.md` 재렌더 · `.obsidian` 설정 등 부수 쓰기 생략. HTTP 핸들러 1개 = 1 action(FastAPI threadpool 의 동시 요청 중 **읽기끼리**의 세부 인터리빙은 모델 밖; 쓰기는 `_write_lock` 으로 직렬화됨).
- A7 Hub 재기동(`HubRestart`)은 언제든 가능한 환경 action(공정성 없음).

## Out of scope
- MCP 서버(`myelin_mcp.service`)의 설정 캐시 — 같은 패턴 가능성, 별도 concern 으로 제안(§후속).
- Hub `_mutation` 롤백 vs 외부 쓰기(CANDIDATES 4), 색인 갱신 경합(5), Obsidian 설정 병합(6).
- CLI `add-domain` 커밋 범위(`git add -A`, CANDIDATES 2) — **F3** 로 기록만(repro 스크립트 포함).

## Tool choice & rationale
- **TLA+/TLC**: 세 행위자의 요청 인터리빙 전수 탐색이 목적. 자료구조 정확성·무한 N 증명은 불필요하고 Lean 4 는 미설치 → L2 목표. 가장 가까운 패턴은 `LostUpdate`(read-modify-write) + `CacheAside`(stale view) 혼합.

## Bounds
- `Doms = {d1, d2}` (MC.cfg): 349 states generated / **72 distinct** / depth **7** — PASS (P1, P2, C1).
- `Doms = {d1, d2, d3}` (MC_3.cfg): 2,593 / **432 distinct** / depth **9** — PASS.
- 반례 길이: P1 2 steps(MC_bug) · P2 3 steps(MC_bug_p2) · P2/F2 3 steps(MC_partial).
- 실행 시간: 각 1초 미만 (TLC 2026.10.28, workers=4).

## Properties (§10.3 수확 기록)
| ID | Property | Level | Source | Frozen |
|---|---|---|---|---|
| P1 | `P1_NoStaleDecision == ~badReject /\ ~badAccept` — Hub 의 결정(promote 대상 Domain 검증 등)은 현재 `myelin.yaml` 의 Domain 목록에 근거한다 | protocol | `PHASE_STATE.md:136`; ADR-0009 §3 `docs/adr/0009-hub-write-policy.md:10` ("Domain 이 설정된 것"); `README.md:17`; `service.py:554-555` | ✅ (HITL: G2 pending Brian review) |
| P2 | `P2_NoLostDomain == lost = {}` — Settings 저장은 `myelin.yaml` 에서 Domain 을 제거하지 않는다(Settings 페이지는 Domain 을 편집하지 않으며 `domains.extra` 의 유일한 쓰기 주체는 add-domain) | protocol | ADR-0004 §2 `docs/adr/0004-myelin-yaml-schema.md:9`; `README.md:69`; `CLAUDE.md` Engineering Rules "사용자 데이터 덮어쓰기 금지"; `Settings.tsx:17-19`; `service.py:676-700` | ✅ (HITL: G2 pending Brian review) |
| C1 | `C1_TypeOK` — 변수 치역 | code | `tla/Spec.tla` | — |
| S1 | `S_NeverAcceptedAdded == accepted = {}` — **반드시 FAIL**(CLI 추가 → Hub 수락 경로 도달성) | sanity | — | — |
| S2 | `S_NeverAllAdded == file # Doms` — 반드시 FAIL | sanity | — | — |

## HITL
`hitl_approvals: ["G2: pending Brian review (P1, P2 동결)", "G7(F2): pending — PUT /api/settings 버전 검사(If-Match)는 공개 API 변경", "G7(F3): pending — CLI 커밋 범위 변경은 init(-A 의도)과의 설계 분리 필요"]`
