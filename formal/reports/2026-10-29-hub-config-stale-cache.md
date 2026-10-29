# MYELIN 형식 검증 보고서 (WDLAB-STD-VERIFY-001)

- 프로젝트: **MYELIN** — Personal Knowledge OS (`~/ai_project/MYELIN`, branch `main`, GitHub `wdlab1958/MYELIN`)
- 검사한 commit: `70509a59a93e39103565731885e8763b51bbfa49` (수정 전 기준, "P9: docs(phase-state): Backlog 추가 — add-domain 이 작업 트리 전체를 커밋하는 문제, Hub myelin.yaml 변경 미반영, 일괄 ingest")
- 날짜: 2026-10-29 · 워크플로: W1 Bug hunt · 표준: WDLAB Unified Proof-Skills Standard v1.0 · 도구: proof-skills 0.1.1, TLA+/TLC 2026.10.28 (tla2tools v1.8.0), OpenJDK 21.0.12.1, pytest 9.1.1, ruff 0.17.1, mypy 2.4.0
- 작성: Claude (claude-fable-5-1) 에이전트 — HITL 승인 항목은 §7 참조. 수정 commit sha 는 §10.

## 1. 판정 요약

| 항목 | 값 |
|---|---|
| Concern | `hub-config-stale-cache` — Hub 프로세스가 기동 시 읽은 `<Vault>/myelin.yaml` 의 Domain 목록을 캐시한 채, CLI `myelin add-domain` 이 파일을 바꾼 뒤에도 옛 값으로 결정(promote 대상 Domain 검증 · Domain 목록 · Settings GET→PUT 되쓰기)을 내리는가 |
| Finding F1 | **FIXED** (severity high) — Hub 는 기동 시 1회만 `myelin.yaml` 을 읽었다. CLI 가 Domain 을 추가하면 ① 그 Domain 으로의 승격이 422 "not configured" 로 거부되고 ② Settings 저장이 옛 Domain 목록을 되써서 **CLI 의 추가가 파일에서 사라졌다**(폴더는 남아 doctor "미등록 domain"). TLC 반례 → pytest 재현(수정 전 실패 로그) → 최소 수정(`_reload_if_changed`) → 모델·테스트 재통과 → mutation 재실패 확인 |
| Finding F2 | **CONFIRMED** (severity medium, 미수정 · HITL) — Settings 저장은 `fetch(current)` → `PUT {...current}` 두 요청. 그 사이에 CLI 가 파일을 바꾸면 F1 수정 후에도 Domain 이 사라진다(창: 1 라운드트립). 수정안 If-Match/ETag 는 공개 API 변경 |
| Finding F3 | **CONFIRMED** (severity medium, 미수정 · 부수 발견) — CLI `add-domain`/`obsidian setup` 의 `git add -A` 가 무관한 사용자 파일을 `[myelin:add-domain]` 커밋에 넣고(ADR-0009 §4 위반), 미완성 노트가 섞이면 pre-commit 장치가 add-domain 커밋 자체를 거부 |
| 달성 레벨 | **L2** — F1 수정 후 모델 **BOUNDED-PASS** (`MC.cfg`: F1 구현 + F2 제안 토글 ON). **코드 그대로**(F1 ON, F2 OFF = `MC_partial.cfg`)는 P2 에서 FAIL — F2 가 열려 있음을 모델이 그대로 보여준다 |
| 경계 | `Doms = {d1, d2}`: 349 states generated / **72 distinct** / depth **7** · `Doms = {d1, d2, d3}`: 2,593 / **432 distinct** / depth **9**. 행위자 3(CLI · Hub · 브라우저 1 탭), Domain 추가만(제거 없음) |
| 신뢰 기반 | TLC 2026.10.28 + JVM 21; 추상화 A1~A8 (§5): myelin.yaml → Domain 집합, CLI 쓰기 원자성, 바이트 비교=즉시 일치, 브라우저 1 탭, git/부수 파일 생략 |
| 3-config | `MC.cfg` PASS(0) · `MC_3.cfg` PASS(0) · `MC_bug.cfg` FAIL(12, `P1_NoStaleDecision`) · `MC_bug_p2.cfg` FAIL(12, `P2_NoLostDomain`) · `MC_partial.cfg` FAIL(12, `P2` — F2) · `MC_sanity.cfg` FAIL(12, `S_NeverAcceptedAdded`) · `-coverage 1` 모든 action 활성 |
| 재현·회귀 | 재현 테스트 2건 수정 전 **실패** → 수정 후 **통과**; Hub API 스위트 **141 passed**(기존 139 + 2); ruff · mypy --strict 통과 |

