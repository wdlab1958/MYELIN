# MYELIN — Personal Knowledge OS

> **쓸수록 빨라지는 나의 지식 신경망** · *Knowledge that fires faster.*
> Obsidian + Claude 기반 개인 지식 운영체계. 개인의 관심·경험을 재사용 가능한 지식으로 전환한다.

정본 명세: [`docs/spec/MYELIN_Rev2.0.md`](docs/spec/MYELIN_Rev2.0.md) (WDLAB-MYELIN-SPEC Rev 2.0, 2026-10-18) · 원본 [`docs/spec/MYELIN_Rev2.0.docx`](docs/spec/MYELIN_Rev2.0.docx)
상태: **v1.4.0** (2026-11-26) — 정본의 구현 Phase P0~P8 완료 + P9(Desktop 라인 기능 이식) + P10(One Cycle 선결 과제: 형식 검증 수정 반영 · Team 모드 · 고객정보 가드 · 인계 수신). git 태그는 `phase-P0`~`phase-P8`, `v1.0.0` 까지만 있다. 남은 것은 사람 참여 항목과 운영(아래 §11), 출하 점검표는 [`docs/RELEASE_READINESS.md`](docs/RELEASE_READINESS.md).

> **위치** — MYELIN 은 고객에게 파는 상품이 아니다. One Cycle Dev. Framework 에서 생긴 정보 자산을 개발자·운영자가 관리하는 **개인 지식 관리 서비스**다. 고객 식별 정보·고객 코드·자격증명은 기록하지 않는다([지식 관리 지침](docs/guides/knowledge-management-policy.md)).

## 🔬 형식 검증 (Formal Verification) — 현재 상태 (Nov.26, 2026)

| Concern | 결과 |
|---|---|
| `hub-config-stale-cache` | F1·F2·F8 FIXED · **F3 FIXED (2026-11-26)** — CLI `add-domain` 이 건드린 경로만 커밋 · L2 |
| `review-gate-promote-toctou` | F4 FIXED · L2 + **L3 (Lean 4)** |
| `hub-pack-save-atomicity` · `hub-onboard-atomicity` | F5·F6·F7 FIXED · L2 |
| `mcp-config-revocation-stale` | **F1 FIXED — 브랜치에만 있던 수정을 2026-11-26 작업 트리에 반영.** 설정 철회 뒤에도 MCP 서버가 초안을 만들고 confidential 본문을 내보내던 결함 · L2 + **L3 (Lean 4)** |

미수정 CONFIRMED 0건. 2026-11-21 라운드의 의심 후보 C2·C3·C5·C6 은 재현 테스트 후 수정, C4·C7·C8 과 MCP 부수 발견 F2(도구 목록은 기동 시 결정)·F4(호출 안의 수 ms 창)는 **미수정**(기록). 2026-11-26 재실행: `formal/run_all.sh` 31개 설정 모두 기대값, `formal/lean_audit.sh` 2개 프로젝트 clean, 포인터 검사 0 broken. 모델은 유한 경계 안에서만 유효하다(경계 밖·추상화 안의 버그는 배제하지 않는다). 상세 [`formal/README.md`](formal/README.md).

### 첫 라운드 — Oct.29, 2026

WDLAB Unified Proof-Skills Standard v1.0(WDLAB-STD-VERIFY-001, proof-skills 0.1.1 · TLA+/TLC)을 적용했다. 산출물은 [`formal/`](formal/README.md), 보고서는 `~/ai_project/Proof-Skills/MYELIN_ProofSkills_Report_2026-10-29.docx`(사본 [`formal/reports/`](formal/reports/2026-10-29-hub-config-stale-cache.md)).

