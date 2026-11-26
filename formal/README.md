# formal/ — MYELIN 형식 검증 (WDLAB-STD-VERIFY-001 v1.0)

| concern | 대상 | 결과 |
|---|---|---|
| [`hub-config-stale-cache/`](hub-config-stale-cache/SCOPE.md) | Hub 가 캐시한 `myelin.yaml` vs CLI `myelin add-domain` vs Settings 저장 | **F1 FIXED** (2026-10-29) · **F2 FIXED** (2026-11-18, If-Match) · **F8 FIXED** (2026-11-18, `/api/vault`) · **F3 FIXED** (2026-11-26, CLI 가 건드린 경로만 커밋 — 모델 밖 부수 발견, 재현 스크립트·회귀 테스트로 확인) · **BOUNDED-PASS L2** `Doms={d1,d2}` 72 states / depth 7, `{d1,d2,d3}` 432 / depth 9 |
| [`review-gate-promote-toctou/`](review-gate-promote-toctou/SCOPE.md) | Review Gate: 읽기 → Promote 클릭 vs 초안을 다시 쓰는 writer | **F4 FIXED** (2026-11-18, digest) · **BOUNDED-PASS L2** `Notes={n1,n2}, MaxVer=2` 847 states / depth 14, `{n1,n2,n3}, MaxVer=3` 105,648 / depth 22 · **PROVEN L3** (Lean 4, sorry 0, 공리 propext) |
| [`hub-pack-save-atomicity/`](hub-pack-save-atomicity/SCOPE.md) | `PUT /api/packs/<name>`: 겹친 두 저장, 로더 거부, commit 거부 | **F5·F6 FIXED** (2026-11-18) · **BOUNDED-PASS L2** `Reqs={r1,r2}` 364 states / depth 9 |
| [`hub-onboard-atomicity/`](hub-onboard-atomicity/SCOPE.md) | `POST /api/onboarding`: 어느 단계에서든 실패 | **F7 FIXED** (2026-11-18) · **BOUNDED-PASS L2** 19 states / depth 8 (모델 전체) |
| [`mcp-config-revocation-stale/`](mcp-config-revocation-stale/SCOPE.md) | 장수명 MCP 서버가 기동 시 읽은 `myelin.yaml` vs 다른 프로세스의 동의 철회(`mcp.write_draft`·`level`·`mcp.expose_confidential`) | **F1 FIXED** (수정안 2026-11-21 브랜치 `wdproof/20261121-115639-myelin` → **2026-11-26 작업 트리에 반영**, 호출마다 바이트 비교 재적재·fail-closed) · **BOUNDED-PASS L2** `Calls={c1,c2}` 919 states, `{c1,c2,c3}` 5,531 · **PROVEN L3** (Lean 4, sorry 0, 공리 propext·Quot.sound) |

상태 갱신 **2026-11-26**: 미수정 CONFIRMED 0건. 2026-11-21 라운드의 *후보*(검증하지 않은 의심) 중 C2·C3·C5·C6 은 재현 테스트를 먼저 쓰고(수정 전 실패 확인) 고쳤다 — 아래 "후보 처리". C4·C7·C8 은 기록만(미수정).

보고서: [`reports/2026-11-21-mcp-config-revocation-stale.md`](reports/2026-11-21-mcp-config-revocation-stale.md) (MCP 라운드, wdproof 0.1.0) · [`reports/2026-11-18-myelin-hub.md`](reports/2026-11-18-myelin-hub.md) (Hub 라운드) · [`reports/2026-10-29-hub-config-stale-cache.md`](reports/2026-10-29-hub-config-stale-cache.md).
결과 파일: `findings.json`(hub-config-stale-cache) + `<concern>/findings.json`(나머지 넷; mcp-config-revocation-stale 는 wdproof 0.1.0 형식 — 그 실행의 후보표 `candidates.json` 동봉) — 모두 proof-skills 스키마 + `wdlab` 블록.

## 실행 (전체)
```bash
TLC_WORKERS=2 bash formal/run_all.sh                 # 3-config 게이트 31개 설정. FORMAL_NIGHTLY=1 이면 큰 경계 포함(32개)
bash formal/lean_audit.sh                            # Lean 2개 프로젝트: lake build + sorry 0 + 표준 공리만 (lean 4.34.0)
python3 formal/tools/correspondence_check.py formal/ --root .   # W6: 모델 ↔ 코드 포인터 (2026-11-26: 0 broken)
uv run pytest packages/myelin-hub/api/tests/test_formal_hub.py packages/myelin-hub/api/tests/test_config_reload.py \
  packages/myelin-hub/api/tests/test_formal_candidates.py packages/myelin-mcp/tests/test_formal_mcp_config_revocation.py -v
```

