# Changelog

## v1.4.0 — 2026-11-26 (One Cycle 선결 과제 · 보안 기본값 · 인계 수신)
MYELIN 의 위치: 고객에게 파는 상품이 아니라, One Cycle Dev. Framework 에서 생긴 정보 자산을 개발자·운영자가 관리하는 개인 지식 관리 서비스. 버전 표기를 하나로 맞췄다(이전: CHANGELOG v1.3.2 / README v1.1.0 / 패키지 0.1.0a0).
- **fix(mcp, formal F1)**: 실행 중인 MCP 서버가 `myelin.yaml` 을 기동 시 한 번만 읽어, Hub Settings 에서 `mcp.write_draft`·`level`·`mcp.expose_confidential` 을 철회한 뒤에도 초안을 만들고 confidential 본문을 내보냈다 → 도구 호출마다 파일 바이트를 비교해 다시 읽는다. 읽을 수 없거나 잘못된 설정이면 호출을 거부한다(옛 권한 유지 안 함). 브랜치 `wdproof/20261121-115639-myelin` 에만 있던 수정·회귀 테스트·TLA+ 모델·Lean 증명을 반영(`formal/mcp-config-revocation-stale/`)
- **fix(cli, formal F3)**: `myelin add-domain`·`myelin obsidian setup` 이 `git add -A` 로 작업 트리 전체를 커밋하던 것 → 자기가 건드린 경로만 커밋(`git commit --only`). 미추적·수정 중·이미 스테이지된 사용자 파일은 그대로 남는다
- **fix(hub/core, formal 후보 C2·C3·C5·C6)**: Hub Domain 추가가 그 사이 CLI 가 추가한 Domain 을 지우던 lost update(409 후 재시도) · Commons 게시 직렬화 · 승격/기각이 그 사이 생긴 같은 이름의 노트를 덮어쓰던 창(배타 생성) · 색인이 mtime 을 되돌린 같은 크기 재작성을 놓치던 것(ctime 반영)
- **feat(hub): Team 모드(선택, ADR-0016)** — `--auth-file`: Bearer 토큰(서버에는 SHA-256 만, 상수 시간 비교), `read`/`write` 역할과 경로 허용 목록(소유자 작업은 채널에 없음), **confidential·`40_IP/**` 는 Team 채널로 나가지 않음**(없는 노트와 같은 404), 접근 기록 `<Vault>/.myelin/hub-access.log`, 인증 파일 변경(토큰 폐기)은 재시작 없이 반영, 실패 제한(429). 비-loopback 바인딩은 인증 + `allowed_hosts` + TLS(또는 `--behind-tls-proxy`)가 모두 있어야 허용. CORS 헤더 없음. `myelin-hub --new-token`. **Personal(loopback) 모드는 그대로**
- **feat(core): 고객정보 가드(ADR-0017)** — `myelin_core.infoguard`: 자격증명·주민번호·고객명 목록 = 차단, 긴 코드 블록·IP·내부 URL = 사람 확인. Hub 승격·patch 적용, MCP `write_draft`, findings 가져오기, Commons 공개, pre-commit(`doctor --staged`)이 호출한다. `myelin guard scan`. 정책 `90_System/infoguard.yaml`, 고객명 목록 `.myelin/customer-names.txt`(git 제외). 지침 `docs/guides/knowledge-management-policy.md`
- **feat(onecycle): 인계 수신(ADR-0018)** — `source_platform: llmops|ssc|argus|proof-skills` 초안은 보통의 AI 초안으로 Review Gate 를 지난다(승격 뒤에도 필드 보존). Pack `wdlab.onecycle`(Domain `LLMOPS`·`SSC`·`ARGUS`)과 Domain 없는 초안의 라우팅 규칙. `myelin onecycle import-findings <file.json>` — `onecycle.findings/v1` 의 finding 하나당 초안 하나, 덮어쓰기 없음·멱등·가드 적용·잘못된 파일 거부. 스키마·표본 `docs/onecycle/`, 절차 `docs/onecycle/HANDOFF.md`
- **packs**: `a3.security-consulting`(용어 37 · 템플릿 9 · 인터뷰 27)·`a3.incident-response`(용어 40 · 템플릿 10 · 인터뷰 26)를 골격에서 v1.0 구조로 — ISO/IEC 27001:2022 Annex A 주제, PTES 단계, NIST SP 800-61 단계, MITRE ATT&CK 전술 이름 등 공개 표준 기반의 일반 내용. **용어는 A3 컨설턴트 확인 전**
- **chore**: 버전 단일 원천 `myelin_core/_version.py` + `scripts/sync_version.py [--check]`(pyproject 5 · uv.lock · web package · README), 제품 표시 이름 상수 `myelin_core.product.PRODUCT_NAME`(`MYELIN_PRODUCT_NAME` 으로 변경 가능 — 식별자는 그대로)
- **docs**: `docs/INSTALL.md`(사내·망분리 설치, 백업·복구, 업그레이드) · `docs/RELEASE_READINESS.md` · `THIRD_PARTY_LICENSES.md` · `docs/guides/pilot-kit.md` · ADR-0016~0018 · 위협 모델 T24~T26
- **동작 변화(재시작 후)**: 자격증명·등록 고객명이 든 초안은 승격·커밋이 거부된다 · 긴 코드 블록/IP 가 든 초안은 승격 때 확인 1회 · `add-domain` 커밋 범위 축소 · Vault 포맷 변경 없음(마이그레이션 불필요)
- tests: 전체 **1,418 passed · 1 skipped**(이전 1,295) — Team 모드 39 · 고객정보 가드 27 · One Cycle(core) 28 · Hub 가드/인계 10 · formal 후보 4 · MCP 철회/가드 5 · CLI 5 · 버전 3 외. `formal/run_all.sh` 31개 설정 기대값 · Lean 감사 2개 프로젝트 clean · ruff · mypy(strict) 통과. Playwright e2e 와 `make gate` 는 다시 돌리지 않았다

