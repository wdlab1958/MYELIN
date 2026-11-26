# G0 — 후보 선정 (MYELIN, 2026-10-29, commit 70509a5)

표준 §11 에 MYELIN 전용 지침은 없다. 가장 가까운 지침은 WDLAB-LLMOps/ARGUS-X(파이프라인·캐시)와 PatentForge-OP(다중 행위자의 동일 파일 편집)이다.
MYELIN 은 Python 모노레포(myelin-core · CLI · MCP · Hub FastAPI)+React Hub 로, 공유 자원은 `<Vault>/` 파일시스템 + git 이고, 동시 행위자는 **CLI 프로세스 · Hub 프로세스(스레드풀) · Obsidian/Claude Code(사용자) · 브라우저** 다.
최신 커밋(70509a5)의 Backlog(`PHASE_STATE.md:136`)가 세 가지 결함을 이미 호소하고 있어 이를 1차 후보로 삼았다.

| 순위 | 후보 (kebab-case) | 위치 | 버그 클래스 | blast × conc. | 결정 |
|---|---|---|---|---|---|
| 1 | **hub-config-stale-cache** — Hub 가 기동 시 읽은 `myelin.yaml` 을 캐시하고, CLI `add-domain` 이 파일을 바꿔도 모든 결정(promote 대상 Domain 검증·Domain 목록·Settings GET/PUT)을 옛 값으로 내린다 | `service.py:158-169 _v()`, `124-150 reload()`, `530-531 promote`, `648-676 settings/save_settings` ↔ `scaffold.py:277-360 add_domain` | stale cache(check-then-act) + **lost update**(GET→PUT 가 옛 Domain 목록을 되써서 CLI 의 추가가 사라짐 → `10_Domains/<D>/_MOC.md` 는 남고 doctor "미등록 domain") | **H × H** (설정 파일 = 단일 원천; CLI·Hub 두 프로세스가 비동기로 공유) | **선택** → F1 FIXED, F2 CONFIRMED |
| 2 | add-domain-commit-scope — CLI `_git_commit_vault` 가 `git add -A` 로 작업 트리 전체를 `[myelin:add-domain]` 커밋에 넣는다 (ADR-0009 §4 "변경된 경로만" 위반). 미완성 사용자 노트가 섞이면 pre-commit 장치가 add-domain 커밋 자체를 거부한다 | `app.py:88-128, 376-385` | 감사 추적 오염 / 커밋 범위 | M × M | **F3 CONFIRMED** (repro 스크립트, 수정 제안만 — 설계 선택: init 은 `-A` 가 의도) |
| 3 | settings-put-no-version — Settings 저장은 `fetch(current)` → `PUT {...current}` 두 요청이라, 그 사이 CLI 가 파일을 바꾸면 되쓰기로 사라진다 | `Settings.tsx:17-20`, `service.py:652-676` | lost update (narrow window) | M × M | 1번 모델에 `IfMatch` 토글로 **통합** → F2 (공개 API 변경 → HITL) |
| 4 | hub-mutation-rollback — `_mutation` 이 스냅샷→본문→실패 시 복원. 본문 중 다른 프로세스가 같은 경로를 썼다면 복원이 그 쓰기를 덮는다 | `service.py:177-211` | lost update (실패 경로) | L × M | 기록만 — 실패 경로+외부 쓰기 동시 발생이 전제 |
| 5 | index-refresh-vs-promote — SQLite 색인(cache-aside) 갱신과 promote 의 move+commit 경합 | `index.py`, `service.py:510-568` | stale cache | M × L | 기록만 — `_write_lock`(RLock)+index `_lock` 으로 직렬화됨 |
| 6 | obsidian-config-merge — `ensure_obsidian_config` 가 `.obsidian/*.json` 을 read-merge-write; Obsidian 앱이 동시에 같은 파일을 쓴다 | `obsidian.py` | lost update | L × M | 기록만 — Obsidian 측 동작 모델 불가(외부) |
| 7 | ingest 파이프라인(dedup/손실/마지막 배치) | `plugin/skills/ingest/SKILL.md` | 데이터흐름 | — | **모델 대상 없음** — `/myelin:ingest` 는 Claude Code Skill(프롬프트)이며 Python 배치 코드가 없다. "일괄 ingest" 는 Backlog 의 기능 요청 |

선택 근거: 1번은 (a) Brian 이 운영 중 실제로 겪어 Backlog 에 적은 결함이고, (b) 두 OS 프로세스가 동기화 없이 하나의 파일을 공유하는 전형적 stale-cache/lost-update 패턴(TLA+ `LostUpdate`+`CacheAside` 혼합)이며, (c) 영향이 설정 파일(단일 원천) 손실과 Review Gate 오거부로 가장 크다. 3번은 같은 자원·같은 모델에서 두 번째 토글로 자연스럽게 함께 검사된다.