## hub-config-stale-cache (2026-10-29)
무엇을 모델링했나: 세 행위자(CLI 프로세스 · Hub 서버 · 브라우저 Settings 페이지)가 `<Vault>/myelin.yaml` 의 Domain 목록을 공유하는 인터리빙을 TLA+ 로 전수 탐색했다. 속성은 `tla/Properties.tla` 에 동결(P1 결정은 파일 기준, P2 Settings 저장은 Domain 을 지우지 않음). fix 토글 `ReloadOnRequest`(구현) · `IfMatch`(제안).

## 실행
```bash
TLC_WORKERS=4 formal/run_all.sh          # 이 concern: MC PASS · MC_bug/MC_bug_p2/MC_partial/MC_sanity FAIL(12) · MC_3 PASS
.venv/bin/python -m pytest packages/myelin-hub/api/tests/test_config_reload.py -v     # F1 재현 테스트 (수정 후 통과)
.venv/bin/python formal/hub-config-stale-cache/repro/repro_F2_settings_put_window.py  # F2: exit 0 (2026-11-18 수정) · --no-if-match 는 exit 1 (선택 헤더의 잔여)
.venv/bin/python formal/hub-config-stale-cache/repro/repro_F3_add_domain_commit_scope.py  # F3: exit 0 (2026-11-26 수정 · 그 전에는 exit 1)
```
TLC 는 `~/.cache/proof-skills/tla2tools.jar`(`$TLA2TOOLS` 로 지정 가능) + Java 21 을 쓴다. 루트 모듈은 `Properties.tla`(`EXTENDS Spec`).

## CI (W5/W6) — 2026-11-16
- 워크플로 [`.github/workflows/formal.yml`](../.github/workflows/formal.yml) (`name: formal-verification`, 기존 `ci.yml` 과 별개) — PR·`main` push(`formal/**` 와 CORRESPONDENCE.md 가 가리키는 소스 경로 변경 시), nightly 03:17 KST, 수동 dispatch. **fail-closed**: 어느 job 이든 실패하면 red.
- job `three-config-gate`: `formal/ci/setup_tla.sh` 로 고정 tla2tools v1.8.0 을 받아 `formal/run_all.sh` 실행 — MC·MC_3 PASS(0), MC_bug·MC_bug_p2·MC_partial·MC_sanity FAIL(12) 이 기대값. 기대값이 하나라도 어긋나면 게이트 실패(모델 약화·fix 토글 변경·사소한 스펙 훼손 감지). 로그는 `formal-evidence-<run_id>` 아티팩트(14일).
- job `drift-check` (W6): `formal/tools/correspondence_check.py formal/ --root .` — `src:` 태그와 CORRESPONDENCE.md 의 `path:line` 포인터가 저장소 루트 기준으로 모두 존재하고 줄 범위가 파일 안에 있는지 확인(**0 broken** 이어야 통과). PR 에서는 base 브랜치 이후 변경된 매핑 소스 파일 목록을 추가로 출력한다(정보용). 포인터는 **삭제가 아니라 갱신**으로 고친다.
- 재실행(로컬 = CI 와 동일): `export PROOF_SKILLS_TOOLS=$(mktemp -d) && bash formal/ci/setup_tla.sh && TLC_WORKERS=2 bash formal/run_all.sh` · `/usr/bin/python3 formal/tools/correspondence_check.py formal/ --root .` — 증거 `hub-config-stale-cache/evidence/ci_sim_run_all.log`, `ci_drift_check.log`.
- 리뷰 규칙: CORRESPONDENCE.md 대상 파일(`service.py`·`app.py`·`scaffold.py`·`config.py`·`Settings.tsx`·ADR·README)을 바꾸는 PR 은 스펙/대응표 갱신 여부를 확인한다(PR 템플릿 없음 — 이 줄이 체크리스트).
- `formal/ci/`·`formal/tools/` 는 proof-skills v0.1.1 (MIT) 의 CI 키트 사본이다. `tlc.sh`(단일 cfg 실행+트레이스 요약), `parse_tlc_trace.py`, `correspondence_check.py`.

## 파일
- `CANDIDATES.md` G0 후보표 · `findings.json` 기계 판독 결과(proof-skills 스키마 + `wdlab` 블록) · `TOOLCHAIN.lock` · `run_all.sh` · `ci/setup_tla.sh` · `tools/`(CI 키트)
- `<concern>/SCOPE.md` · `CORRESPONDENCE.md`(모델 ↔ `file:line`) · `tla/` · `evidence/`(TLC 로그·트레이스·테스트 전/후·mutation·패치 diff) · `repro/`(스위트 밖 재현 스크립트)
- `reports/2026-10-29-hub-config-stale-cache.md` 보고서 사본 (docx: `~/ai_project/Proof-Skills/MYELIN_ProofSkills_Report_2026-10-29.docx`)