## v1.3.2 — 2026-11-21 (Hub 에서 Domain 추가)
- hub: **Domain Packs 카드의 `+ Domain 추가 · <ID>` 버튼** — Pack 에 선언됐지만 Vault 에 없는 Domain 을 클릭 한 번으로 추가(ADR-0015). `POST /api/domains {id, pack?}`(클릭 헤더, 1 commit `[myelin:add-domain] <ID>`, 건드린 경로만 스테이징) — CLI `myelin add-domain` 과 같은 core 경로(MOC · 템플릿 · taxonomy · CLAUDE.md · myelin.yaml · Obsidian 색 그룹). 선언 없음 404 · 이미 설정됨/MOC 존재/모호한 Pack 409 · 잘못된 ID 422, 실패 시 전부 롤백. `GET /api/packs` 의 `domains[].configured`. Pack 저장 뒤 안내 문구가 다음 단계(카드의 버튼)를 가리킨다
- 도우미: `assistant_kb.md` 의 Domain 추가 절차를 실제 화면(① 개인 Pack 저장 → ② `+ Domain 추가`)으로 정정 — 이전에는 "Domain Packs 화면에서 한다" 뿐이라 로컬 LLM 이 없는 'Add Domain'·'Create' 버튼을 지어냈다
- tests: Hub API 3건(1 commit·무관 파일 미포함·재시작 없이 반영 / 거부 시 무변경 / commit 실패 롤백) · 클릭 헤더 감사 · e2e "Packs: + Domain 추가" · 위협 모델 T23

## v1.3.1 — 2026-10-27 (Obsidian Graph View 연동)
- core: `myelin_core.obsidian` — Vault `.obsidian/` 에 **Graph View 설정**을 쓴다: `core-plugins.json`(graph·backlink·outgoing-link·tag-pane·properties 켜기, daily-notes·sync·publish 끄기), `graph.json`(**Domain 폴더마다 Emboss accent 색 그룹** — `design/tokens.json` 단일 원천, + Inbox/40_IP/Archive), `app.json`(새 노트 → 00_Inbox, `[[stem]]` 링크). `myelin init` 이 함께 만들고 `add-domain` 이 새 Domain 의 색 그룹을 보탠다. 있는 파일은 덮어쓰지 않고 병합, 읽을 수 없는 JSON 이면 아무것도 쓰지 않는다(fail-closed)
- cli: `myelin obsidian setup [--open]` · `myelin obsidian status` — 기존 Vault 적용 + `obsidian://open?path=` 로 Vault 를 열어 Obsidian 에 등록
- hub: `GET /api/obsidian`(Graph View on/색 그룹/테마/Obsidian 등록 여부/열기 URI) · `POST /api/obsidian/setup`(클릭 헤더, 1 commit `[myelin:settings] obsidian graph view`). Dashboard **Obsidian Graph View** 카드 — 상태 칩, "Obsidian 에서 Vault 열기(Ctrl+G)" (Advanced URI 플러그인이 있으면 Graph View 직접 열기), "Graph View 설정 쓰기"
- install: `scripts/install.sh --vault` 가 테마 복사 뒤 `myelin obsidian setup` 을 실행 · 가이드 `obsidian-setup.md` 6절 · 도우미 지식
- tests: `test_obsidian.py` 8건(토큰 → 색, 병합·보존, fail-closed, 상태·URI·등록, init/add-domain 동기화) · Hub API 1건 · 골든 scaffold 에 `.obsidian/{core-plugins,graph,app}.json` 추가 — 1,283 passed

