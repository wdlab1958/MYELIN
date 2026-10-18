# MYELIN — Personal Knowledge OS

> **쓸수록 빨라지는 나의 지식 신경망** · *Knowledge that fires faster.*
> Obsidian + Claude 기반 개인 지식 운영체계. 개인의 관심·경험을 재사용 가능한 지식으로 전환한다.

정본 명세: [`docs/spec/MYELIN_Rev2.0.md`](docs/spec/MYELIN_Rev2.0.md) (WDLAB-MYELIN-SPEC Rev 2.0, 2026-10-18) · 원본 [`docs/spec/MYELIN_Rev2.0.docx`](docs/spec/MYELIN_Rev2.0.docx)
상태: **v1.0.0** — 정본의 구현 Phase P0~P8 완료 (`phase-P0`~`phase-P8`, `v1.0.0` 태그). 남은 것은 사람 참여 항목과 운영(아래 "남은 일").

---

## 1. 무엇인가

| 원칙 (정본 §3) | 구현 |
|---|---|
| **Fail-closed** | AI 쓰기는 `00_Inbox/ai-drafts/` 등 Level 별 허용 경로만. Claude Code PreToolUse Hook 이 Write/Edit/NotebookEdit **와 Bash** 를 차단(exit 2). 판단 불가 = 차단 |
| **Deterministic Auditability** | 모든 변경은 git commit. AI 커밋 `[myelin:<skill>]`, frontmatter `origin` 추적 |
| **Phase-gated Autonomy** | `myelin.yaml level` 0~3 에 따라 Skill·허용 경로 누적 개방 |
| **HITL Oversight** | verified 승격·패치 적용·Commons 공개는 Hub 에서 **사람의 클릭**으로만, commit 으로 기록 |
| **Thin Additive Routing Shell** | Domain 은 코드가 아니라 **Pack(YAML)**. Domain 추가에 코드 변경 없음 |
| **Personal Ownership** | Vault 는 개인 소유. 조직은 열람하지 않고 지표는 opt-in 익명 집계만 |
| **Low-friction Onboarding** | 설치→첫 verified 노트 15분 이내(자동 측정 포함) |

## 2. 구성 요소 (정본 §2.3 제품군)

| 제품 | 경로 | 내용 |
|---|---|---|
| **MYELIN Vault** | Vault 표준 §6 | Frontmatter v2(id/type/domain/status/origin/confidence/classification/share/source/created/reviewed/tags), 폴더 표준(`00_Inbox 10_Domains 20_Projects 30_Resources 40_IP 50_Journal 80_Outputs 90_System 99_Archive _patches .myelin`) |
| **MYELIN Packs** | [`packs/`](packs/) | `myelin.core`(note type 9종 템플릿 + 공통 용어), `brian.physical-ai`(Reference, D1~D4, 인터뷰 질문 16), `a3.security-consulting`, `a3.incident-response`(Org). Pack 스키마·로더·의존성 해석·검증 |
| **MYELIN CLI** | [`packages/myelin-cli`](packages/myelin-cli) | `myelin init`(3+1 마법사) · `add-domain` · `doctor`(규칙 8종) · `stats`(§11.1) · `skills` · `interview-bank` · `publish` · `pack-propose` · `metrics` · `commons` |
| **MYELIN for Claude Code** | [`plugin/`](plugin/) | Skill 7종 `/myelin:ingest distill interview review link compose ip-scan`, Fail-closed Guard(`guard_write.py`, `guard_bash.py`, 표준 라이브러리만), 로컬 marketplace |
| **MYELIN MCP** | [`packages/myelin-mcp`](packages/myelin-mcp) | stdio 서버, 읽기 전용 기본(`search_notes get_note query_frontmatter list_domains vault_stats`), opt-in `write_draft`, 기밀 비노출 기본, SQLite FTS5 색인 |
| **MYELIN Hub** | [`packages/myelin-hub`](packages/myelin-hub) | FastAPI + React 18/Vite/Tailwind. Dashboard · My Domains · Inbox/Review Gate · Domain Packs · Settings · 온보딩 마법사. 모든 쓰기는 클릭 헤더 + git commit |
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