> "검증됨"의 의미: 위 경계·추상화 내에서 P1·P2(F1+F2 토글 ON)·C1 에 반례가 없다는 것이다. 코드가 모든 입력·모든 동시 행위자에 대해 정확하다는 뜻이 아니며, 특히 F2 는 코드에 **아직 남아 있다**(§3.2).

## 2. 프로젝트 개요와 G0 후보표

MYELIN 은 Obsidian + Claude Code 기반 개인 지식 운영체계다. Python 모노레포(`myelin-core` 엔진 · `myelin-cli` · `myelin-mcp` · `myelin-hub` FastAPI API)와 React Hub 웹, Claude Code plugin(Skill 7종 + Guard hook)로 구성되며, 공유 자원은 `<Vault>/` 파일시스템 + git 이다. 동시 행위자는 **CLI 프로세스 · Hub 프로세스(스레드풀) · Obsidian/Claude Code(사용자) · 브라우저**다. 표준 §11 에 MYELIN 전용 지침은 없어 LLMOps/ARGUS-X(캐시·파이프라인)와 PatentForge-OP(여러 행위자의 동일 파일 편집) 지침을 준용했다. 검사한 commit 의 Backlog(`PHASE_STATE.md:136`)가 세 결함을 이미 호소하고 있어 이를 1차 후보로 삼았다.

| 순위 | 후보 | 위치 | 버그 클래스 | blast × conc. | 결정 |
|---|---|---|---|---|---|
| 1 | hub-config-stale-cache | `service.py:158-169 _v()`, `124-150 reload()`, `530-531 promote`, `648-676 settings/save_settings` ↔ `scaffold.py:277-360 add_domain` | stale cache(check-then-act) + lost update | **H × H** | **선택** → F1 FIXED, F2 CONFIRMED |
| 2 | add-domain-commit-scope (`git add -A`) | `app.py:88-128, 376-385` | 커밋 범위 / 감사 추적 오염 | M × M | F3 CONFIRMED (repro, 제안만) |
| 3 | settings-put-no-version (GET→PUT 창) | `Settings.tsx:17-20`, `service.py:652-676` | lost update (narrow window) | M × M | 1번 모델에 `IfMatch` 토글로 통합 → F2 |
| 4 | hub-mutation-rollback vs 외부 쓰기 | `service.py:177-211` | lost update(실패 경로) | L × M | 기록만 |
| 5 | index-refresh-vs-promote | `index.py`, `service.py:510-568` | stale cache | M × L | 기록만 — `_write_lock`+index lock 으로 직렬화 |
| 6 | obsidian-config-merge (`.obsidian/*.json` RMW vs Obsidian 앱) | `obsidian.py` | lost update | L × M | 기록만 — 외부 앱 동작 모델 불가 |
| 7 | ingest 파이프라인(dedup/손실/마지막 배치) | `plugin/skills/ingest/SKILL.md` | 데이터흐름 | — | **모델 대상 없음** — `/myelin:ingest` 는 Claude Code Skill(프롬프트)로 Python 배치 코드가 없다. "일괄 ingest" 는 기능 요청 |

선택 근거: Brian 이 운영 중 실제로 겪어 Backlog 에 적은 결함이고, 두 OS 프로세스가 동기화 없이 하나의 파일을 공유하는 전형적 stale-cache/lost-update 패턴(TLA+ `LostUpdate` + `CacheAside` 혼합)이며, 영향이 설정 파일(단일 원천) 손실과 Review Gate 오거부로 가장 크다.

## 3. Finding 별 상세

### 3.1 F1 — Hub 설정 캐시가 CLI `add-domain` 을 반영하지 못함 (FIXED)

**위반 속성 (동결, `tla/Properties.tla`)**

