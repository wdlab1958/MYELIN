# MYELIN Hub 형식 검증 보고서

> 문서 기준: WDLAB-STD-VERIFY-001 v1.0 (Unified WDLAB Proof-Skills Standard) · 2026-11-18
> 대상: `wdlab1958/MYELIN` `packages/myelin-hub` (API + Web), 기준 커밋 `c29d83f`
> 작업 브랜치: `formal/hub-2026-11-18` (원격에 push 하지 않음 — 패치 파일로 전달)

## 1. 판정 요약

MYELIN Hub 에서 결함 6건을 모델로 찾아 실제 코드에서 재현했고, 모두 수정한 뒤 재검증했다. 달성 레벨은 L2(경계 내 전수 검사) 4건, 그중 Review Gate 한 건은 L3(Lean 4 무한 증명)까지 올렸다.

| concern | 판정 | 레벨 | 경계 | finding |
|---|---|---|---|---|
| review-gate-promote-toctou | **FIXED · BOUNDED-PASS · PROVEN** | L3 | TLC: 초안 2개·재작성 2회 847 states / depth 14, 초안 3개·재작성 3회 105,648 states / depth 22. Lean: 경계 없음 | F4 |
| hub-onboard-atomicity | **FIXED · BOUNDED-PASS** | L2 | 요청 1개 + 재시도, 모든 실패 지점, 19 states / depth 8 (모델 전체) | F7 |
| hub-pack-save-atomicity | **FIXED · BOUNDED-PASS** | L2 | 동시 저장 2개, 제출 텍스트·로더 판정 모든 조합, commit 실패 허용, 364 states / depth 9 | F5, F6 |
| hub-config-stale-cache (기존) | **FIXED · BOUNDED-PASS** | L2 | Domain 2개 72 states / depth 7, 3개 432 states / depth 9 | F2, F8 (F1 은 10-29 수정) |

| ID | 심각도 | 한 줄 | 위반 속성 | 판정 |
|---|---|---|---|---|
| F4 | high | 사람이 읽은 뒤 초안이 다시 쓰이면, 읽지 않은 글이 verified 가 된다 | P3 | FIXED |
| F7 | high | 온보딩이 실패하면 반쯤 만들어진 Vault 가 남고 재시도는 409 | P8·P9·P10 | FIXED |
| F5 | medium | Pack 저장 더블 클릭 → 두 번째 요청이 500 (외 2가지 변형) | P7 (P4·P5) | FIXED |
| F6 | medium | Pack 저장의 commit 이 거부돼도 파일은 쓰인 채로 남는다 | P6 | FIXED |
| F2 | medium | Settings 저장이 GET~PUT 사이에 추가된 Domain 을 지운다 | P2 | FIXED |
| F8 | low | `/api/vault` 만 옛 myelin.yaml 로 답한다 | P1 | FIXED |

수정 후 확인: 3-config 게이트 27개 설정 모두 기대대로(PASS 7 / 의도된 FAIL 20, nightly 경계 포함), Lean 감사 clean, 재현 테스트 7건 통과, 전체 테스트 1,291건 통과(수정 전 1,284건), ruff·mypy(strict)·웹 빌드 통과, Playwright e2e 12건 통과.

F2 와 F4 의 보장에는 조건이 하나 붙는다. 서버는 클라이언트가 보낸 버전(If-Match)·digest 가 있을 때만 검사한다. Hub UI 는 항상 보내지만, 이 값을 보내지 않는 클라이언트(스크립트, 옛 UI 빌드)는 검사받지 않는다. 필수로 바꾸는 것은 공개 API 변경이라 결정을 남겨 두었다(§6).

## 2. Finding

### F4 — 읽지 않은 글이 verified 가 된다 (high, FIXED)

**위반 속성 P3**: verified 가 된 내용은 사람이 Promote 를 누르기 전에 읽은 바로 그 내용이다. 출처: ADR-0009 "HITL 승격 — verified 승격은 Review Gate 에서 사람의 클릭으로만", "AI 는 초안만, 승격은 사람만"; Review 페이지의 "승격은 사람이 읽은 뒤에만".