예외 기록: hub-config-stale-cache·hub-pack-save-atomicity·hub-onboard-atomicity 는 유한 상태 속성이라 L2 까지만 주장한다(Lean 승격 없음). L3 는 review-gate-promote-toctou 한 건. 2026-10-29 보고서는 docx, 2026-11-18 보고서는 Claude Docs 아티팩트 + `reports/` 의 md 사본.

CI 추가(2026-11-18): job `lean-trust-audit`(`formal/lean_audit.sh`), nightly 에서 `FORMAL_NIGHTLY=1`.

## 2026-11-26 — 브랜치 수정 반영 · F3 · 후보 처리

실행 증거: `mcp-config-revocation-stale/evidence/run_all_2026-11-26.log`(31개 설정 모두 기대값, TLC 2026.10.28) · `lean_audit_2026-11-26.log`(두 프로젝트 clean).

| 항목 | 종류 | 처리 | 회귀 테스트 (수정 전 실패 확인) |
|---|---|---|---|
| mcp-config-revocation-stale **F1** | FIXED(브랜치에만 있었음) | `packages/myelin-mcp/src/myelin_mcp/service.py` — 도구 호출마다 `_reload_if_changed`(바이트 비교), 읽을 수 없거나 잘못된 파일이면 호출 거부 | `packages/myelin-mcp/tests/test_formal_mcp_config_revocation.py` (P1·P2, + Domain 목록·잘못된 설정 fail-closed) |
| 같은 실행의 부수 발견 F3(Domain 검증·`list_domains` 가 옛 설정) | 미검증 의심 | F1 의 호출별 재적재로 함께 해소 | `test_domain_list_follows_the_file_too` |
| 같은 실행의 부수 발견 F2(도구 **목록**은 기동 시 결정) · F4(호출 안의 수 ms 창) | 미검증 의심 | **미수정** — 철회 뒤 도구는 보이지만 호출이 거부된다(안전). F4 는 프로세스 간 원자성이 없어 남는다(SCOPE 가정 A5) | — |
| hub-config-stale-cache **F3** (CLI `git add -A`) | CONFIRMED | `myelin add-domain`·`myelin obsidian setup` 이 건드린 경로만 `git commit --only` — 무관한 미추적·수정·이미 스테이지된 파일은 그대로 남는다. `myelin init` 의 첫 커밋(방금 만든 Vault)은 전체 커밋 그대로 | `packages/myelin-cli/tests/test_cli.py::test_add_domain_commits_only_its_own_paths`, `::test_obsidian_setup_commits_only_obsidian_paths` · `repro_F3_*.py` exit 0 |
| 후보 **C2** hub-add-domain-stale-vault | 의심 → 재현됨 | `HubService.add_domain` 이 `_mutation` 안에서 현재 설정으로 다시 판단, 그 사이 파일이 바뀌었으면 409(재시도) | `packages/myelin-hub/api/tests/test_formal_candidates.py::test_c2_*` |
| 후보 **C3** commons-publish-base-branch | 의심 → 직렬화 누락 확인 | `commons_publish` 를 `@_serialised` 로 | `::test_c3_*` |
| 후보 **C5** promote-dest-check-then-write | 의심 → 재현됨 | 승격·기각이 배타 생성(`open("x")`)으로 쓰고, 충돌 시 남의 파일을 지우지 않고 409 | `::test_c5_*` (2건) |
| 후보 **C6** index-refresh-signature | 의심 → 재현됨(mtime 을 되돌린 같은 크기 재작성) | 색인 서명에 ctime 반영(`max(mtime, ctime)`, 스키마 불변) | `packages/myelin-core/tests/test_index.py::test_same_size_rewrite_with_restored_mtime_is_reindexed` |
| 후보 C4(롤백이 외부 쓰기를 덮음) · C7(재적재 중 색인 연결 닫힘 → 500) · C8(`.obsidian/` 빈 디렉터리 잔존) | 의심 | **미수정·미재현** — 재현 테스트를 쓰지 않았다. 영향 L×L 로 기록만 | — |

같은 결함 유형(기동 시 읽은 설정으로 권한 판정)을 다른 경로에서 점검한 결과: Hub 는 `_v()` 가 요청마다 재적재(F1·F8), MCP 는 위 수정, 새로 만든 Hub Team 모드 인증 파일도 요청마다 재적재한다(`LiveTeamAuth`, 철회 테스트 포함). 남는 것은 위 F2(도구 목록)뿐이다.

모델 ↔ 코드 포인터(CORRESPONDENCE.md·`src:` 태그)는 이번 변경으로 밀린 줄 번호를 기계적으로 다시 맞췄다(내용이 바뀌지 않은 줄 기준). 기존 네 concern 의 TLA+ 모델은 바꾸지 않았다 — 후보 C2·C3·C5·C6 의 수정은 모델에 편입하지 않았고 테스트로만 고정했다(L1).