| ID | 속성 | 의미 | 출처 |
|---|---|---|---|
| P1 | `P1_NoStaleDecision == ~badReject /\ ~badAccept` | Hub 의 결정(promote 대상 Domain 검증·Domain 목록·Settings 응답)은 **현재** `myelin.yaml` 의 Domain 목록에 근거한다 | `PHASE_STATE.md:136`; ADR-0009 §3 (`docs/adr/0009-hub-write-policy.md:10` "Domain 이 설정된 것"); `README.md:17`; `service.py:554-555` |
| P2 | `P2_NoLostDomain == lost = {}` | Settings 저장은 `myelin.yaml` 에서 Domain 을 제거하지 않는다 — Settings 페이지는 Domain 을 편집하지 않으며(`Settings.tsx:17-19`), `domains.extra` 의 유일한 쓰기 주체는 add-domain 이다 | ADR-0004 §2 (`docs/adr/0004-myelin-yaml-schema.md:9`); `README.md:69`; `CLAUDE.md` "사용자 데이터 덮어쓰기 금지"; `service.py:676-700` |

**최소 트레이스 ① — P1 (`MC_bug.cfg`, `evidence/trace_bug_P1.md`, 2 steps)**

| # | 행위자 | Action | 코드 (CORRESPONDENCE) | 변경 |
|---|---|---|---|---|
| 1 | — | `Init` | `service.py:126-130 open() → reload()` (파일 1회 읽음) | `file = {}`, `cache = {}` |
| 2 | CLI | `CliAddDomain(d1)` | `scaffold.py:307-316, 352` (`extra += [d1]`, `myelin.yaml` 쓰기); `app.py:362-385` | `file = {d1}` |
| 3 | Hub | `HubPromote(d1)` ⚠ — `View = cache = {}` → 422 | `service.py:554-555` (수정 전 `_v()` 166-169 는 `self.vault` 를 그대로 반환) | `badReject = TRUE` → **P1 위반** |

**최소 트레이스 ② — P2, 캐시 경로 (`MC_bug_p2.cfg`, `evidence/trace_bug_P2.md`, 3 steps)**

| # | 행위자 | Action | 코드 | 변경 |
|---|---|---|---|---|
| 2 | CLI | `CliAddDomain(d1)` | `scaffold.py:352` | `file = {d1}` |
| 3 | 브라우저 | `BrowserGet` — `current` = 캐시 `{}` | `Settings.tsx:17` → `service.py:672-674 settings()` | `form = {}`, `formLoaded = TRUE` |
| 4 | 브라우저 | `BrowserPut` ⚠ — `{...current, level}` 되쓰기 | `Settings.tsx:18-20` → `service.py:676-700 save_settings()` | `file = {}`, **`lost = {d1}`** → **P2 위반** |

**코드 매핑** — `HubService.open()` 이 `reload()` 로 `Vault.open(root)` 를 1회 수행해 `self.vault.config` 에 보관(`service.py:124-150`, 수정 전). 이후 모든 읽기·쓰기는 `self._v()`(166-169) 로 그 객체를 받으며, `reload()` 는 `save_settings`(675) · `_onboard`(878) 에서만 다시 호출됐다. 반면 CLI `add_domain()` 은 별도 프로세스에서 `myelin.yaml` 을 통째로 다시 쓴다(`scaffold.py:352`). 두 프로세스를 잇는 장치가 없었다.

**재현 테스트** — `packages/myelin-hub/api/tests/test_config_reload.py` (Hub API 테스트 관례: `basic` fixture Vault 복사 + git init, `TestClient`, `X-Myelin-Intent: user-click`). CLI 는 **실제 별도 프로세스**(`python -m myelin_cli add-domain SEC-CONSULT`)로 실행해 트레이스의 `CliAddDomain` 을 그대로 재현한다. 외부 서비스 없음.

- `test_f1_hub_sees_domain_added_by_cli_without_restart` — 트레이스 ①: 승격 200 이어야 함(P1), 이어서 `/api/domains`·`/api/settings` 가 파일과 같아야 함.
- `test_f1_settings_save_keeps_domain_added_by_cli` — 트레이스 ②: GET→PUT 뒤 파일에 `SEC-CONSULT` 가 남아야 함(P2).

**수정 전 실패 로그 발췌** (`evidence/test_before.log`)
```
E       AssertionError: P1 violated (stale reject): 422 {"detail":"domain 'SEC-CONSULT' is not configured"}
E       assert 422 == 200
E       AssertionError: P2 violated (lost update): Settings save wrote the stale Domain list back
E       assert 'SEC-CONSULT' in ['D1', 'D3', 'D4', 'D2']
2 failed in 0.70s
```
두 실패 모두 **속성 단언**에서 일어났다(API/시그니처 변경 아님).