**최소 트레이스** (`MC_bug.cfg`, 5 스텝)

| # | 행위자 | 동작 | 상태 |
|---|---|---|---|
| 1 | — | 초안 n1 이 v0 로 대기 | draft = v0 |
| 2 | 브라우저 | "내용 읽기" | 화면 = v0 |
| 3 | writer | skill·MCP·편집기가 초안을 다시 씀 | draft = v1 |
| 4 | 사람 | Promote 클릭 | 클릭이 본 것 = v0 |
| 5 | Hub | 지금 파일을 읽어 승격 ⚠ | verified = v1, 읽은 것 = v0 |

**코드**: `service.py promote()` 가 클릭 시점의 파일을 그대로 읽어 `status: verified`, `reviewed: 오늘`, `origin: mixed` 로 옮기고 commit 했다. 같은 파일의 `apply_patch()` 는 digest 로 이 상황을 막고 있었다.

**재현**: `test_formal_hub.py::test_f4_promote_never_verifies_text_the_human_did_not_read` — 수정 전 `P3 violated: 10_Domains/D2/Lit - 양자화 서베이.md is verified with text nobody read`, 수정 후 통과.

**수정**: `GET /api/notes/<path>` 가 본문과 같은 바이트에서 계산한 `digest` 를 함께 돌려준다. Review 페이지는 Promote 클릭에 그 digest 를 실어 보낸다. `promote()` 는 초안을 한 번만 읽고, digest 가 다르면 409 로 거부한다(이동·commit 없음). 409 를 받은 화면은 본문을 닫아 다시 읽게 한다.

**무한 증명 (Lean 4)**: `ReviewGate.verified_is_what_was_read` — 초안의 수, 내용, 재작성 횟수, 실행 길이에 제한 없이 P3 성립. inductive invariant(`init_inv` + `step_inv`). `sorry` 0, 사용 공리 `propext` 하나, `native_decide` 미사용. 수정 전 모델이 실제로 실패한다는 것(`unpatched_violates`)과 수정 후에도 승격이 가능하다는 것(`patched_can_promote`)도 정리로 넣었다.

### F7 — 실패한 온보딩이 반쯤 만든 Vault 를 남긴다 (high, FIXED)

**위반 속성 P8**(실패한 온보딩은 자기가 만든 것을 남기지 않는다) · **P9**(myelin.yaml 이 가리키는 개인 Pack 은 디스크에 있다) · **P10**(온보딩이 만든 Vault 에는 `[myelin:init]` commit 이 있다).

**상황**: 새 사용자가 기존 노트가 있는 폴더(쓰던 Obsidian 폴더)를 지정하고 마법사에서 Domain 을 직접 정의한다. Hub 는 개인 Pack → myelin.yaml·scaffold → welcome 초안 → `git init` 순으로 쓰고 첫 commit 을 시도한다. frontmatter 없는 기존 노트 때문에 Vault pre-commit 장치가 commit 을 거부한다(500). 수정 전 오류 처리기는 개인 Pack 만 지웠다.

**결과(수정 전)**: myelin.yaml 은 `me.my-domains` Pack 과 그 Domain 을 가리키는데 Pack 은 없다. commit 도 없다. 마법사를 다시 누르면 409 "Vault already initialised".

**재현**: `test_f7_failed_onboarding_leaves_nothing_and_can_be_retried` — 수정 전 `P8 violated: half-initialised Vault left behind — ['.claude', '.claude/settings.json', '.git', …]`, 수정 후 통과(실패 후 폴더가 원래대로, 원인 노트를 고치면 같은 요청이 성공).

**수정**: 온보딩이 첫 쓰기 전에 폴더 상태를 기록해 두고(`_OnboardUndo`), 실패하면 이 요청이 만든 것만 지운다 — scaffold plan 의 파일, welcome 초안, 전에 없던 `.myelin/`·`.git/`, 전에 없었고 지금 빈 디렉터리. 덮어썼을 수 있는 `.gitignore` 와 기존 개인 Pack 은 원래 바이트로 복원한다. 사용자의 기존 파일은 건드리지 않는다.