## 3. 빠른 시작

```bash
git clone git@github.com:wdlab1958/MYELIN.git myelin && cd myelin
scripts/install.sh --vault ~/Vaults/me      # python/uv 자가 검사 → uv sync → Hub 빌드 → 런처(~/.local/bin) → plugin → MCP → Obsidian 테마
myelin-hub --vault ~/Vaults/me               # http://127.0.0.1:8787 → 온보딩 마법사(3+1 Domain) → 첫 ai-draft 승격
```
CLI 로만: `myelin init --vault ~/Vaults/me` → Obsidian 에서 열기 → Vault 폴더에서 `claude` → `/myelin:ingest <자료>` → `/myelin:distill` → Hub 에서 Promote.

요구 사항: Python 3.12, [uv](https://docs.astral.sh/uv/), git, Node 22 (Hub 웹), [Claude Code](https://claude.com/claude-code) 2.1.275+ (plugin/MCP), Google Chrome (e2e 선택).

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
| `myelin-mcp --vault <v>` · `myelin-hub --vault <v> [--port]` | MCP 서버 · Hub (localhost 전용) |

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
make check         # ruff + mypy --strict + pytest (406 tests)
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

## 9. 문서

- 가이드: [사용자](docs/guides/user-guide.md) · [관리자](docs/guides/admin-guide.md) · [MCP 설정](docs/guides/mcp-setup.md) · [파일럿](docs/guides/pilot-guide.md) · [60분 워크숍](docs/guides/workshop-60min.md) · [Day 1 체크리스트](docs/guides/day1-checklist.md)
- 스펙: [정본](docs/spec/MYELIN_Rev2.0.md) · [JSON Schema](docs/spec/schema/) · [Commons 구조](docs/spec/commons.md) · [컴포넌트 스펙](design/components.md)
- 보안: [위협 모델(STRIDE)](docs/security/threat-model.md) · [이름 확인(상표·도메인·GitHub)](docs/reports/P8/naming-check.md)
- 릴리스: [RELEASE_NOTES](docs/RELEASE_NOTES.md) · [CHANGELOG](CHANGELOG.md)

## 10. 검증 요약 (v1.0.0)

| 항목 | 값 |
|---|---|
| 테스트 | 406 (core 99% 커버리지) · Guard 차단 케이스 137 · Playwright e2e 4 · 성능 1 |
| Gate | P0~P8 스크립트 고정, `make gate P=<n>` |
| 성능 | 5,000 노트 검색 p95 17ms · 설치→첫 verified 0.5s(캐시 기준) |
| 접근성 | 텍스트 쌍 13개 전부 ≥ 4.5:1, 네온 텍스트 0, 색 하드코딩 0 |
| 보안 | STRIDE 21건, High 0 (2건 조치·회귀 테스트) |

## 11. 알려진 제약 · 남은 일

- 다크 모드 미지원(§8.3 가드레일 5) · Team 모드 인증 없음(Hub 는 localhost 전용) · Bash Guard 는 스크립트 파일 실행 부작용 미검사(settings.json ask) · 비식별 스캔은 휴리스틱(챔피언 리뷰 2중) · MCP 기밀 노출은 소유자 opt-in.
- **사람 참여 항목**: P7 파일럿 5명 온보딩·피드백 기록(`scripts/pilot.py`) → `make gate P=7` → `phase-P7` 태그 · KIPRIS 국내 상표 직접 조회 결과 기입 · Commons 챔피언 지정 · 정본 §9.2 Rollout Wave 1·2.
- 브랜드명 MYELIN 은 사내용 가칭(미국 동일 명칭 소프트웨어 상표 선출원 심사 중, 주요 도메인 점유). 대외 공개 시 결합형 `MYELIN KOS` 검토.

---
WDLAB · A3 Security · AI·ML·AX Research Division · 작성 Brian (Research Director, A3-AI WG) · 구현 Claude Code