**수정 diff** (`evidence/patches/F1-hub-config-reload-on-change.diff`, `packages/myelin-hub/api/src/myelin_hub_api/service.py`, +27/−3) — 핵심 hunk:
```diff
+    _config_bytes: bytes | None = field(default=None, repr=False)  # myelin.yaml as last loaded
 ...
     def reload(self) -> None:
         self.config_error = None
+        self._config_bytes = self._read_config_bytes()
 ...
+    def _read_config_bytes(self) -> bytes | None:
+        try:
+            return (self.root / CONFIG_FILE).read_bytes()
+        except FileNotFoundError:
+            return None
+
+    def _reload_if_changed(self) -> None:
+        """Re-read myelin.yaml before any decision when it changed on disk. ..."""
+        if self._read_config_bytes() == self._config_bytes:
+            return
+        with self._write_lock:  # one reload at a time; writers already hold this lock
+            if self._read_config_bytes() != self._config_bytes:
+                self.reload()
+
     @property
     def ready(self) -> bool:
+        self._reload_if_changed()
         return self.vault is not None
 ...
     def _v(self) -> Vault:
+        self._reload_if_changed()
         if self.vault is None:
```
그 밖에 `packs()`·`save_pack()` 의 `self.vault` 직접 참조 2곳을 `self.ready`/`self._v()` 로 바꿨다. 최소 변경 원칙(§6.6): 기능 제거·무조건 early-return 없음. 바뀌는 입력 범위 = "파일 바이트가 마지막 로드와 다를 때"만 재파싱(mtime 아닌 바이트 비교 → 같은 tick 의 편집도 감지, 소형 파일 1회 읽기 비용). 유효하지 않은 파일로 바뀌면 기존 기동 시 의미와 같이 `config_error` + 409(fail-closed).

**수정 후 증거**
- `evidence/test_after.log`: `2 passed in 0.73s`.
- `evidence/regression_hub_api.log`: Hub API 전체 `141 passed in 38.10s`(기존 139 + 2). `ruff check/format`, `mypy --strict service.py` 통과.
- 모델 재검사 `evidence/tlc_fixed.log`: `MC.cfg` 72 distinct / depth 7, 위반 없음. `MC_3.cfg` 432 / depth 9 위반 없음.
- **mutation** `evidence/mutation.log`: 토글 OFF(`MC_bug.cfg`) → `P1_NoStaleDecision` 다시 위반(exit 12, 11 states); `MC_bug_p2.cfg` → `P2_NoLostDomain` 위반(42 states); 토글 ON → PASS. 속성이 실제로 이 버그를 지킨다.

### 3.2 F2 — Settings `PUT` 에 버전 검사가 없다 (CONFIRMED, 미수정 · HITL)

**트레이스 (`MC_partial.cfg` = F1 ON·F2 OFF = **현재 커밋의 코드**, `evidence/trace_partial_P2_F2.md`, 3 steps)**

| # | 행위자 | Action | 코드 | 변경 |
|---|---|---|---|---|
| 2 | 브라우저 | `BrowserGet` — `current` = 파일 `{}` (F1 로 신선함) | `Settings.tsx:17` → `service.py:672-674` | `form = {}` |
| 3 | CLI | `CliAddDomain(d1)` | `scaffold.py:352` | `file = {d1}` |
| 4 | 브라우저 | `BrowserPut` ⚠ | `Settings.tsx:18-20` → `service.py:676-700` | `file = {}`, **`lost = {d1}`** → **P2 위반** |

F1 수정 전에는 이 창이 Hub 수명 전체였고(트레이스 ②), 수정 후에는 **GET 과 PUT 사이 1 라운드트립**으로 줄었다. 그러나 "저장 클릭과 터미널 `add-domain` 이 겹치는" 경우 Domain 은 여전히 사라진다.

**재현** — `formal/hub-config-stale-cache/repro/repro_F2_settings_put_window.py` (스위트 밖 스크립트; `HubService.settings()` → `add_domain()` → `save_settings(current)`). 수정된 코드에서 실행 결과(`evidence/repro_F2_settings_put_window.log`): `myelin.yaml domains after save: ['D1','D3','D4','D2']` · `F2 VIOLATED (P2)` · `10_Domains/SEC-CONSULT/_MOC.md exists: True -> doctor: unregistered domain` · exit 1.

