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