## v1.3.0 — 2026-10-19 (Hub 도움말 챗봇)
- hub: 우측 하단 말풍선 → 모달 **도움말 챗봇**(ADR-0013). `GET /api/assistant/status`, `POST /api/assistant/chat`. 내장 지식 `assistant_kb.md`(17절) + Vault FTS 발췌(근거 노트를 Obsidian 링크로) + Vault 상태(Level·Domain·KPI 이탈·검토 대기)를 로컬 Ollama(`MYELIN_ASSISTANT_URL`·`MYELIN_ASSISTANT_MODEL`, 기본 exaone3.5 → qwen2.5 …)에 주입. 읽기 전용(클릭 헤더 불필요, Vault 불변), 엔드포인트가 loopback 이 아니면 confidential·`40_IP/**` 제외(ADR-0011 기준), Ollama 없으면 **지식 기반 모드**로 200 응답, 인젝션·비밀값 요청 거부, 한자 드리프트 제거, 한글 IME 중 Enter/ESC 무시. Review 토스트는 말풍선 위로
- tests: `test_assistant.py` 23건 · e2e "도움말 챗봇" 시나리오(12번째) — kb 모드 고정 · 위협 모델 T22

## v1.2.0 — 2026-10-18 (설계 철학 갭 보완 · 정본 Rev 2.1 부록)
설계 철학 세 의도와 구현의 갭(`docs/reports/QA-2026-10-18.md` §5)을 장치로 닫았다. 요구사항은 `docs/spec/MYELIN_Rev2.1-addendum.md`, 결정은 ADR-0011·0012.
- 복리(의도 1): 노트별 **미엘린 강도 0~3**(피인용·산출물 재료·Commons 인용), KPI `reuse_ratio`·`reuse_lag_days`·`compose_sources_avg` 와 목표 판정, Dashboard "Myelination" 분포·재사용 비율, 노트 표의 `myelin ×N` 텍스트 라벨, `myelin stats` 출력 확장
- 환류(의도 1): `/compose` 산출물의 `## 환류 후보` 절 → `/distill <산출물>` 이 lesson/evergreen/adr 초안으로 되돌림(`tags: [refeed]`), `/review` 가 "환류 대기" 와 재사용 지표 이탈을 보고
- 승격 품질(의도 2): Review Gate 의 Promote 는 "내용 읽기" 로 본문을 연 뒤에만 활성(읽음 확인 장치)
- 기밀 라우팅 장치화(의도 2·3, ADR-0011): `MYELIN_LLM=local` 세션만 `40_IP/**`·confidential 접근. 새 `guard_read.py`(Read/Grep/Glob) + guard_write/guard_bash 의 EXTERNAL 40_IP 쓰기 차단(Level 3 포함) + Bash `grep/find/git show` 읽기 채널 판정 + `git commit --no-verify` 차단; settings.json `Read(./40_IP/**)` deny; MCP 는 로컬 프로세스가 아니면 `expose_confidential` 무시(경고)
- Claude Code 밖 보호(의도 2): `myelin init` 이 Vault git **pre-commit 훅**(`90_System/hooks/pre-commit` → `myelin doctor --staged`)을 설치, Hub 의 첫 커밋도 동일 설치; `myelin doctor --install-hook`; 규칙 = 스키마·confidential-share·temporal·domain·ai-scope(AI 초안이 쓰기 범위 밖이면 거부, 사람이 옮긴 unverified 는 경고)
- 평판(의도 3, ADR-0012): Commons 인용 집계 — 익명 지표에 `cited_commons_ids`, `aggregate` 의 `reuse` 열, `aggregate_reuse()` 의 노트별 인용·`top_contributors`(author 별 published/cited), `myelin metrics aggregate` 출력; `/api/commons/candidates.cited`, `/api/vault.commons.published_count/cited_total`
- Hub Commons 제안 → **push + PR**(opt-in 체크, `gh`), 실패해도 커밋 보존 + 다음 명령 안내(`next_step`), `commons.remote` 를 clone origin 으로 사용; Review·Settings 에 "두 정체성(Commons 실명 / 지표 익명)" 명시
- 문서: 정본 Rev 2.1 부록, 사용자 가이드·README, 위협모델 T02/T05 갱신 + T20/T21 추가, 골든 스냅샷(settings.json deny, pre-commit 훅)
- 테스트: guard_read 118, CLI 장치 31, MCP 라우팅 12, 재사용 14, e2e 갱신(읽음 확인, PR opt-in, pre-commit 거부 확인) — 전체 1,249