**제안 수정 (HITL 필요 — 공개 API 변경)** — 모델의 `IfMatch` 토글이 이 수정이다(ON 이면 `MC.cfg` PASS, mutation OFF 면 FAIL):
1. `GET /api/settings` 응답에 `version`(= `myelin.yaml` 바이트의 sha256, 또는 ETag 헤더) 추가; `PUT /api/settings` 가 `If-Match`/`base_version` 을 보내고 서버는 현재 파일과 다르면 **412** 로 거부; `Settings.tsx save()` 는 412 에 재조회 후 1회 재시도.
2. 대안(서버만, API 불변): `save_settings` 가 **폴더가 있는 Domain 을 제거하는 저장을 거부**(fail-closed) — 의도적 제거 UX 가 바뀌므로 역시 설계 결정.

### 3.3 F3 — CLI `add-domain` 이 작업 트리 전체를 커밋 (CONFIRMED, 부수 발견 · 미수정)

**속성(출처)** — ADR-0009 §4 (`docs/adr/0009-hub-write-policy.md:11`): "스테이징은 변경된 경로만(`git add -- path`), 무관한 사용자 변경은 커밋에 섞이지 않는다." Hub 의 `_stage()`(`service.py:292-301`) 는 이를 지키지만 CLI `_git_commit_vault`(`app.py:88-128`, `:105 git add -A`) 는 모든 호출자(`init`·`add-domain`·`obsidian setup`)에 `-A` 를 쓴다.

**재현** — `formal/hub-config-stale-cache/repro/repro_F3_add_domain_commit_scope.py` (`evidence/repro_F3_add_domain_commit_scope.log`), 수정 전 코드:
- **Case A**: 사용자 임시 파일 `30_Resources/wip-notes.txt` 가 `[myelin:add-domain] D2` 커밋에 포함 — `commit contains: ['.obsidian/graph.json', '10_Domains/D2/_MOC.md', '30_Resources/wip-notes.txt', 'CLAUDE.md', 'myelin.yaml']` vs `add-domain touched: 10_Domains/D2/_MOC.md, 90_System/taxonomy.md, CLAUDE.md, myelin.yaml, .obsidian/graph.json`.
- **Case B**: frontmatter 없는 미완성 노트 `20_Projects/wip-not-ready.md` 가 함께 스테이지되자 Vault pre-commit 장치(`doctor --staged`)가 거부 → `(git commit 생략: … ERROR schema 20_Projects/wip-not-ready.md …)` — add-domain 의 **자기 변경 7건이 커밋되지 않은 채** 남음(`git status`: `A 10_Domains/SEC-CONSULT/_MOC.md …`).

**제안 수정 (HITL — `init` 은 전체 스캐폴드 `-A` 가 의도이므로 분리 설계 필요)**: `_git_commit_vault(root, message, paths=None)` 에 `paths` 를 두고 `add-domain`·`obsidian setup` 은 `touched` 를 넘겨 `git add -- <paths>`(Hub `_stage` 와 동일), `init` 은 `-A` 유지. CLI 테스트에 `git show --name-only HEAD == touched` 단언 추가.

## 4. 검증된 것과 경계

| ID | 속성 | 결과 | 경계 | 증거 |
|---|---|---|---|---|
| P1 `P1_NoStaleDecision` | Hub 결정은 현재 파일 기준 | **holds** (F1 ON) · violated (F1 OFF) | `Doms={d1,d2}` 72 states/depth 7; `{d1,d2,d3}` 432/depth 9 | `tlc_fixed.log`, `tlc_fixed_doms3.log`, `tlc_bug.log` |
| P2 `P2_NoLostDomain` | Settings 저장이 Domain 을 지우지 않음 | **holds** (F1+F2 ON) · **violated** (F1 ON·F2 OFF = 현재 코드, `MC_partial`) · violated (둘 OFF) | 같음 | `tlc_fixed.log`, `tlc_partial.log`, `tlc_bug_p2.log` |
| C1 `TypeOK` | 변수 치역 | holds | 전 config | `tlc_fixed.log` |
| S1 `S_NeverAcceptedAdded` | 도달성(반드시 FAIL) | violated ✔ | 14 states/depth 4 | `tlc_sanity.log`, `trace_sanity.md` |
| coverage | 모든 action 활성 | `CliAddDomain 19:24`, `HubRestart 4:72`, `HubPromote 20:144`, `BrowserGet 9:72`, `BrowserPut 19:36` | `MC.cfg -coverage 1` | `tlc_coverage.log` |

