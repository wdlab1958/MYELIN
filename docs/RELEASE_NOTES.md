# MYELIN v1.0.0 — Release Notes (2026-10-18)

Personal Knowledge OS — powered by Obsidian + Claude. 정본 `docs/spec/MYELIN_Rev2.0.md`(WDLAB-MYELIN-SPEC Rev 2.0) 의 P0~P8 구현.

## 포함
- **MYELIN Vault 표준** — Frontmatter v2, 폴더 표준(§6), Domain Pack 체계(Core / Reference `brian.physical-ai` / Org `org.security-consulting`, `org.incident-response` / Personal).
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
- **Bash Guard 는 스크립트 파일 실행의 부작용을 검사하지 않는다** — `python x.py` 등은 settings.json 에서 ask. 커밋 이력으로 사후 감사.
- **비식별 스캔은 휴리스틱** — 별명·프로젝트 코드는 `deid.yaml` 에 등록해야 잡힌다. 챔피언 PR 리뷰가 2차 통제.
- **MCP 기밀 노출은 소유자 opt-in** — 로컬 LLM 세션에서만 켤 것.
- **브랜드명 MYELIN 은 사내용** — 미국에 동일 명칭 소프트웨어 상표 선출원(심사 중)이 있고 주요 도메인이 점유됨. 대외 공개 시 `MYELIN KOS` 등 결합형 검토(`docs/reports/P8/naming-check.md`). KIPRIS 국내 조회는 사람이 직접 수행.
- **P7 파일럿 결과는 미기록** — 도구는 준비됐고 사람 운영이 필요(`docs/reports/P7.md`).
- Vault CLAUDE.md 의 personal 블록 외 영역은 Pack 재생성 시 덮어쓴다(의도된 동작).
- 색인 구축은 5,000 노트에 약 12초(ruamel RT 파서). 20k+ Vault 는 v1.1 에서 safe 로더 검토.

## 업그레이드
`git pull && scripts/install.sh --vault <v>` → `myelin doctor`.
