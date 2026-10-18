# PHASE_STATE

current_phase: P5
status: in_progress   # in_progress | gate_pending | awaiting_approval
last_updated: 2026-10-18

> P0~P4 완료(`phase-P0`~`phase-P4`). 2026-10-18 Brian "GO P5" 승인으로 P5 착수.

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

## Next
- [ ] P5-T1 design/tokens.json 정본 확정 (8.1·8.4 전량) + JSON Schema
- [ ] P5-T2 생성 스크립트 tokens → CSS vars (emboss.css) / Tailwind preset / Obsidian theme.css
- [ ] P5-T3 컴포넌트 스펙 문서 (8.3 8종) + 상태 의미 체계(8.2)
- [ ] P5-T4 정적 컴포넌트 갤러리 (HTML, 토큰 CSS만 사용)
- [ ] P5-T5 접근성 검사 스크립트 — 텍스트 대비 4.5:1, 네온 위 텍스트 = --ink 규칙
- [ ] P5-T6 토큰 하드코딩 lint 규칙 (CSS/TSX에서 raw hex 금지)
- [ ] P5-T7 theme/obsidian-myelin-emboss (manifest.json, theme.css 생성물)
- [ ] P5-T8 갤러리 스크린샷 승인 · make gate P=5 · reports/P5.md · tag phase-P5

## Blockers
- (없음) — CI green은 GitHub 원격 push 후 확인 필요

## Decisions (→ ADR)
- ADR-0001~0006 (기술 스택 · Plugin/Hook · 스키마 검증 · myelin.yaml · Level-gated Guard · _patches 형식)
- ADR-0007 MCP 정책 — stdio 단일 Vault, 기본 읽기 전용(write_draft 는 `mcp.write_draft: true` + level ≥ 1 일 때만 **등록**), 기밀 정책은 소유자 opt-in(`mcp.expose_confidential`, 기본 false → confidential·40_IP 본문 비공개·검색 제외), 색인 `.myelin/index.db`(FTS5 trigram + 2자 이하 토큰 LIKE 하이브리드, 증분 갱신), myelin.yaml `mcp:` 블록 추가(ADR-0004 보강)
- P4 결정(기록): **개발 인터프리터 고정** — 이 워크스테이션의 pyenv 3.12.11 은 바이너리 3.12.3 + stdlib 3.12.11 혼합 설치로 `asyncio.run` 세그폴트. Makefile 이 `/usr/bin/python3.12` 가 있으면 `UV_PYTHON` 으로 고정(venv 재생성 완료). CI(ubuntu-latest + setup-python 3.12)는 영향 없음. P8 설치 스크립트에서 인터프리터 검증 단계 필요.
- P4 결정(기록): mcp SDK 2.x(`MCPServer`) 사용. 도구 핸들러는 async, `VaultIndex` 는 RLock 커넥션 파사드로 스레드 안전. 성능: 5,000 노트 색인 구축 약 12s(ruamel RT 파서), 검색 p50 12ms · p95 17ms, no-op refresh 274ms.

## Backlog (Phase 범위 밖)
- P5: `tokens.schema.json`; accent 집합 확장 시 ADR-0003 §6 갱신
- P6: Hub API 는 `VaultService`/`VaultIndex` 재사용(전체 스캔 대체) · Review Gate 가 `_patches` 적용(ADR-0006) · Guard 차단 이벤트 표시 · 온보딩 마법사는 `init_vault` 공유
- P6/P8: 색인 구축 속도 — 대형 Vault(≥ 20k 노트)면 safe 로더로 1차 파싱 후 RT 파서는 쓰기 경로에서만 사용 검토
- P7: a3.security-consulting Sub-MOC·용어 확정, Org Pack 1종 추가
- P8: 위협 모델에서 Guard 한계(스크립트 실행 부작용, CLI 경유 쓰기)·MCP 기밀 정책 재평가 · 설치 스크립트에 인터프리터 일관성 검사 · plugin/README marketplace 한 줄 · Pack 번들 경로