경계의 뜻: Domain 2~3개, 브라우저 1 탭, Hub 재기동 임의 시점, Domain 추가만. 이 안의 **모든** 인터리빙에 반례가 없다는 것이지 코드가 정확하다는 뜻이 아니다. 특히 `MC_partial` 이 FAIL 인 것은 "현재 코드에는 F2 가 남아 있다"는 **정직한 상태 표시**다.

## 5. 신뢰 기반과 버그를 숨길 수 있는 추상화

- 신뢰: TLC 2026.10.28(tla2tools v1.8.0) · OpenJDK 21.0.12.1 · `Properties.tla` 의 동결 속성 문장 · pytest 9.1.1 재현 테스트.
- A1 `myelin.yaml` → Domain 집합. level/packs/commons/mcp 의 lost update 는 같은 메커니즘이나 미모델(Settings 가 쓰는 필드는 의도된 덮어쓰기).
- A2 CLI 쓰기 원자성. 실제 `Path.write_text` 는 truncate+write — Hub 가 그 틈에 읽으면 빈/부분 파일 → `ConfigError` → 409(fail-closed), 다음 요청에서 회복. **F1 수정이 새로 노출하는 창**이며 모델 밖. 완화책(후속): `save_config`/`add_domain` 의 tmp+`os.replace` 원자적 쓰기.
- A3 바이트 비교→재파싱 사이의 변경은 다음 `_v()` 에서 수렴한다고 가정.
- A4 Domain 제거 없음(CLI 명령 없음). 사용자의 수동 편집은 `CliAddDomain` 으로 포괄되지 않음.
- A5 브라우저 1 탭 · 폼은 domains 미편집. 여러 탭/사용자(Team 모드)는 미모델.
- A6 git commit · `CLAUDE.md` 재렌더 · `.obsidian` · 색인 갱신 생략. 동시 **읽기끼리**의 세부 인터리빙 미모델(쓰기는 `_write_lock` 직렬화; `_reload_if_changed` 도 같은 락으로 이중 검사).
- A7 `HubRestart` 공정성 없음. A8 Pack 검색 경로(`MYELIN_PACKS`/`<Vault>/packs`) 가 재로드 후에도 유효.
- 재현 테스트의 한계: 결정적 순차 실행(프로세스 간 경합을 순서로 고정)이며 스레드 동시성은 Hub 스위트의 기존 chaos 테스트에 맡김.

## 6. 재실행 명령어

```bash
cd ~/ai_project/MYELIN
TLC_WORKERS=4 formal/run_all.sh                       # 6 config 기대값 단언 (MC·MC_3 PASS, 나머지 FAIL 12) — 5초 미만
SAVE_EVIDENCE=1 formal/run_all.sh                     # + evidence/ 로그 갱신
.venv/bin/python -m pytest packages/myelin-hub/api/tests/test_config_reload.py -v   # F1 재현 테스트 (2 passed)
.venv/bin/python -m pytest packages/myelin-hub/api/tests -q                         # Hub API 회귀 (141 passed)
.venv/bin/python formal/hub-config-stale-cache/repro/repro_F2_settings_put_window.py       # F2: exit 1 (미수정)
.venv/bin/python formal/hub-config-stale-cache/repro/repro_F3_add_domain_commit_scope.py   # F3: exit 1 (미수정)
# 단일 config:
java -cp ~/.cache/proof-skills/tla2tools.jar tlc2.TLC -workers 4 -config MC_bug.cfg Properties.tla   # (cd formal/hub-config-stale-cache/tla)
```
`git stash` 로 수정 전 코드에서 `test_config_reload.py` 를 돌리면 `evidence/test_before.log` 와 같은 2 failed 가 재현된다.

## 7. HITL 승인 이력