### F5 — Pack 저장만 직렬화되지 않았다 (medium, FIXED)

**위반 속성 P7**: 겹친 두 저장이 서로를 실패시키지 않는다. 출처: `_serialised` 의 설명 "a double click or two tabs must not race each other".

**최소 트레이스** (`MC_bug.cfg`): 두 요청이 같은 `pack.yaml.tmp` 를 쓴다 → 첫 요청이 move → 두 번째 요청의 move 가 FileNotFoundError → 500 "filesystem error". Pack 은 저장됐는데 화면은 "저장 실패".

같은 원인의 변형 두 가지를 TLC 가 더 찾았다. (a) 다른 요청의 텍스트를 로드하고 200 을 답한다(P5). (b) 로더가 거부한 두 저장이 서로의 텍스트를 "백업"으로 복원해 거부된 pack.yaml 이 디스크에 남는다(P4). 이 두 변형은 실코드에서 따로 재현하지 않았다 — 원인(잠금 누락)과 수정이 같고, 수정 후 모델에서 함께 사라진다.

**재현**: `test_f5_double_click_save_pack_never_fails_on_the_other_request` — 수정 전 `P7 violated (race): … [FileNotFoundError(2, 'No such file or directory')]`, 수정 후 통과.

**수정**: `save_pack` 에 `@_serialised`.

### F6 — commit 이 거부돼도 Pack 파일은 남는다 (medium, FIXED)

**위반 속성 P6**: 저장은 전부 아니면 전무. 출처: `_mutation` 의 설명 "the Vault is left either untouched or fully committed", ADR-0009 §2.

**재현**: `test_f6_save_pack_is_all_or_nothing_when_the_commit_is_refused` — pre-commit 이 거부하는 상태에서 저장 → 수정 전 `P6 violated: pack.yaml was written although its commit was refused`, 수정 후 통과.

**수정**: 첫 쓰기 이후 어떤 실패에서든(로더 거부·commit 거부) pack.yaml 을 이전 바이트로 복원하거나 삭제하고, 이 요청이 복사한 sidecar 와 만든 디렉터리를 지우고, staging 을 되돌린다.

### F2 — Settings 저장이 사이에 추가된 Domain 을 지운다 (medium, FIXED)

10-29 라운드에서 CONFIRMED 로 남겨 둔 건. **위반 속성 P2**: Settings 저장은 Domain 을 지우지 않는다.

**수정**: `GET /api/settings` 가 ETag(읽은 myelin.yaml 바이트의 digest)를 보내고, `PUT` 은 `If-Match` 가 현재 파일과 다르면 412(쓰지 않음). Settings 페이지는 412 를 받으면 다시 읽고 재시도한다(최대 2회).

**재현**: `test_f2_settings_put_between_get_and_put_keeps_domain` — 수정 전 `P2 violated (lost update): PUT /api/settings -> 200 dropped SEC-CONSULT`, 수정 후 통과. 기존 스크립트 `repro_F2_settings_put_window.py` 는 기본 실행 exit 0, `--no-if-match` 는 exit 1(선택 헤더의 잔여 — §6).

### F8 — `/api/vault` 만 옛 설정으로 답한다 (low, FIXED)

대응표 드리프트 점검(W6) 중 발견. F1 수정이 모든 결정을 `_v()`/`ready` 로 보냈는데 `summary()` 만 캐시를 직접 읽었다. **위반 속성 P1**. `summary()` 와 도움말 챗봇의 Vault 요약이 먼저 파일 변경을 확인하도록 고쳤다. 재현: `test_f8_vault_summary_is_not_built_from_a_stale_config`.

## 3. 검증된 것과 경계