---

# G0 — 후보 재선정: MYELIN Hub 전용 라운드 (2026-11-18, commit c29d83f)

범위는 Brian 지시로 **MYELIN Hub** (`packages/myelin-hub/api` + `packages/myelin-hub/web`)만. `service.py`(1,066행)·`app.py`·`assistant.py`·Review/Settings/Packs 페이지를 전부 읽고, 공유 자원(Vault 파일시스템·git·`myelin.yaml`·초안 파일)과 그것을 건드리는 행위자(Hub 스레드풀·브라우저·CLI·Claude Code skill/MCP·Obsidian)의 조합으로 순위를 매겼다.

| 순위 | 후보 (kebab-case) | 위치 | 버그 클래스 | blast × conc. | 결정 |
|---|---|---|---|---|---|
| 1 | **review-gate-promote-toctou** — 사람이 초안 본문을 읽은 뒤 Promote 클릭이 도착하기 전에 초안이 다시 쓰이면, 읽지 않은 글이 verified 가 된다. `apply_patch` 는 digest 로 막는데 `promote` 는 막지 않는다 | `service.py promote()`, `note()`, `Review.tsx` | check-then-act (TOCTOU), HITL 우회 | **H × M** | **선택** → **F4 FIXED**, TLA+ BOUNDED-PASS + Lean PROVEN |
| 2 | **hub-onboard-atomicity** — 온보딩이 중간에 실패하면 개인 Pack 만 지워지고 myelin.yaml·scaffold·.git 이 남는다. 재시도는 409 | `service.py onboard()`, `_onboard()`, `ensure_git()` | 실패 경로의 부분 쓰기 (all-or-nothing 위반) | **H × L** | **선택** → **F7 FIXED**, BOUNDED-PASS |
| 3 | **hub-pack-save-atomicity** — `save_pack` 만 `@_serialised` 가 아니고 `_mutation` 도 쓰지 않는다. 더블 클릭 → 500, 거부된 Pack 이 디스크에 남음, commit 거부 시 쓰인 채로 남음 | `service.py save_pack()` | race (공유 임시 파일) + 실패 경로 | **M × M** | **선택** → **F5·F6 FIXED**, BOUNDED-PASS |
| 4 | hub-config-stale-cache 의 미해결 F2 (Settings GET→PUT 창) | `service.py save_settings()`, `Settings.tsx` | lost update | M × M | 기존 concern 에서 **F2 FIXED** (If-Match) |
| 5 | hub-config-stale-cache 대응표 드리프트 점검(W6) 중 발견 — `summary()` 만 재로드 없이 `self.vault` 를 읽음 | `service.py summary()`, `assistant.py _vault_state()` | stale cache | L × H | 기존 concern 에서 **F8 FIXED** |
| 6 | commons-publish-unserialised — `commons_publish` 도 `@_serialised` 가 아니다(Commons clone 저장소에 commit/push). 더블 클릭 시 clone 의 `index.lock` 충돌 가능 | `service.py commons_publish()` | race | L × L | **기록만** — 반례를 만들지 않았다. 직렬화하면 `git push`(네트워크) 동안 다른 쓰기가 막히는 trade-off 가 있어 설계 판단 필요 |
| 7 | apply-patch-digest-scope — Apply 의 digest 는 patch 파일만 덮는다. 미리보기 뒤에 **대상 노트**가 바뀌면 화면의 diff 와 다른 결과가 적용된다(같은 patch 의미가 새 내용에 적용; fail-closed 규칙은 apply 시점에 다시 검사됨) | `myelin_core/patches.py digest()`, `service.py apply_patch()` | TOCTOU | M × L | **기록만** — 코어(`myelin_core`) 변경이 필요해 Hub 범위 밖 |
| 8 | promote-read-unlink-window — `promote` 가 초안을 읽은 뒤 `unlink` 하기 전(수 ms)에 writer 가 또 쓰면 그 수정은 사라진다. 승격된 글은 읽은 글 그대로(P3 유지) | `service.py promote()` | lost update (좁은 창) | L × L | **기록만** (review-gate SCOPE A2) |
| 9 | reload-drops-index-under-readers — `myelin.yaml` 이 일시적으로 파싱 불가(다른 프로세스의 truncate→write 사이)일 때 `reload()` 가 `_drop_index()` 로 SQLite 연결을 닫는다. 그 순간 다른 스레드가 질의 중이면 409 가 아니라 500 가능 | `service.py reload()`, `_drop_index()` | race (실패 경로) | L × L | **기록만** — 다음 요청에서 회복 |
| 10 | save-settings-cross-process-window — 버전 검사와 파일 쓰기 사이에 CLI 가 쓰는 경우(프로세스 간 잠금 없음) | `service.py save_settings()` | lost update (μs~ms) | L × L | **기록만** (hub-config CORRESPONDENCE A2) |
| 11 | init-vault-partial-write — `init_vault` 가 파일을 쓰다 OSError 로 죽으면 plan 을 돌려주지 못해 Hub 가 되돌릴 수 없다 | `myelin_core/scaffold.py init_vault()` | 부분 쓰기 | L × L | **기록만** — 코어, Hub 범위 밖 |

