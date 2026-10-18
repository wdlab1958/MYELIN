# PHASE_STATE

current_phase: P8
status: awaiting_approval   # in_progress | gate_pending | awaiting_approval
last_updated: 2026-10-18

> **P8 Gate PASS → `phase-P8` · `v1.0.0` 태그.** 정본 Rev 2.0 의 구현 Phase 는 모두 끝났다(`docs/reports/P8.md` 회고). P7 은 사람 참여 Gate 2항목이 열린 상태(`gate_pending`, 태그 없음). **남은 사람 참여 항목**: ① P7 파일럿 기록(`scripts/pilot.py record`)과 피드백 리포트 → `make gate P=7` → `phase-P7` 태그 ② KIPRIS 국내 상표 직접 조회 결과를 `docs/reports/P8/naming-check.md` 에 기입 ③ (선택) 변리사 검토.

## Done
### P0
- [x] P0-T1 모노레포 골격 생성 (10.1 구조) · git init · .gitignore
- [x] P0-T2 docs/spec/MYELIN_Rev2.0.md 정본 등재 + docs/phases/P0~P8.md 분리
- [x] P0-T3 CLAUDE.md(부록 A) · PHASE_STATE.md(부록 B) 작성
- [x] P0-T4 uv workspace · 패키지 4종 골격(myelin-core/cli/mcp/hub-api) · ruff/mypy/pytest 설정
- [x] P0-T5 Makefile(gate/test/lint/typecheck) · scripts/gate.py Gate 체계
- [x] P0-T6 GitHub Actions CI (lint + typecheck + test + gate P=0)
- [x] P0-T7 ADR-0001 기술 스택 · ADR-0002 Claude Code Plugin/Hook 현행 사양 확인 메모
- [x] P0-T8 design/tokens.json 시드(8.1) · plugin/ · theme/ · tests/fixtures 자리표시
- [x] P0-T9 make gate P=0 통과 · docs/reports/P0.md · git tag phase-P0 · 멈추고 승인 요청
### P1
- [x] P1-T1 Frontmatter v2 Pydantic 모델 (6.2 정본: id/type/domain/status/origin/confidence/classification/share/source/created/reviewed/tags)
- [x] P1-T2 Note 파서 (YAML frontmatter + body, wikilink 추출) + 라운드트립 테스트
- [x] P1-T3 Pack 스키마 Pydantic 모델 (5.2: pack/version/kind/maintainer/requires/domains[])
- [x] P1-T4 Domain 모델 (id/name/accent/description/sub_mocs/note_types/taxonomy_seed/templates/interview_bank/classification_default/compose_targets)
- [x] P1-T5 Pack 로더 — 디렉터리 탐색, requires 의존성 해석(semver), 순환·누락 오류
- [x] P1-T6 JSON Schema export (frontmatter.schema.json, pack.schema.json) + CLI 없이 함수로 제공
- [x] P1-T7 packs/myelin.core 작성 (note types, 기본 템플릿, 공통 taxonomy)
- [x] P1-T8 packs/brian.physical-ai 작성 (5.5 D1~D4, Sub-MOC, interview bank 초안)
- [x] P1-T9 packs/a3.security-consulting 초안 작성 (5.2 예시 기준)
- [x] P1-T10 tests/fixtures/vaults/basic — 30+ 노트 fixture (모든 type·status·origin 조합 포함)
- [x] P1-T11 잘못된 Pack fixture 10종 + 각기 명확한 오류 메시지 테스트
- [x] P1-T12 커버리지 ≥ 90% 확인 · make gate P=1 · reports/P1.md · tag phase-P1
### P2
- [x] P2-T1 Typer CLI 골격 `myelin` (init/add-domain/doctor/stats) + --vault 옵션
- [x] P2-T2 myelin.yaml(5.3) 모델·로더 (owner/language/packs/domains/level/llm/commons)
- [x] P2-T3 대화형 init 마법사 — 이름, 3+1 Domain, Pack 선택, Level (비대화형 플래그 동일)
- [x] P2-T4 Vault 스캐폴더 — 6.1 폴더 구조, 기존 파일 존재 시 중단(fail-closed, 덮어쓰기 금지)
- [x] P2-T5 템플릿·MOC·taxonomy 렌더러 (Pack → 10_Domains/<ID>/_MOC.md, 90_System/*)
- [x] P2-T6 Vault CLAUDE.md 렌더러 (Pack 규칙 자동 생성 + 개인 섹션 보존)
- [x] P2-T7 add-domain — Pack에서 Domain 추가, 기존 노트 불변
- [x] P2-T8 doctor 규칙 8종 (스키마 위반 / fail-closed 링크 위반 / 고아 노트 / confidential+share 모순 / 깨진 링크 / id 중복 / 미등록 domain / 날짜 역전)
- [x] P2-T9 stats — 11.1 지표 7종 산출 (JSON/표)
- [x] P2-T10 golden snapshot 테스트 (init 결과 디렉터리 트리+내용 일치)
- [x] P2-T11 doctor fixture 시드 위반 100% 검출 · 오탐 0 · init < 10초 벤치
- [x] P2-T12 make gate P=2 · reports/P2.md · tag phase-P2
### P3
- [x] P3-T1 plugin/.claude-plugin/plugin.json + skills 디렉터리 골격 (ADR-0002 사양 준수)
- [x] P3-T2 hooks/hooks.json + guard_write.py (표준 라이브러리만, 판단 불가 → exit 2)
- [x] P3-T3 Guard 테스트 — 허용 외 경로·Vault 밖·심볼릭 링크·`..` 경로·빈 file_path·비JSON 입력 차단 100%
- [x] P3-T4 Vault용 .claude/settings.json 템플릿 (Bash 우회 deny 규칙) + CLI init에 포함
- [x] P3-T5 Level별 Skill 개방 로직 (myelin.yaml level 0~3 → Skill 노출/비활성)
- [x] P3-T6 /ingest SKILL.md + fixture e2e (literature 초안이 doctor 통과)
- [x] P3-T7 /distill SKILL.md + fixture e2e
- [x] P3-T8 /interview SKILL.md + Pack interview_bank 연동
- [x] P3-T9 /link SKILL.md (_patches 제안 형식 정의) · /compose · /review · /ip-scan SKILL.md
- [x] P3-T10 Level 0에서 쓰기 Skill 비활성 확인 테스트 · make gate P=3 · reports/P3.md · tag phase-P3
### P4
- [x] P4-T1 myelin-core 색인기 — SQLite FTS5 (.myelin/index.db), frontmatter 컬럼, 증분 갱신(mtime/hash)
- [x] P4-T2 stdio MCP 서버 골격 (MCP Python SDK) + Vault 루트 경계 검사 유틸
- [x] P4-T3 search_notes (FTS + domain/status/type 필터)
- [x] P4-T4 get_note (confidential 노출 정책: local 클라이언트만) · query_frontmatter
- [x] P4-T5 list_domains / vault_stats
- [x] P4-T6 write_draft — myelin.yaml 명시 허용 + Level ≥ 1일 때만 tool 등록
- [x] P4-T7 경로 이탈 테스트 (.., symlink, 절대경로) · 기본 읽기 전용 확인
- [x] P4-T8 5,000 노트 fixture 생성기 · search p95 < 300ms 벤치
- [x] P4-T9 Claude Desktop/Code 설정 가이드 문서 · make gate P=4 · reports/P4.md · tag phase-P4
### P5
- [x] P5-T1 design/tokens.json 정본 확정 (8.1·8.4 전량) + JSON Schema
- [x] P5-T2 생성 스크립트 tokens → CSS vars (emboss.css) / Tailwind preset / Obsidian theme.css
- [x] P5-T3 컴포넌트 스펙 문서 (8.3 8종) + 상태 의미 체계(8.2)
- [x] P5-T4 정적 컴포넌트 갤러리 (HTML, 토큰 CSS만 사용)
- [x] P5-T5 접근성 검사 스크립트 — 텍스트 대비 4.5:1, 네온 위 텍스트 = --ink 규칙
- [x] P5-T6 토큰 하드코딩 lint 규칙 (CSS/TSX에서 raw hex 금지)
- [x] P5-T7 theme/obsidian-myelin-emboss (manifest.json, theme.css 생성물)
- [x] P5-T8 갤러리 스크린샷 승인 · make gate P=5 · reports/P5.md · tag phase-P5
### P6
- [x] P6-T1 FastAPI 앱 골격 (myelin-core 재사용), localhost 바인딩, 읽기 API
- [x] P6-T2 React 18 + Vite + TS + Tailwind(Emboss preset) 골격, 토큰 외 색 금지 lint
- [x] P6-T3 Dashboard 화면 (KPI Tile, 지표 11.1)
- [x] P6-T4 My Domains 화면 (Domain Orb, Domain Map → MOC)
- [x] P6-T5 Inbox / Review Gate 화면 — Promote(Lime)/Reject, 승격 시 git commit
- [x] P6-T6 Domain Packs 화면 (Pack 편집기)
- [x] P6-T7 Settings 화면 + 온보딩 마법사 (init과 동일 로직 공유)
- [x] P6-T8 Playwright e2e: 신규 사용자 온보딩 → 첫 노트 승격 · 커밋 생성 확인
- [x] P6-T9 사용자 클릭 없이 Vault 쓰기 0 검증(쓰기 경로 감사 테스트) · 스크린샷 docs/reports/P6/ · make gate P=6 · tag phase-P6
### P7
- [x] P7-T1 Commons Git 구조 정의 (packs registry + notes) · 사내 Pack Registry 포맷
- [x] P7-T2 publish 흐름 — share:true + verified + classification ≤ internal 검사 → PR 생성, 사용자 확인 단계 필수
- [x] P7-T3 비식별 체크리스트(고객명·IP·기밀) + publish 전 자동 스캔
- [x] P7-T4 confidential / share:false publish 차단 100% 테스트
- [x] P7-T5 opt-in 익명 지표 집계 (11.2) — 개인 Vault 내용 미전송 보장
- [x] P7-T6 Org Pack 2종 확정 (팀 챔피언과) · Pack 진화 제안 흐름
- [x] P7-T7 파일럿 가이드 · 60분 워크숍 자료(9.3) · Day 1 체크리스트(부록 D)
- [ ] P7-T8 파일럿 5명+ 온보딩 15분 측정 · 피드백 리포트 · make gate P=7 · tag phase-P7
### P8
- [x] P8-T1 위협 모델(STRIDE) 문서 — Guard 우회, MCP 경로 이탈, Commons 유출, 공급망
- [x] P8-T2 High 항목 조치 및 회귀 테스트
- [x] P8-T3 설치 스크립트 (uv tool install, plugin 등록, MCP 설정, Theme 복사)
- [x] P8-T4 사용자 가이드 · 관리자 가이드 · 릴리스 노트(알려진 제약: 다크 모드 미지원 등)
- [x] P8-T5 KIPRIS 상표 검색(제9류·제42류) · 도메인 · GitHub 조직명 확인 결과 기록
- [x] P8-T6 신규 사용자 설치→첫 verified 노트 < 15분 측정
- [x] P8-T7 v1.0 태그 · 회고 · make gate P=8 · reports/P8.md

## Next
- [ ] P7(사람): 파일럿 운영·기록 → `make gate P=7` → `git tag phase-P7`
- [ ] P8(사람): KIPRIS 직접 조회 결과 기입(제9류·제42류), 필요 시 결합형 명칭(MYELIN KOS) 결정
- (P8 이후는 구현이 아니라 운영: 정본 §9.2 Rollout Wave 1·2)

## Blockers
- 사람 참여: 파일럿 운영(3주), 챔피언 지정, KIPRIS 조회. 코드 측 블로커 없음.
- CI: **green** — github.com/wdlab1958/MYELIN `main` run 39087153818 (check + gate P=8, 2026-10-18). 기존 원격 main 은 `main-alt-2026-10-18` 브랜치에 보존.

## Decisions (→ ADR)
- ADR-0001~0010 (변경 없음)
- P8 결정(기록): 위협 모델 High 2건(T08 Hub Host/Origin 검증, T09 정적 서빙 경로 이탈) 조치 + 회귀 테스트. 스크립트 인터프리터 실행은 Vault settings.json 에서 ask(T02 완화). 설치는 `scripts/install.sh`(런처 = `uv --directory <repo> run …`, 기존 파일 보존, 테마 .bak). 로컬 plugin marketplace(`.claude-plugin/marketplace.json`, 이름 `myelin-local`), plugin 버전 1.0.0. 이름 확인: 미국 "MYELIN" 소프트웨어 상표 선출원(심사 중)·주요 도메인 점유·GitHub `myelin` 개인 계정 사용 중 → 사내 사용은 MYELIN 유지, 대외 공개 시 결합형. "설치→첫 verified" 자동 측정 1초 미만(캐시된 uv 기준; 신규 환경은 네트워크 의존).

## Backlog (v1.1+)
- Team 모드 인증(Hub 비-loopback) · 다크 모드 토큰 · CI 에 Node 22/Chrome(e2e) 단계 · Commons CI 비식별 재스캔 · Hub 에서 Registry Pack 설치 · 20k+ Vault 색인 가속(safe 로더) · 정본 Rev 2.1 제안서(§8.1 값, §7.2 Level 누적, MCP 기밀 opt-in, Hub 쓰기 헤더, Commons 비식별 차단, 이름 결합형) · 로컬 임베딩 검색(선택)