- **PASS 의 의미는 "이 경계 안에서 반례 없음"이다.** L2 네 건은 §1 표의 경계 안 모든 인터리빙을 전수 탐색했다. hub-onboard-atomicity 는 모델의 상태 공간 전체다.
- **L3 는 한 건.** P3 는 모델 수준에서 모든 크기에 대해 증명됐다. 증명 대상은 Lean 모델이고, Python 코드가 그 모델과 같다는 것은 대응표와 재현 테스트가 받친다.
- **모든 모델이 실패할 수 있음을 확인했다.** concern 마다 수정 토글을 끈 설정이 동결 속성을 위반하고, 도달성 설정이 위반하며, 가드 하나를 바꾼 변이도 속성에 걸린다(`evidence/mutation.log`). 모든 action 이 실행됐다(`evidence/tlc_coverage.log`).
- **반례는 모두 수정 전 코드에서 속성 단언으로 실패했다**(`evidence/test_before.log`). 예외 한 건: 긍정 경로 테스트 `test_f4_promote_after_reading_again_succeeds` 는 수정 전 `digest` 필드가 없어서(KeyError) 실패했다.

- **F5 의 변형 두 가지(P4, P5)는 모델 반례만 있고 실코드 재현은 하지 않았다.** 판정 어휘로는 SUSPECTED 이며, 같은 수정(직렬화)으로 모델에서 사라졌다.
- CI 의 `lean-trust-audit` job 은 GitHub Actions 에서 실행해 보지 못했다. 같은 스크립트(`formal/lean_audit.sh`)를 로컬에서만 돌렸다.
- Claude Docs 보고서: https://claude.ai/artifact/DvaATHUsVFokSzcYN3v7ph

## 4. 신뢰 기반과 버그를 숨길 수 있는 추상화

**신뢰해야 하는 것**: TLC 2026.11.15 (tla2tools v1.8.0), Lean 4.34.0 커널 + 공리 `propext`, 각 `Properties.tla`·`Properties.lean` 의 속성 문장, `CORRESPONDENCE.md` 의 모델↔코드 대응(포인터 123개, 깨진 것 0).

**증명 범위 밖 — 여기서는 버그가 남아 있을 수 있다**

1. **digest·If-Match 를 보내지 않는 클라이언트.** 검사 대상이 아니다.
2. **프로세스 간 창.** `save_settings` 의 버전 검사와 파일 쓰기 사이, `promote` 의 읽기와 원본 삭제 사이(각 수 ms 이하)에 다른 프로세스가 쓰는 경우. 프로세스 간 잠금이 없다. 뒤의 경우 승격된 글은 읽은 글 그대로지만 writer 의 마지막 수정이 사라진다.
3. **digest 충돌.** sha256 앞 16 hex 가 같으면 같은 내용으로 본다.
4. **온보딩 되돌리기는 "이 요청이 만든 것"을 지운다.** 처리 중(1~2초)에 다른 프로그램이 같은 이름의 파일을 만들었다면 함께 지워질 수 있다. `init_vault` 가 파일을 쓰다 중간에 죽는 경우는 되돌리지 못한다.
5. **Pack 저장의 sidecar 복사.** 실패 시 정리 코드는 있으나 모델과 전용 테스트가 없다.
6. **수정하지 않고 기록만 한 후보**(`formal/CANDIDATES.md`): `commons_publish` 미직렬화, `apply_patch` digest 가 대상 노트를 덮지 않음, 설정 파일이 일시적으로 깨졌을 때 색인 연결 종료 경합, F3(CLI `git add -A`).

## 5. 재실행 명령

```bash
git checkout formal/hub-2026-11-18        # 또는 패치 적용: git am 0001-*.patch
uv sync --all-packages --group dev
bash formal/ci/setup_tla.sh               # tla2tools → ~/.cache/proof-skills

TLC_WORKERS=2 bash formal/run_all.sh      # 3-config 게이트 26개 설정 (FORMAL_NIGHTLY=1: 27개)
bash formal/lean_audit.sh                 # lean 4.34.0 필요: lake build + sorry 0 + 표준 공리
python3 formal/tools/correspondence_check.py formal/ --root .   # 123 pointers, 0 broken

uv run pytest packages/myelin-hub/api/tests/test_formal_hub.py -v   # 재현 테스트 7건
uv run pytest -q                                                     # 1291 passed, 2 skipped
(cd packages/myelin-hub/web && npm ci && npm run build && npx playwright test)   # e2e 12건
```

## 6. HITL 승인 이력 (WDLAB 확장)