## v1.1.1 — 2026-10-18 (QA: A/B · E2E · Chaos · Gap · Agent)
전수 테스트 캠페인(`docs/reports/QA-2026-10-18.md`)에서 발견한 결함을 수정. 테스트 1,070+ 건.
- guard(plugin 1.0.1): 줄바꿈 구분 명령·`#` 주석·`>&`/`|&` 리다이렉션·`{ }`/`if`/`while` 접두·`nohup/timeout/command` 래퍼·`find -delete/-exec`·`awk > file`·`sed --in-place`·stdin 스크립트(`bash -s`, `python3 -`, `curl | sh`)·Vault 내부 스크립트 실행·`wget/curl -o`·glob 대상·git 은 읽기 전용+add/commit 허용 목록으로 전환; Write/Edit 는 `.md` 만(`_patches/` 는 직속 `*.patch.md`), 숨김 디렉터리·제어문자 경로·`_patches/applied|rejected/` 쓰기 차단; NotebookEdit 양쪽 경로 검사; stderr 닫힘(EPIPE) 시에도 exit 2
- settings.json: `ask` 에 `bash/sh/perl/ruby/curl/wget` 추가(골든 재생성)
- mcp: 공개 노트의 백링크로 `40_IP/`·confidential 노트 **제목**이 새던 문제, 제어문자 제목 `write_draft`, 스레드 동시 호출 직렬화
- core: 깊게 중첩된 YAML(RecursionError)·5 MB 노트(FTS5 snippet 2차 시간)·Vault 밖을 가리키는 symlink·`packs/` 템플릿이 노트로 색인되던 문제·SQLite 커서 경합(락 안에서 행 확정)·패치 이름 길이/제어문자·`_patches/applied` 이력 덮어쓰기
- hub-api: 손상된 `myelin.yaml` 로 Hub 가 뜨지 않던 문제(이제 not-ready + 사유), 온보딩이 기존 Vault 위에 개인 Pack 을 남기던 문제, Promote 더블클릭 경합, 동시 설정 저장(`index.lock`), git 실패 시 부분 상태 롤백, 읽기 전용 Vault·NUL 검색어·긴 경로의 bare 500, Pack 복사 시 사이드카(taxonomy/templates) 동반 복사(`copy_from`)와 Pack 디렉터리 전체 커밋, `/api/vault.commons` 준비 상태, KPI 목표 판정
- hub-web: 제목에 `#`/`?`/`%` 가 있는 초안의 Promote/Reject 404, My Domains 늦은 응답이 선택을 되돌리던 경합, Commons 미설정 시 안내·버튼 비활성, Settings 에 Commons 카드(로컬 clone·원격·연동·익명 지표 opt-in), Settings Skill 표 전폭, Dashboard KPI "목표 이탈" 배지
- cli: `myelin init` 이 git 저장소와 `[myelin:init]` 커밋을 만든다(`--no-git`), `add-domain` 은 `[myelin:add-domain]` 커밋
- tests: e2e 11 시나리오(온보딩 직접 정의 Domain·Sub-MOC·Pack 복사·패치 Apply·Commons·콘솔 오류 0), A/B 변형 계약 9건, chaos 127건, guard 적대 394건, MCP 적대 91건, skills 일관성 24건; CI 에 e2e 단계

## v1.1.0 — 2026-10-18
Desktop 세션 라인(보존 브랜치 `main-desktop-p9-2026-10-18`)에만 있던 기능을 이 라인에 이식(P9).
- patches: `under` 제목 구획 append, `## set` 허용 키 제한, 적용 계획(diff·digest·fail-closed 검사), `_patches/applied|rejected/` 이동
- hub: 패치 목록·미리보기(diff) API, digest 검증 Apply(불일치 409), Review 화면 미리보기
- install: `--claude` opt-in(플러그인/MCP 등록), Obsidian 설치 스크립트(`install_obsidian.sh`), 테마 선설치(`init_vault`)
- obsidian: 노트 제목 상태 링·칩(cssclasses), Obsidian 연동 가이드, 사용자 가이드 v1.0 docx/xlsx/png
- hub-web: favicon, React Router v7 flags

## v1.0.0 — 2026-10-18
첫 릴리스. 정본 Rev 2.0 의 P0(Bootstrap) ~ P8(Hardening) 전 Phase 구현. 상세는 `docs/RELEASE_NOTES.md`, Phase 별 보고서는 `docs/reports/P0.md`~`P8.md`, 설계 결정은 `docs/adr/0001`~`0010`.
