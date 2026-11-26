# Correspondence: hub-config-stale-cache

Spec commit: `70509a59a93e39103565731885e8763b51bbfa49` (수정 전). **2026-11-18 갱신**: 줄 번호는 F1·F2·F8 패치 적용 후(`c29d83f` + Hub 패치) 기준. "수정 전" 이라고 적은 줄 번호는 70509a5 의 것.

## Map

| Model element | Code | Kind | Abstraction | Notes |
|---|---|---|---|---|
| `file` | `<Vault>/myelin.yaml` `domains.extra` — `packages/myelin-core/src/myelin_core/config.py:167-186 load_config()`, `:200-203 save_config()` | variable | Domain ID 집합 ⊆ `Doms`; 다른 필드 생략(A1) | 디스크의 진실 |
| `cache` | `packages/myelin-hub/api/src/myelin_hub_api/service.py:218-225 HubService.vault` (`Vault.config`), 채워지는 곳 `packages/myelin-hub/api/src/myelin_hub_api/service.py:233-254 reload()` | variable | Domain 집합 | 수정 전엔 `open()`·`save_settings`·`_onboard` 에서만 갱신 |
| `form`, `formBase`, `formLoaded` | `packages/myelin-hub/web/src/pages/Settings.tsx:21-23` `res = await fetch("/api/settings")`; `current = await res.json()`; `etag = res.headers.get("ETag")` | variable | 폼 = GET 응답의 domains; `formBase` = 그 시점 파일 = ETag(myelin.yaml 바이트의 digest) | `IfMatch` 토글이 비교하는 값 |
| `accepted`, `badReject`, `badAccept`, `lost` | — (history/witness 변수) | variable | 속성 판정용 | 코드에 대응 없음 |
| `View` | `packages/myelin-hub/api/src/myelin_hub_api/service.py:291-295 _v()` → `packages/myelin-hub/api/src/myelin_hub_api/service.py:267-279 _reload_if_changed()` (fix ON) / 수정 전 `_v()` 는 `self.vault` 를 그대로 반환 (fix OFF) | definition | 바이트 비교+재파싱을 즉시 일치로 봄(A3) | **F1 fix toggle `ReloadOnRequest`** |
| `CliAddDomain(d)` | `packages/myelin-core/src/myelin_core/scaffold.py:277-360 add_domain()`: `:307-316` extra 추가, `:352` `(vault.root / CONFIG_FILE).write_text(dump_config(new_cfg))`; 호출자 `packages/myelin-cli/src/myelin_cli/app.py:414-437` | action | 원자적 쓰기(A2); MOC/템플릿/CLAUDE.md/.obsidian/commit 생략(A6) | 별도 OS 프로세스 |
| `HubRestart` | `packages/myelin-hub/api/src/myelin_hub_api/service.py:227-231 HubService.open()` → `reload()` | action (env) | 운영자의 재기동 = 오늘까지의 우회책 | 공정성 없음(A7) |
| `HubPromote(d)` | `packages/myelin-hub/api/src/myelin_hub_api/service.py:662-715 promote()`: `v = self._v()` (658), `if target_domain not in v.config.domains.all_ids: raise HubError(..., 422)` (679-680); 라우트 `packages/myelin-hub/api/src/myelin_hub_api/app.py:472-475`. 동일 패턴: `domains()` `packages/myelin-hub/api/src/myelin_hub_api/service.py:529-569`, `summary()` `packages/myelin-hub/api/src/myelin_hub_api/service.py:438-455` (**F8**: 2026-11-18 까지 `summary()` 만 재로드 없이 `self.vault` 를 읽었다 → 430 행에서 `_reload_if_changed()`), 도움말 챗봇 `packages/myelin-hub/api/src/myelin_hub_api/assistant.py:387-391` | action | 결정 1개 = 1 action; 초안 파일 이동·commit 생략 | P1 witness 갱신 |
| `BrowserGet` | `packages/myelin-hub/web/src/pages/Settings.tsx:21-23` → `packages/myelin-hub/api/src/myelin_hub_api/app.py:434-439 GET /api/settings` (ETag 헤더) → `packages/myelin-hub/api/src/myelin_hub_api/service.py:874-879 settings_versioned()` | action | 서버 처리 포함 1 action | `cache' = View` 는 fix ON 일 때 `_v()` 의 재로드를 반영 |
| `BrowserPut` | `packages/myelin-hub/web/src/pages/Settings.tsx:24-26` `next = {...current, level, mcp, commons}; userPut("/api/settings", next, {"If-Match": etag})` → `packages/myelin-hub/api/src/myelin_hub_api/app.py:506-513 PUT /api/settings` → `packages/myelin-hub/api/src/myelin_hub_api/service.py:881-918 save_settings()`: 버전 검사→412 (815-822), `MyelinConfig.model_validate(data)` (824), `myelin.yaml` 쓰기 (830), `_commit` (842), `self.reload()` (843) | action | commit·CLAUDE.md 재렌더 생략; `IfMatch` 분기(412)는 2026-11-18 구현(F2). 검사와 쓰기 사이(같은 함수 안, μs~ms)에 다른 프로세스가 쓰는 경우는 A2 로 추상화 | P2 witness `lost' = lost ∪ (file \ form)` |
| `P1_NoStaleDecision` | `tla/Properties.tla` ← `PHASE_STATE.md:136`, `docs/adr/0009-hub-write-policy.md:10`, `README.md:32` | invariant | 프로토콜 수준(동결) | |
| `P2_NoLostDomain` | `tla/Properties.tla` ← `docs/adr/0004-myelin-yaml-schema.md:9`, `README.md:84`, `CLAUDE.md`, `packages/myelin-hub/web/src/pages/Settings.tsx:24-25` | invariant | 프로토콜 수준(동결) | |
| `ReloadOnRequest` | **F1 패치** `packages/myelin-hub/api/src/myelin_hub_api/service.py:261-295` (`_read_config_bytes`, `_reload_if_changed`, `ready`, `_v`), `reload()` 가 바이트 기록(233), `packs()`·`save_pack()` 의 `self.vault` 직접 참조를 `self.ready`/`_v()` 로; **F8 패치** `packages/myelin-hub/api/src/myelin_hub_api/service.py:439` | constant (fix) | | `evidence/patches/F1-hub-config-reload-on-change.diff` |
| `IfMatch` | **F2 패치** `packages/myelin-hub/api/src/myelin_hub_api/app.py:434-439` (ETag), `packages/myelin-hub/api/src/myelin_hub_api/app.py:211-219` `_etag_value`, `packages/myelin-hub/api/src/myelin_hub_api/app.py:506-513` (If-Match), `packages/myelin-hub/api/src/myelin_hub_api/service.py:874-879`, `packages/myelin-hub/api/src/myelin_hub_api/service.py:888-895` (412), `packages/myelin-hub/web/src/pages/Settings.tsx:19-31` (412 면 다시 읽고 재시도, 최대 2회) | constant (fix) | `If-Match` 가 없는 PUT 은 검사하지 않는다(선택 헤더 — 스크립트·구버전 UI) | `evidence/patches/F2-F8-settings-if-match-summary-reload.diff` |

