# MYELIN v1.2.0 — Release Notes (2026-10-18)

## v1.2.0 — 설계 철학 갭 보완
세 의도(복리·사람 승격·개인 소유)를 장치로 닫았다: 미엘린 강도·재사용 KPI·환류, 읽음 확인, 기밀 라우팅 장치(`MYELIN_LLM=local`)·Vault pre-commit 훅, Commons 인용 집계·push/PR. 정본 Rev 2.1 부록(`docs/spec/MYELIN_Rev2.1-addendum.md`), ADR-0011·0012, `CHANGELOG.md` v1.2.0. 운영 변경: 로컬 LLM 세션에서만 `MYELIN_LLM=local` 을 설정한다. 기존 Vault 는 `myelin doctor --install-hook` 으로 pre-commit 장치를 설치한다.


## v1.1.1 — QA 캠페인 수정
A/B · E2E · Chaos · Gap · Agent 5종 테스트(`docs/reports/QA-2026-10-18.md`)에서 찾은 결함 수정. 목록은 `CHANGELOG.md` v1.1.1. 플러그인 1.0.1.

# MYELIN v1.1.0 — Release Notes (2026-10-18)

## v1.1.0 추가
- patch 적용이 **계획 → diff 미리보기 → digest 확인 → 적용** 으로 바뀌었다(ADR-0006 보강). `under` 로 제목 구획에 append, frontmatter patch 는 허용 키만. 적용/거부된 patch 는 `_patches/applied|rejected/` 에 남는다.
- `scripts/install.sh --claude` 가 있을 때만 Claude Code plugin/MCP 를 등록한다(opt-in). `scripts/install_obsidian.sh` 가 Obsidian 을 설치하고 테마를 선선택한다. 새 Vault 는 Obsidian 테마가 미리 들어간 채 생성된다.
- Obsidian: 노트 제목에 verified/ai-draft/blocked 상태 링·칩(`cssclasses`). 사용자 가이드(docx/xlsx/png), Obsidian 연동 가이드.

# MYELIN v1.0.0 — Release Notes (2026-10-18)

Personal Knowledge OS — powered by Obsidian + Claude. 정본 `docs/spec/MYELIN_Rev2.0.md`(WDLAB-MYELIN-SPEC Rev 2.0) 의 P0~P8 구현.

## 포함
- **MYELIN Vault 표준** — Frontmatter v2, 폴더 표준(§6), Domain Pack 체계(Core / Reference `brian.physical-ai` / Org `a3.security-consulting`, `a3.incident-response` / Personal).
- **MYELIN CLI** — `init`(3+1 마법사) · `add-domain` · `doctor`(규칙 8종) · `stats` · `skills` · `interview-bank` · `publish` · `pack-propose` · `metrics` · `commons`.
- **MYELIN for Claude Code** — Skill 7종(`/ingest /distill /interview /review /link /compose /ip-scan`), Level-gated Fail-closed Guard(Write/Edit/NotebookEdit + Bash), Vault `.claude/settings.json` 2차 방어.
- **MYELIN MCP** — stdio, 읽기 전용 기본(`search_notes get_note query_frontmatter list_domains vault_stats`), opt-in `write_draft`, 기밀 비노출 기본.
- **MYELIN Emboss** — `design/tokens.json` 단일 원천 → CSS/Tailwind/Obsidian Theme, 대비 4.5:1 자동 검사.
- **MYELIN Hub** — Dashboard · My Domains · Inbox/Review Gate(Promote/Reject/패치 적용/Commons 제안) · Domain Packs · Settings · 온보딩 마법사. 모든 쓰기는 사람 클릭 + git commit.
- **MYELIN Commons** — 공개 하드 게이트 + 비식별 스캔 + 확인 단계 + 브랜치/PR, Pack Registry, 익명 지표(opt-in).
- 설치 스크립트 `scripts/install.sh`, 로컬 plugin marketplace, 가이드(사용자·관리자·파일럿·MCP), 위협 모델(STRIDE, High 0).

## 검증
- 테스트 400+ (core 99% 커버리지), Guard 차단 케이스 137, Playwright e2e(온보딩→승격), 5,000 노트 검색 p95 17ms, 설치→첫 verified 노트 자동 측정 < 15분.

## 알려진 제약
- **다크 모드 미지원** (정본 §8.3 가드레일 5). 토큰 `modes` 만 예약.
- **Team 모드 인증 없음** — Hub 는 localhost 전용. 공유 호스트에서 띄우지 말 것.
- **Bash Guard 의 범위는 Vault 쓰기 정책이다** — Vault 내부 스크립트 실행·stdin 스크립트·`find -delete`·`curl -o` 등은 차단하지만(v1.1.1), Vault 밖 스크립트·패키지 설치·네트워크 송신(`curl -T`, `scp`)은 검사하지 않는다. settings.json 에서 `bash/sh/perl/ruby/curl/wget` 은 ask. 커밋 이력으로 사후 감사.
- **비식별 스캔은 휴리스틱** — 별명·프로젝트 코드는 `deid.yaml` 에 등록해야 잡힌다. 챔피언 PR 리뷰가 2차 통제.
- **MCP 기밀 노출은 소유자 opt-in 이며 로컬 프로세스(`MYELIN_LLM=local`)에서만 유효** — 외부 세션에서는 무시된다(v1.2.0). 잔여 위험(40_IP 밖 confidential 제목, `.myelin/index.db` 캐시, Vault 밖 스크립트)은 ADR-0011.
- **브랜드명 MYELIN 은 사내용** — 미국에 동일 명칭 소프트웨어 상표 선출원(심사 중)이 있고 주요 도메인이 점유됨. 대외 공개 시 `MYELIN KOS` 등 결합형 검토(`docs/reports/P8/naming-check.md`). KIPRIS 국내 조회는 사람이 직접 수행.
- **P7 파일럿 결과는 미기록** — 도구는 준비됐고 사람 운영이 필요(`docs/reports/P7.md`).
- Vault CLAUDE.md 의 personal 블록 외 영역은 Pack 재생성 시 덮어쓴다(의도된 동작).
- 색인 구축은 5,000 노트에 약 12초(ruamel RT 파서). 20k+ Vault 는 v1.1 에서 safe 로더 검토.

## 업그레이드
`git pull && scripts/install.sh --vault <v>` → `myelin doctor`.