이번 작업은 표준의 승인 게이트를 사람 없이 지나갔다. 아래는 모두 **Brian 확인 대기**이며, 패치는 브랜치/패치 파일로만 전달하고 원격에 push 하지 않았다.

| 게이트 | 항목 | 상태 |
|---|---|---|
| G2 | 속성 동결: P3 (Review Gate), P4~P7 (Pack 저장), P8~P10 (온보딩) | 2026-11-18 동결, 확인 대기 |
| G2 | P1·P2 (10-29 동결) | 확인 대기 (변경 없음) |
| G7 | F4: `POST /api/review/promote` 에 선택 필드 `digest`, `GET /api/notes` 응답에 `digest` 추가 | 확인 대기 (추가형 API 변경) |
| G7 | F2: `GET /api/settings` ETag, `PUT` 의 선택 헤더 `If-Match` → 412 | 확인 대기 (추가형 API 변경) |
| G7 | F7: 온보딩 실패 시 요청이 만든 파일 삭제 | 확인 대기 (§4-4 의 삭제 범위) |
| G7 | F5·F6·F8 | 확인 대기 (API 변경 없음) |
| G7 | F3 (CLI) | 10-29 부터 대기, 이번 범위 밖 |

**결정이 필요한 것**

1. `digest`(Promote)와 `If-Match`(Settings)를 **필수**로 할 것인가. 필수로 하면 §4-1 의 잔여가 닫힌다. 대신 이 값을 보내지 않는 기존 호출(테스트 다수 포함)은 428 로 거부된다.
2. 기존 노트가 있는 폴더의 온보딩을 **성공**시킬 것인가. 지금은 깨끗하게 실패하고 원인을 알려 준다. 첫 commit 이 MYELIN 이 만든 파일만 담도록 바꾸면(ADR-0009 §4 와 같은 방향) 기존 Obsidian 폴더에서도 온보딩이 된다.

## 7. Definition of Done

- [x] SCOPE.md: 단일 concern, 포함/추상화/제외, 경계 — concern 3개 신설, 1개 갱신
- [x] Properties: 출처 인용, 프로토콜 속성 동결 — HITL 승인은 대기
- [x] CORRESPONDENCE.md: 모든 action ↔ file:line — 123 포인터, 0 broken
- [x] MC PASS / MC_bug FAIL / MC_sanity FAIL (로그 저장)
- [x] 반례 → 결정적 재현, 수정 전 실패 로그 저장, 속성 단언에서 실패
- [x] 수정 후 모델·테스트 통과, 수정 되돌리면 다시 실패(mutation)
- [x] (Lean) sorry 0, 표준 공리만, native_decide 없음
- [x] 패치 감사 기록 (`evidence/patches/`), 무력화 수정 아님 — 기능 제거·무조건 early-return 없음. 추가된 거부 경로(409·412)는 "읽은 것과 다를 때"만 발동하고, 다시 읽은 뒤의 승격·저장이 성공함을 모델(`MC_sanity_reread`)과 테스트로 확인
- [x] findings.json (wdlab 블록, 판정 어휘) — concern 별 4개, 스키마 검증 통과
- [x] 보고서 발행 + `reports/` 사본
- [x] W5 CI 가드: `run_all.sh` 에 3개 concern 추가, `lean-trust-audit` job 추가. W4 단순화 제안 없음(삭제할 수 있다고 증명된 가드 없음)

## 8. 변경 파일

- 코드: `service.py`, `app.py`, `assistant.py`, `web/src/lib/api.ts`, `web/src/pages/Review.tsx`, `web/src/pages/Settings.tsx` (6개, +308 / −60)
- 테스트: `packages/myelin-hub/api/tests/test_formal_hub.py` (신규, 7건)
- 검증 산출물: `formal/review-gate-promote-toctou/`, `formal/hub-pack-save-atomicity/`, `formal/hub-onboard-atomicity/` (신규), `formal/hub-config-stale-cache/` (갱신), `formal/run_all.sh`, `formal/lean_audit.sh`, `formal/CANDIDATES.md`, `formal/README.md`, `formal/TOOLCHAIN.lock`, `.github/workflows/formal.yml`