| 게이트 | 항목 | 상태 |
|---|---|---|
| G2 | P1·P2 동결(`tla/Properties.tla`) | **pending Brian review** (2026-10-29) |
| G7 (F1) | `_reload_if_changed` 최소 수정 — 공개 API 불변, Backlog 가 지시한 방향("설정 파일 변경 감지 또는 요청마다 재로드") | 자동 적용, 감사 요청(`evidence/patches/`) |
| G7 (F2) | `PUT /api/settings` If-Match/ETag(공개 API 변경) 또는 "폴더 있는 Domain 제거 거부" | **pending** — 수정하지 않음 |
| G7 (F3) | CLI `_git_commit_vault(paths=touched)` vs `init -A` 분리 | **pending** — 수정하지 않음 |

## 8. 후속 제안

- **W5 CI 가드**: `make gate` 또는 `.github/workflows` 에 `formal/run_all.sh`(5초 미만) 추가; `MC_partial` 은 F2 수정 시 기대값을 PASS 로 바꾸어 "F2 닫힘"을 게이트로 기록.
- **W6 드리프트**: `CORRESPONDENCE.md` 등록 파일(`service.py`, `scaffold.py`, `Settings.tsx`, `app.py`) 변경 시 대응표 재검토.
- **W4 단순화**: F2 수정 후 사용자 가이드의 "add-domain 뒤 Hub 재시작" 안내(우회책, `HubRestart`)를 제거 가능.
- 새 concern 후보: `myelin_mcp.service` 의 설정 캐시(같은 패턴), `save_config`/`add_domain` 의 원자적 쓰기(A2), Hub `_mutation` 롤백 vs 외부 쓰기.
- **W7 Lean 승격**: 불필요 — 유한 상태 속성이며 Team 모드(다중 사용자 설정)가 생기면 재검토.

## 9. Definition of Done 체크리스트 (§15)

| 항목 | 상태 |
|---|---|
| SCOPE.md: 단일 concern, 포함/추상화/제외, 경계 | ✅ `formal/hub-config-stale-cache/SCOPE.md` |
| Properties: 출처 인용, 프로토콜 속성 동결 + HITL 기록 | ✅ (HITL **pending**) |
| CORRESPONDENCE.md: 모든 action ↔ file:line | ✅ |
| MC PASS / MC_bug FAIL / MC_sanity FAIL (로그) | ✅ + `MC_bug_p2`, `MC_partial`(F2 열림 표시), `MC_3` |
| 반례 → 결정적 재현, 수정 전 실패 로그, 속성 단언 실패 | ✅ F1 (pytest) · F2/F3 (repro 스크립트) |
| 수정 후 모델·테스트 통과, mutation 재실패 | ✅ F1 |
| (Lean) sorry 0 … | — 해당 없음(미설치, L3 미주장) |
| 패치 감사 기록, 무력화 수정 아님 | ✅ `evidence/patches/F1-hub-config-reload-on-change.diff` |
| findings.json (wdlab 블록), 판정 어휘 | ✅ `formal/findings.json` |
| Artifact 보고서 + reports/ 사본 | ⚠ docx 로 대체(Artifact HTML 미발행) · `formal/reports/2026-10-29-hub-config-stale-cache.md` |
| W5 CI 등록 여부 결정, W4 제안 | ⚠ 제안만(§8) — 등록은 Brian 결정 |

## 10. 변경 파일 목록과 git commit

| 파일 | 변경 |
|---|---|
| `packages/myelin-hub/api/src/myelin_hub_api/service.py` | F1 수정 (+27/−3) |
| `packages/myelin-hub/api/tests/test_config_reload.py` | 재현 테스트 2건 (신규) |
| `formal/` (README · TOOLCHAIN.lock · CANDIDATES.md · findings.json · run_all.sh · .gitignore) | 신규 |
| `formal/hub-config-stale-cache/` (SCOPE · CORRESPONDENCE · tla/ 6 config · evidence/ · repro/) | 신규 |
| `formal/reports/2026-10-29-hub-config-stale-cache.md` | 이 보고서 사본 |
| `README.md` | "형식 검증 — Oct.29, 2026" 섹션 추가 |

- 커밋: `__COMMIT_SHA__` (`main`, push 결과: `__PUSH_RESULT__`). `git log -1 --stat` 은 `formal/hub-config-stale-cache/evidence/git_commit.log`.
- 사용자의 다른 dirty 파일은 없었다(작업 전 `git status --porcelain` 빈 상태).