## Assumptions

- A1 설정 파일의 다른 필드는 Domain 과 같은 운명이지만 모델 밖. Settings 페이지가 쓰는 level/mcp/commons 는 의도된 덮어쓰기.
- A2 CLI 쓰기 원자성(실제 truncate+write; 창 안의 읽기는 409 fail-closed 후 회복). `BrowserPut` 도 한 action — `save_settings` 안의 버전 검사와 파일 쓰기 사이에 CLI 가 쓰는 경우(프로세스 간 잠금 없음)는 모델 밖이며 그 창에서는 P2 가 깨질 수 있다.
- A3 바이트 비교→재파싱 사이의 추가 변경은 다음 요청에서 수렴.
- A4 Domain 제거는 모델 밖(CLI 명령 없음; 수동 편집 미모델).
- A5 브라우저 1 탭; 폼은 domains 미편집.
- A6 git·부수 파일·동시 읽기 인터리빙 생략; 쓰기는 `_write_lock` 직렬화.
- A7 `HubRestart` 는 공정성 없는 환경 action.
- A8 Hub 는 `MYELIN_PACKS`/`<Vault>/packs` 에서 Pack 을 다시 찾을 수 있다(`_v()` 재로드 후 `domains()` 가 Pack 메타를 읽음). 테스트는 `MYELIN_PACKS` 를 repo `packs/` 로 둔다.

## Granularity

- 1 action = **HTTP 요청 핸들러 1개**(서버측 처리 포함) 또는 **CLI 의 myelin.yaml 쓰기 1회**. 브라우저의 저장 클릭은 `fetch`(GET) 와 `userPut`(PUT) 두 요청이므로 **두 action** 으로 분리했다 — 그 사이에 CLI 가 끼어드는 것이 F2 의 창이다.
- 합친 곳: `add_domain()` 의 여러 파일 쓰기(MOC·templates·taxonomy·CLAUDE.md·myelin.yaml·.obsidian)를 myelin.yaml 쓰기 하나로. 다른 파일은 P1/P2 가 읽지 않는다.
- 합친 곳: fix ON 의 `_reload_if_changed()`(read bytes → compare → `reload()` → `Vault.open` 재읽기)를 요청 action 안에 흡수(A3).