이전 라운드(2026-10-29)의 후보 4(hub-mutation-rollback)·5(index-refresh-vs-promote)·6(obsidian-config-merge)는 판단 변동 없음(기록만). F3(CLI commit 범위)는 CLI 라 이번 범위 밖 — CONFIRMED 그대로.

선택 근거: 1번은 제품의 핵심 약속("승격은 사람만", ADR-0009)을 직접 깨는 유일한 후보이고, 같은 코드베이스가 `apply_patch` 에서는 이미 digest 로 막고 있어 의도된 속성임이 분명하다. 2번은 사내 확산 대상자의 첫 경험에서 재현되며 복구 방법이 없다(409). 3번은 `_serialised` 의 docstring 이 금지한 바로 그 상황이 한 메서드에만 남아 있었다.

---

# S2 — 위험 후보: MCP 라운드 (MYELIN, 2026-11-21, commit 3690ada, wdproof 0.1.0)

범위: 저장소 전체(myelin-core · CLI · MCP · Hub API)에서 동시성·상태·재시도·데이터 흐름 결함이 숨을 수 있는 곳.
공유 자원은 `<Vault>/` 파일시스템(특히 `myelin.yaml` 단일 원천)·Vault git·Commons clone git 이며, 동시 행위자는
**Hub 프로세스(FastAPI 스레드풀) · CLI 프로세스 · 장수명 MCP 서버 프로세스(Claude Code 세션) · Obsidian/사용자 편집**이다.
이전 라운드(2026-10-29 · 2026-11-18)에서 FIXED 된 F1·F2·F4~F8 의 concern(`hub-config-stale-cache`, `review-gate-promote-toctou`,
`hub-onboard-atomicity`, `hub-pack-save-atomicity`)은 재선정하지 않았다(이전 표는 git 이력 f24742e 의 이 파일).