| 항목 | 내용 |
|---|---|
| Concern | [`hub-config-stale-cache`](formal/hub-config-stale-cache/SCOPE.md) — Hub 가 캐시한 `myelin.yaml` vs CLI `myelin add-domain` vs Settings 저장 (Backlog 항목) |
| Verdict | **F1 FIXED** · F2 CONFIRMED(HITL) · F3 CONFIRMED(기록) — 모델 **BOUNDED-PASS (L2)**, 경계 `Doms={d1,d2}` 72 states/depth 7 · `{d1,d2,d3}` 432/depth 9, 신뢰 기반 TLC 2026.10.28 + 추상화 A1~A8(SCOPE.md). 경계 밖·추상화 안의 버그는 배제하지 않는다 |
| F1 (수정) | Hub 가 기동 시 1회 읽은 `myelin.yaml` 로만 결정해 CLI 가 추가한 Domain 으로의 승격이 422 로 거부되고, Settings 저장이 옛 Domain 목록을 되써서 추가가 사라졌다 → `HubService._reload_if_changed`: 파일 바이트가 바뀌면 요청마다 재로드 (`service.py`, 재현 테스트 `packages/myelin-hub/api/tests/test_config_reload.py`) |
| F2 / F3 (당시 미수정 → 이후 수정) | `PUT /api/settings` 버전 검사 부재 → 2026-11-18 If-Match 로 수정 · CLI `add-domain` 의 `git add -A` 커밋 범위(ADR-0009 §4 위반) → 2026-11-26 수정. 재현 스크립트 `formal/hub-config-stale-cache/repro/` 는 이제 exit 0 |
| 실행 | `TLC_WORKERS=4 formal/run_all.sh` (3-config 게이트) · `.venv/bin/python -m pytest packages/myelin-hub/api/tests/test_config_reload.py -v` |

