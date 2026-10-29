# Correspondence: hub-config-stale-cache

Spec commit: `70509a59a93e39103565731885e8763b51bbfa49` (수정 전) → 수정 후 줄 번호는 F1 패치 적용 상태 기준. 수정 전 줄은 괄호에.

## Map

| Model element | Code | Kind | Abstraction | Notes |
|---|---|---|---|---|
| `file` | `<Vault>/myelin.yaml` `domains.extra` — `packages/myelin-core/src/myelin_core/config.py:167-186 load_config()`, `:200-203 save_config()` | variable | Domain ID 집합 ⊆ `Doms`; 다른 필드 생략(A1) | 디스크의 진실 |
| `cache` | `packages/myelin-hub/api/src/myelin_hub_api/service.py:118-123 HubService.vault` (`Vault.config`), 채워지는 곳 `:131-154 reload()` | variable | Domain 집합 | 수정 전엔 `open()`(126-130)·`save_settings`(699)·`_onboard`(902)에서만 갱신 |
| `form`, `formBase`, `formLoaded` | `packages/myelin-hub/web/src/pages/Settings.tsx:17 const current = await (await fetch("/api/settings")).json()` | variable | 폼 = GET 응답의 domains; `formBase` = 그 시점 파일(추상 ETag) | `IfMatch` 토글이 비교하는 값 |
| `accepted`, `badReject`, `badAccept`, `lost` | — (history/witness 변수) | variable | 속성 판정용 | 코드에 대응 없음 |
| `View` | `service.py:189-192 _v()` → `:165-177 _reload_if_changed()` (fix ON) / 수정 전 `service.py:166-169 _v()` 는 `self.vault` 를 그대로 반환 (fix OFF) | definition | 바이트 비교+재파싱을 즉시 일치로 봄(A3) | **F1 fix toggle `ReloadOnRequest`** |
| `CliAddDomain(d)` | `packages/myelin-core/src/myelin_core/scaffold.py:277-360 add_domain()`: `:307-316` extra 추가, `:352` `(vault.root / CONFIG_FILE).write_text(dump_config(new_cfg))`; 호출자 `packages/myelin-cli/src/myelin_cli/app.py:362-385` | action | 원자적 쓰기(A2); MOC/템플릿/CLAUDE.md/.obsidian/commit 생략(A6) | 별도 OS 프로세스 |
| `HubRestart` | `service.py:126-130 HubService.open()` → `reload()` | action (env) | 운영자의 재기동 = 오늘까지의 우회책 | 공정성 없음(A7) |
| `HubPromote(d)` | `service.py:534-555 promote()`: `v = self._v()` (538), `if target_domain not in v.config.domains.all_ids: raise HubError(..., 422)` (554-555); 라우트 `app.py:274`. 동일 패턴: `domains()` 419-439, `summary()` 329 | action | 결정 1개 = 1 action; 초안 파일 이동·commit 생략 | P1 witness 갱신 |
| `BrowserGet` | `Settings.tsx:17` → `app.py:239 GET /api/settings` → `service.py:672-674 settings(): v.config.model_dump()` | action | 서버 처리 포함 1 action | `cache' = View` 는 fix ON 일 때 `_v()` 의 재로드를 반영 |
| `BrowserPut` | `Settings.tsx:18-20` `next = {...current, level, mcp, commons}; userPut("/api/settings", next)` → `app.py:298 PUT /api/settings` → `service.py:676-700 save_settings()`: `MyelinConfig.model_validate(data)` (680), `myelin.yaml` 쓰기 (686), `_commit` (698), `self.reload()` (699) | action | commit·CLAUDE.md 재렌더 생략; `IfMatch` 분기(412)는 **코드에 없음** — 제안 F2 | P2 witness `lost' = lost ∪ (file \ form)` |
| `P1_NoStaleDecision` | `tla/Properties.tla` ← `PHASE_STATE.md:136`, `docs/adr/0009-hub-write-policy.md:10`, `README.md:17` | invariant | 프로토콜 수준(동결) | |
| `P2_NoLostDomain` | `tla/Properties.tla` ← `docs/adr/0004-myelin-yaml-schema.md:9`, `README.md:69`, `CLAUDE.md`, `Settings.tsx:17-19` | invariant | 프로토콜 수준(동결) | |
| `ReloadOnRequest` | **F1 패치** `service.py:159-192` (`_read_config_bytes`, `_reload_if_changed`, `ready`, `_v`), `:133` reload 가 바이트 기록, `:748`·`:831` `self.vault` 직접 참조를 `self.ready`/`_v()` 로 | constant (fix) | | `evidence/patches/F1-hub-config-reload-on-change.diff` |
| `IfMatch` | 없음 (제안: `GET /api/settings` 에 `version`/ETag, `PUT` 에 `If-Match`/`base_version` → 불일치 412, `Settings.tsx save()` 재조회) | constant (proposed fix) | | finding F2 |

## Assumptions

- A1 설정 파일의 다른 필드는 Domain 과 같은 운명이지만 모델 밖. Settings 페이지가 쓰는 level/mcp/commons 는 의도된 덮어쓰기.
- A2 CLI 쓰기 원자성(실제 truncate+write; 창 안의 읽기는 409 fail-closed 후 회복).
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