| id | 후보 | 위치 | 버그 클래스 | blast × conc. | 가장 가까운 패턴 | 결정 |
|---|---|---|---|---|---|---|
| C1 | **mcp-config-revocation-stale** — MCP 서버는 기동 시 읽은 `myelin.yaml` 을 다시 읽지 않는다. Hub Settings 에서 `mcp.write_draft: false`·`level: 0`·`mcp.expose_confidential: false` 로 동의를 철회해도, 떠 있는 MCP 서버는 옛 정책으로 `write_draft` 를 계속 허용하고 confidential/40_IP 본문을 계속 반출한다 | `packages/myelin-mcp/src/myelin_mcp/service.py:59-84` (정책 판정) · `:116-168` (search/get_note 반출) · `:220-292` (write_draft) · `packages/myelin-mcp/src/myelin_mcp/server.py:160-167` (1회 open) | check-then-act (철회된 동의의 stale 판정) | **H × H** | consent-revocation | **선택** |
| C2 | **hub-add-domain-stale-vault** — 새 `HubService.add_domain` 이 `_mutation` 진입 전에 잡은 `v` 를 core `add_domain` 에 넘긴다. 그 사이 CLI `myelin add-domain`(또는 손 편집)이 `myelin.yaml` 을 바꾸면 `_mutation` 은 새 바이트를 스냅샷하지만 core 는 옛 `v.config` 로 파일 전체를 다시 써서 CLI 의 추가가 사라진다(F1 과 같은 lost update, 새 경로) | `packages/myelin-hub/api/src/myelin_hub_api/service.py:926-1014` ↔ `packages/myelin-core/src/myelin_core/scaffold.py:277-360` | lost-update | H × M | lease-fencing (설정 바이트 = fencing 버전) | 후보 (2순위) |
| C3 | **commons-publish-base-branch** — `commons_publish` 는 `@_serialised` 가 아니고 `publish_note` 는 clone 의 HEAD 를 `base` 로 읽은 뒤 `checkout -b publish/<id>` 한다. 동시 두 게시(더블 클릭·두 노트·Hub+CLI)에서 B 가 A 의 `publish/X` 를 base 로 읽으면 Y 의 PR 에 X 의 노트가 섞이고, `finally` 가 clone 을 `publish/X` 에 남겨 이후 게시가 모두 오염된다 | `packages/myelin-core/src/myelin_core/commons.py:319-404` · `packages/myelin-hub/api/src/myelin_hub_api/service.py:1278-1315` | race | M × M | — | 후보 (3순위) |
| C4 | **hub-mutation-rollback-clobber** — `_mutation` 실패 경로가 스냅샷 바이트를 무조건 되쓴다. 본문 실행 중 다른 프로세스(CLI·Obsidian)가 같은 경로(`myelin.yaml`·노트)를 썼다면 복원이 그 쓰기를 덮는다 | `packages/myelin-hub/api/src/myelin_hub_api/service.py:305-339` | lost-update (실패 경로) | M × L | — | 기록만 |
| C5 | **promote-dest-check-then-write** — `promote`/`reject` 가 `dest.exists()` 를 검사한 뒤 `_mutation` 스냅샷과 `write_text` 를 한다. 그 사이 Obsidian 에서 같은 이름의 노트를 만들면 사람 노트가 초안으로 덮인다(open "x" 미사용) | `packages/myelin-hub/api/src/myelin_hub_api/service.py:699-713` | check-then-act | M × L | hitl-approval-gate | 기록만 |
| C6 | **index-refresh-signature** — 색인 갱신이 `(mtime_ns, size)` 서명만 비교한다. 같은 tick·같은 크기 재작성(예: status 값 교체)은 놓쳐 MCP/Hub 검색·필터가 옛 frontmatter(옛 classification 포함)를 돌려준다 | `packages/myelin-core/src/myelin_core/index.py:303-349` | dataflow-loss (stale cache) | M × L | — | 기록만 |
| C7 | **reload-drops-index-under-readers** — `myelin.yaml` 이 일시적으로 파싱 불가일 때 `reload()` 가 `_drop_index()` 로 SQLite 연결을 닫는다. 다른 스레드가 질의 중이면 409 대신 500 | `packages/myelin-hub/api/src/myelin_hub_api/service.py:235-261` | race | L × L | — | 기록만 |
| C8 | **add-domain-rollback-residue** — Hub `add_domain` 실패 롤백이 `.obsidian/` 디렉터리 생성과 core 가 미리 만든 상위 디렉터리를 되돌리지 않는다(빈 디렉터리 잔존, 데이터 손실 없음) | `packages/myelin-hub/api/src/myelin_hub_api/service.py:994-1011` | other | L × L | — | 기록만 |

C1 이 1순위인 이유: C1 은 이 제품의 두 보안 약속 — "MCP 쓰기는 `mcp.write_draft` 와 Level ≥ 1 일 때만"과 "confidential/40_IP 는
소유자가 허락한 로컬 세션에서만 노출"(ADR-0011 §3) — 을 **철회 시점 이후에도** 깨는 유일한 후보이고, 영향이 Vault 밖(외부 LLM 컨텍스트)으로
반출되는 데이터라 되돌릴 수 없다(blast H). 동시성도 가장 높다: MCP 서버는 Claude Code 세션 동안 몇 시간씩 떠 있는 별도 프로세스이고,
Hub Settings 저장은 일상 조작이라 "검사(기동 시 1회 로드) → 철회(Hub 가 myelin.yaml 커밋) → 사용(get_note 본문 반출·write_draft)" 순서가
특별한 타이밍 없이 매번 성립한다(conc. H). `HubService` 는 같은 결함을 F1 에서 바이트 비교 재로드로 이미 고쳤고 이전 라운드 SCOPE 가 MCP 쪽을
후속 concern 으로 명시해 두었으므로 의도된 속성임이 분명하며, consent-revocation 패턴(`Inv_NoReleaseAfterRevoke`: 철회 이후 어떤 요청도
데이터를 읽지 않는다)에 그대로 대응한다. C2 는 같은 lost-update 계열이지만 창이 `discover_packs` 수 ms 로 좁고 데이터는 git 이력에서
복구 가능하며, C3 은 Commons 오염이 사람의 PR 리뷰 단계에서 걸러질 여지가 있어 그 아래에 둔다.

**처리 (2026-11-26)**: C1 = F1 FIXED(작업 트리 반영). C2·C3·C5·C6 은 재현 테스트 후 수정(`formal/README.md` "후보 처리" 표). C4·C7·C8 은 미수정·기록만.