### W5 CI 회귀 가드 — Nov.16, 2026
[`.github/workflows/formal.yml`](.github/workflows/formal.yml)(`formal-verification`, fail-closed)이 PR·`main` push·nightly 에서 `formal/run_all.sh` 3-config 게이트(MC PASS / MC_bug·MC_partial·MC_sanity FAIL 기대값)와 W6 드리프트 검사(`formal/tools/correspondence_check.py`, 모델→코드 `file:line` 포인터 0 broken)를 실행한다. 스펙을 약화시키거나 fix 토글 기대값을 바꾸는 변경, 그리고 매핑된 소스가 움직여 대응표가 깨진 PR 을 막는다 — 상세 [`formal/README.md`](formal/README.md#ci-w5w6--2026-11-16).

---

## 1. 무엇인가

| 원칙 (정본 §3) | 구현 |
|---|---|
| **Fail-closed** | AI 쓰기는 `00_Inbox/ai-drafts/` 등 Level 별 허용 경로만. Claude Code PreToolUse Hook 이 Write/Edit/NotebookEdit **와 Bash** 를 차단(exit 2). 판단 불가 = 차단 |
| **Deterministic Auditability** | 모든 변경은 git commit. AI 커밋 `[myelin:<skill>]`, frontmatter `origin` 추적 |
| **Phase-gated Autonomy** | `myelin.yaml level` 0~3 에 따라 Skill·허용 경로 누적 개방 |
| **HITL Oversight** | verified 승격·패치 적용·Commons 공개는 Hub 에서 **사람의 클릭**으로만, commit 으로 기록 |
| **Thin Additive Routing Shell** | Domain 은 코드가 아니라 **Pack(YAML)**. Domain 추가에 코드 변경 없음 |
| **Personal Ownership** | Vault 는 개인 소유. 조직은 열람하지 않고 지표는 opt-in 익명 집계만. Commons 기여는 실명으로 남아 인용 집계가 평판이 된다 |
| **Compounding (복리)** | verified 는 시작. 노트별 강도(myelin ×1~3)·재사용 비율·재투입 소요일을 재고, 산출물의 `## 환류 후보` 를 `/distill` 로 되돌리는 환류 경로가 있다(정본 Rev 2.1 부록) |
| **Confidential Routing** | `MYELIN_LLM=local` 세션만 `40_IP/**`·confidential 을 읽고 쓴다. 외부 세션은 Guard(Read/Grep/Glob/Write)와 MCP 가 차단. Vault pre-commit 훅이 Claude Code 밖의 커밋도 검사 |
| **Low-friction Onboarding** | 설치→첫 verified 노트 15분 이내(자동 측정 포함) |

## 2. 구성 요소 (정본 §2.3 제품군)

| 제품 | 경로 | 내용 |
|---|---|---|
| **MYELIN Vault** | Vault 표준 §6 | Frontmatter v2(id/type/domain/status/origin/confidence/classification/share/source/created/reviewed/tags), 폴더 표준(`00_Inbox 10_Domains 20_Projects 30_Resources 40_IP 50_Journal 80_Outputs 90_System 99_Archive _patches .myelin`) |
| **MYELIN Packs** | [`packs/`](packs/) | `myelin.core`(note type 9종 템플릿 + 공통 용어), `brian.physical-ai`(Reference, D1~D4, 인터뷰 질문 16), `a3.security-consulting`(용어 37·템플릿 9·인터뷰 27), `a3.incident-response`(용어 40·템플릿 10·인터뷰 26)(Org, v1.0 구조 — 용어는 A3 컨설턴트 확인 전), `wdlab.onecycle`(One Cycle 수신 Domain `LLMOPS`·`SSC`·`ARGUS`). Pack 스키마·로더·의존성 해석·검증 |
| **MYELIN CLI** | [`packages/myelin-cli`](packages/myelin-cli) | `myelin init`(3+1 마법사) · `add-domain` · `doctor`(규칙 8종) · `stats`(§11.1) · `skills` · `interview-bank` · `publish` · `pack-propose` · `metrics` · `commons` |
| **MYELIN for Claude Code** | [`plugin/`](plugin/) | Skill 7종 `/myelin:ingest distill interview review link compose ip-scan`, Fail-closed Guard(`guard_write.py`, `guard_bash.py`, 표준 라이브러리만), 로컬 marketplace |
| **MYELIN MCP** | [`packages/myelin-mcp`](packages/myelin-mcp) | stdio 서버, 읽기 전용 기본(`search_notes get_note query_frontmatter list_domains vault_stats`), opt-in `write_draft`, 기밀 비노출 기본, SQLite FTS5 색인 |
| **MYELIN Hub** | [`packages/myelin-hub`](packages/myelin-hub) | FastAPI + React 18/Vite/Tailwind. Dashboard · My Domains · Inbox/Review Gate · Domain Packs · Settings · 온보딩 마법사 · 우측 하단 **도움말 챗봇**(로컬 Ollama, 읽기 전용). 모든 쓰기는 클릭 헤더 + git commit |
| **MYELIN Emboss** | [`design/`](design/), [`theme/`](theme/) | `tokens.json` 단일 원천 → `emboss.css`·Tailwind preset·Obsidian theme 생성, 대비 4.5:1 자동 검사, 색 하드코딩 lint, 컴포넌트 갤러리 |
| **MYELIN Commons** | `myelin_core.commons` | 팀 공유 저장소 구조·Pack Registry·공개 하드 게이트·비식별 스캔·확인 단계·`publish/<id>` 브랜치/PR·Pack 제안·익명 지표(opt-in) |

### 아키텍처 (정본 §4.1)
```
L0 Definition   packs/*.yaml · Frontmatter v2 · docs/spec/schema/*.json
L1 Capture      Obsidian · Web Clipper · /ingest
L2 Vault (SoR)  <Vault>/ (Markdown + YAML + git)
L3 Engine       myelin-core (schema·parser·packs·doctor·stats·index·render·scaffold·patches·commons·metrics)
                myelin-cli · plugin (Guard/Skills) · myelin-mcp
L4 Experience   myelin-hub (api + web) · Obsidian Emboss theme
L5 Commons      <commons repo>/ (registry · notes · proposals · metrics)
```
데이터 흐름(§4.2): Capture → `00_Inbox` → `/ingest`·`/distill` → `ai-drafts`(origin claude, draft) → **Hub Review Gate(사람) Promote → commit** → `10_Domains/<D>/`(verified) → `/link` 패치 제안(`_patches/`, 사람 승인) → `/compose` → `80_Outputs` → **Commons 제안(비식별 검사 + 확인) → PR**.

## 3. 빠른 시작 — 다운로드 → 설치 → 초기화(온보딩)

신규 사용자는 **빈 폴더**에서 시작한다. 온보딩 마법사에서 이름과 Primary Domain 을 정하면 Vault 가 생기고 첫 AI 초안 "MYELIN 시작하기" 가 Review Gate 에 올라온다. 다른 사람의 Vault·관심사를 복사하지 않는다 — Reference Pack(brian.physical-ai)은 참고용 선택지일 뿐이고, 마법사에서 **내 Domain 을 직접 정의**할 수 있다(개인 Pack `me.my-domains` 로 저장).

```bash
git clone git@github.com:wdlab1958/MYELIN.git myelin && cd myelin
scripts/install.sh --vault ~/Vaults/me --claude   # python/uv 자가 검사 → uv sync → Hub 빌드 → 런처 → Obsidian 테마 (+ --claude: plugin/MCP 등록, opt-in)
myelin-hub --vault ~/Vaults/me               # http://127.0.0.1:8787 → 온보딩 마법사(3+1 Domain) → 첫 ai-draft 승격
```
Obsidian 이 없으면 `scripts/install_obsidian.sh --vault ~/Vaults/me` (Debian/Ubuntu: 공식 .deb 설치 + Emboss 테마 선선택 + Vault 열기).
CLI 로만: `myelin init --vault ~/Vaults/me` → Obsidian 에서 열기 → Vault 폴더에서 `claude` → `/myelin:ingest <자료>` → `/myelin:distill` → Hub 에서 Promote.

요구 사항: Python 3.12, [uv](https://docs.astral.sh/uv/), git, Node 22 (Hub 웹), [Claude Code](https://claude.com/claude-code) 2.1.295+ (plugin/MCP — hook `onFailure: block` 은 2.1.295 부터), Google Chrome (e2e 선택).

## 4. 명령 요약

| 명령 | 설명 |
|---|---|
| `myelin init [--vault] [-y --name --primary --research --growth --pack --level]` | Vault 생성. 기존 파일 있으면 중단(덮어쓰기 금지). `.claude/settings.json`·CLAUDE.md·MOC·템플릿·taxonomy 생성 |
| `myelin add-domain <ID> [--pack]` | Pack 의 Domain 을 `domains.extra` 로 추가. 기존 노트 불변, personal 블록 보존 |
| `myelin doctor [--json --strict]` | 규칙 8종: schema · fail-closed · orphan · confidential-share · broken-link · duplicate-id · domain · temporal. 오류 시 exit 1 |
| `myelin stats [--today]` | §11.1 지표(Inbox 체류·주간 verified·AI 승격률·고아·cross-domain·산출물) |
| `myelin skills` · `myelin interview-bank [-d D]` | Level 별 Skill 개방 표 · Pack 질문 은행 |
| `myelin publish <note> [--check -y --push --pr]` | Commons 제안: 하드 게이트 → 비식별 스캔 → 확인 → `publish/<id>` 브랜치 커밋 |
| `myelin pack-propose <dir>` · `myelin commons init\|add-pack\|registry` | Org Pack 제안 · Commons 골격/Registry |
| `myelin metrics show\|send\|aggregate` | 익명 지표(opt-in) |
| `myelin guard scan [경로…] [--vault --json --strict]` | 고객정보 가드: 자격증명·주민번호·고객명(BLOCK, exit 1) · 긴 코드 블록·IP·내부 URL(FLAG). 적중 내용은 가려서 출력 (ADR-0017) |
| `myelin onecycle import-findings <file.json> [--vault --domain --dry-run --json]` | `onecycle.findings/v1` 의 finding 하나당 초안 하나를 `00_Inbox/ai-drafts` 에. 덮어쓰기 없음·멱등·가드 적용. 잘못된 파일 exit 2, 가드 차단 exit 1 (ADR-0018) |
| `myelin-mcp --vault <v>` · `myelin-hub --vault <v> [--port]` | MCP 서버 · Hub (기본 localhost 전용·무인증) |
| `myelin-hub --host <addr> --auth-file <yaml> --tls-cert/--tls-key \| --behind-tls-proxy` · `myelin-hub --new-token <name> [--role]` | Team 모드(선택): 토큰 인증·역할·기밀 미제공·접근 기록. 조건이 하나라도 빠지면 비-loopback 바인딩 거부 (ADR-0016) |

Claude Code: `/myelin:ingest` `/myelin:distill` `/myelin:interview` (Level ≥ 1) · `/myelin:review` (1) · `/myelin:link` `/myelin:compose` (2) · `/myelin:ip-scan` (3, 사용자 호출 전용).

## 5. 저장소 구조 (정본 §10.1)

```
├── CLAUDE.md · PHASE_STATE.md · Makefile · CHANGELOG.md
├── docs/{spec, phases, adr, reports, guides, security}/
├── packs/{myelin.core, brian.physical-ai, a3.security-consulting, a3.incident-response}/
├── packages/{myelin-core, myelin-cli, myelin-mcp, myelin-hub/{api, web}}/
├── plugin/ (.claude-plugin/plugin.json · skills/ · hooks/) · .claude-plugin/marketplace.json
├── design/{tokens.json, tokens.schema.json, dist/, gallery/, components.md}
├── theme/obsidian-myelin-emboss/
├── scripts/ (gate · emboss · install · pilot · time_to_first_verified · 생성기들)
└── tests/{fixtures/{vaults, packs, golden, skill-outputs}, plugin/, e2e}
```

## 6. 개발

```bash
make sync          # uv sync (Makefile 이 /usr/bin/python3.12 를 UV_PYTHON 으로 고정 — 혼합 pyenv 회피)
make check         # ruff + mypy --strict + pytest (1,070+ tests)
make gate P=8      # Phase gate (각 Phase 의 통과 기준을 스크립트로 고정, 미구현 Phase 는 fail-closed)
make web · make e2e · make hub VAULT=…   # Hub 빌드 · Playwright e2e(스크린샷) · Hub 실행
make emboss · make a11y · make emboss-lint · make gallery   # 디자인 토큰 생성·대비·하드코딩 lint·갤러리 스크린샷
make perf · make ttfv · make phases · make schemas · make fixtures · make golden · make packs
```
작업 규칙은 [`CLAUDE.md`](CLAUDE.md), 세션 간 상태는 [`PHASE_STATE.md`](PHASE_STATE.md), Phase 계획은 [`docs/phases/`](docs/phases/).

## 7. Phase 별 구현 현황

| Phase | 내용 | Gate | 보고서 |
|---|---|---|---|
| P0 Bootstrap | 모노레포·uv workspace·Gate 체계·CI·ADR-0001/0002 | PASS | [P0](docs/reports/P0.md) |
| P1 Core Model & Domain Pack | Frontmatter v2·라운드트립 파서·Pack 스키마/로더·Pack 3종·fixture 35 노트·잘못된 Pack 14종 | PASS (coverage 99%) | [P1](docs/reports/P1.md) |
| P2 CLI Scaffolder | init/add-domain/doctor/stats·렌더러·golden snapshot·시드 위반 100% 검출 | PASS | [P2](docs/reports/P2.md) |
| P3 Plugin + Guard | Skill 7종·Level-gated Guard(Write/Edit + Bash, 137 케이스)·settings.json·`_patches` 형식 | PASS | [P3](docs/reports/P3.md) |
| P4 MCP Server | FTS5 색인(증분)·MCP tools·경로 이탈 차단·기밀 정책·5,000 노트 p95 17ms | PASS | [P4](docs/reports/P4.md) |
| P5 Emboss + Theme | tokens.json·생성 스크립트·대비 4.5:1(13쌍)·하드코딩 lint·갤러리·Obsidian theme | PASS | [P5](docs/reports/P5.md), [갤러리](docs/reports/P5/gallery.png) |
| P6 Hub | FastAPI + React 5화면·온보딩·Promote/Reject/패치 적용 commit·Playwright e2e·클릭 없는 쓰기 0 | PASS | [P6](docs/reports/P6.md), [스크린샷](docs/reports/P6/) |
| P7 Commons & Pilot | Commons 구조·Registry·비식별 스캔·publish/PR·Pack 제안·익명 지표·Org Pack 2종·파일럿 키트 | 자동 PASS · **사람 항목 2개 대기** | [P7](docs/reports/P7.md) |
| P8 Hardening & v1.0 | 위협 모델(High 0)·install.sh·가이드·릴리스 노트·이름 확인·15분 측정 | PASS → **v1.0.0** | [P8](docs/reports/P8.md) |
| P9 Desktop 기능 이식 | patch plan/diff/digest·Hub 미리보기·install `--claude`·Obsidian 선설치/가이드 | tests 417 → **v1.1.0** | [CHANGELOG](CHANGELOG.md) |

## 8. 설계 결정 (ADR)

| ADR | 결정 |
|---|---|
| [0001](docs/adr/0001-tech-stack.md) | 기술 스택 (Python 3.12 · uv workspace · Pydantic v2 · Typer · ruamel · FastAPI · React · SQLite FTS5) |
| [0002](docs/adr/0002-plugin-spec.md) | Claude Code Plugin/Hook 현행 사양 확인 (matcher에 NotebookEdit, onFailure block, exit 2, `Edit(...)` deny 만 유효, Bash hook 보강) |
| [0003](docs/adr/0003-schema-validation-policy.md) | Frontmatter 미지 필드 허용·보존 / Pack 미지 필드 금지 / 모순은 doctor 규칙 |
| [0004](docs/adr/0004-myelin-yaml-schema.md) | myelin.yaml (`domains.extra`, primary 만 필수, mcp/commons 블록) |
| [0005](docs/adr/0005-level-gated-guard.md) | Level 누적 허용 경로, Bash Guard, Skill 비노출 3겹, settings.json 2차 방어 |
| [0006](docs/adr/0006-patches-format.md) | `_patches/*.patch.md` 형식 (append / replace / frontmatter), 적용은 Hub 만 |
| [0007](docs/adr/0007-mcp-policy.md) | MCP 읽기 전용 기본, write_draft 등록 조건, 기밀 소유자 opt-in, 색인·하이브리드 검색 |
| [0008](docs/adr/0008-emboss-contrast-adjustments.md) | 정본 §8.1 세 토큰(muted·lime-ink·cyan-ink) 을 4.5:1 기준으로 조정 |
| [0009](docs/adr/0009-hub-write-policy.md) | Hub 쓰기 = 클릭 헤더 필수, 동작 6종 = commit 6종, welcome 초안, localhost 전용 |
| [0010](docs/adr/0010-commons-policy.md) | Commons 공개 게이트·비식별·확인 단계·브랜치/PR·Pack 진화·익명 지표·온보딩 계측 |
| [0011](docs/adr/0011-confidential-routing-devices.md) | 기밀 라우팅 장치화: `MYELIN_LLM=local` 세션만 `40_IP/**`·confidential 접근, Read/Grep/Glob Guard, MCP 강제, Vault pre-commit 훅 |
| [0012](docs/adr/0012-myelin-strength-and-reuse-metrics.md) | 미엘린 강도 0~3, 재사용 KPI 3종, Commons 인용 집계·top_contributors, Hub push/PR |
| [0013](docs/adr/0013-hub-assistant.md) | Hub 도움말 챗봇 — 읽기 전용, 로컬 Ollama 전용(비-loopback 이면 기밀 제외), 지식 기반 폴백, 입력 가드 |
| [0014](docs/adr/0014-public-repo-vault-isolation.md) | 공개 저장소와 개인 Vault·로컬 Commons 분리 — Vault/Commons 는 push 금지 |
| [0015](docs/adr/0015-hub-add-domain.md) | Hub 에서 Domain 추가 `POST /api/domains` |
| [0016](docs/adr/0016-hub-team-mode.md) | Hub Team 모드(선택) — 토큰 인증, read/write 역할과 경로 허용 목록, 기밀 미제공, 접근 기록, 비-loopback 바인딩 조건 |
| [0017](docs/adr/0017-customer-information-guard.md) | 고객정보 가드 — 쓰기 전 결정적 검사(block/flag), 호출 경로, 고객명 목록 위치, fail-closed |
| [0018](docs/adr/0018-onecycle-handoff.md) | One Cycle 인계 수신 — `source_platform` 초안, Pack `wdlab.onecycle`, 라우팅 규칙, findings 가져오기 |

## 9. 문서

- 설치·운영: [**INSTALL**(사내·망분리 설치, 백업·복구, 업그레이드)](docs/INSTALL.md) · [출하 점검표](docs/RELEASE_READINESS.md) · [지식 관리 지침](docs/guides/knowledge-management-policy.md) · [One Cycle 인계 절차](docs/onecycle/HANDOFF.md) · [파일럿 키트](docs/guides/pilot-kit.md)
- 가이드: [사용자](docs/guides/user-guide.md) · [관리자](docs/guides/admin-guide.md) · [Obsidian 연동](docs/guides/obsidian-setup.md) · [MCP 설정](docs/guides/mcp-setup.md) · [파일럿](docs/guides/pilot-guide.md) · [60분 워크숍](docs/guides/workshop-60min.md) · [Day 1 체크리스트](docs/guides/day1-checklist.md)
- 스펙: [정본](docs/spec/MYELIN_Rev2.0.md) · [JSON Schema](docs/spec/schema/) · [Commons 구조](docs/spec/commons.md) · [컴포넌트 스펙](design/components.md)
- 보안: [위협 모델(STRIDE)](docs/security/threat-model.md) · [이름 확인(상표·도메인·GitHub)](docs/reports/P8/naming-check.md)
- 릴리스: [RELEASE_NOTES](docs/RELEASE_NOTES.md) · [CHANGELOG](CHANGELOG.md)

## 10. 검증 요약 (v1.4.0, 2026-11-26 측정)

| 항목 | 값 | 측정 방법 |
|---|---|---|
| 테스트 | **1,418 passed · 1 skipped**(성능 벤치는 `MYELIN_PERF=1` 일 때만) | `.venv/bin/python -m pytest -q` (약 2분 20초). 이번 변경 전 1,295 |
| 정적 검사 | ruff · ruff format · mypy(strict, 67 파일) 통과 | `ruff check` · `ruff format --check .` · `mypy` |
| 형식 검증 | TLC 3-config 게이트 31개 설정 기대값 · Lean 2개 프로젝트 clean · 포인터 0 broken | `formal/run_all.sh` · `formal/lean_audit.sh` · `correspondence_check.py` |
| Pack | 5개 검증(`myelin.core`·`brian.physical-ai`·`a3.*` 2·`wdlab.onecycle`) | `scripts/validate_packs.py` + 임시 Vault 에 `myelin add-domain` |
| 이번에 다시 재지 않은 것 | Playwright e2e · 5,000 노트 성능 벤치 · 접근성(대비) 검사 · Phase Gate(`make gate`) | 이전 값은 `docs/reports/P4·P5·P6·P8.md` |

## 11. 알려진 제약 · 남은 일

- 다크 모드 미지원(§8.3 가드레일 5) · Team 모드는 선택 기능이며 사용자 관리 화면·토큰 만료·SSO 가 없고 침투 시험을 하지 않았다(ADR-0016) · 고객정보 가드는 패턴 검사라 목록에 없는 고객명·형식 없는 비밀값은 잡지 못한다(ADR-0017, 사람의 검토가 1차 통제) · Hub 웹 UI 의 Team 토큰 입력·가드 확인 창은 타입 검사만 했고 e2e 로 확인하지 않았다 · 망분리 설치 절차는 실제 망분리 PC 에서 검증하지 않았다 · A3 Pack 2종의 용어는 A3 컨설턴트 확인 전 · 다섯 플랫폼의 실제 내보내기를 이어 돌린 통합 시험은 이 저장소에서 하지 않았다 · Bash Guard 는 Vault 밖 스크립트·패키지 설치·네트워크 송신은 검사하지 않음(settings.json ask + 커밋 이력 사후 감사) · 비식별 스캔은 휴리스틱(챔피언 리뷰 2중) · MCP 기밀 노출은 소유자 opt-in.
- **사람 참여 항목**: P7 파일럿 5명 온보딩·피드백 기록(`scripts/pilot.py`) → `make gate P=7` → `phase-P7` 태그 · KIPRIS 국내 상표 직접 조회 결과 기입 · Commons 챔피언 지정 · 정본 §9.2 Rollout Wave 1·2.
- 브랜드명 MYELIN 은 사내용 가칭(미국 동일 명칭 소프트웨어 상표 선출원 심사 중, 주요 도메인 점유). 대외 공개 시 결합형 `MYELIN KOS` 검토.

## 12. 라이선스

Apache License 2.0 — [`LICENSE`](LICENSE) · [`NOTICE`](NOTICE) (Copyright 2026 Brian (이원대), WDLAB). 상업적 이용이 가능한 공개 라이선스이며 다시 라이선스하지 않았다. 직접 의존성과 외부 도구의 라이선스는 [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md)(직접 의존성 24개 중 copyleft·비상업 조건 0, 미확인 1). 이 문서들은 **법무 검토 전**이다.

---
WDLAB · A3 Security · AI·ML·AX Research Division · 작성 Brian (Research Director, A3-AI WG) · 구현 Claude Code
