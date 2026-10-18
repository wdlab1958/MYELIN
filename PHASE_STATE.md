# PHASE_STATE

current_phase: P4
status: in_progress   # in_progress | gate_pending | awaiting_approval
last_updated: 2026-10-18

> P0~P3 완료(`phase-P0`~`phase-P3`). 2026-10-18 Brian "GO P4" 승인으로 P4 착수.

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

## Next
- [ ] P4-T1 myelin-core 색인기 — SQLite FTS5 (.myelin/index.db), frontmatter 컬럼, 증분 갱신(mtime/hash)
- [ ] P4-T2 stdio MCP 서버 골격 (MCP Python SDK) + Vault 루트 경계 검사 유틸
- [ ] P4-T3 search_notes (FTS + domain/status/type 필터)
- [ ] P4-T4 get_note (confidential 노출 정책: local 클라이언트만) · query_frontmatter
- [ ] P4-T5 list_domains / vault_stats
- [ ] P4-T6 write_draft — myelin.yaml 명시 허용 + Level ≥ 1일 때만 tool 등록
- [ ] P4-T7 경로 이탈 테스트 (.., symlink, 절대경로) · 기본 읽기 전용 확인
- [ ] P4-T8 5,000 노트 fixture 생성기 · search p95 < 300ms 벤치
- [ ] P4-T9 Claude Desktop/Code 설정 가이드 문서 · make gate P=4 · reports/P4.md · tag phase-P4

## Blockers
- (없음) — CI green은 GitHub 원격 push 후 확인 필요

## Decisions (→ ADR)
- ADR-0001 기술 스택 · ADR-0002 Plugin/Hook 사양 · ADR-0003 스키마 검증 정책 · ADR-0004 myelin.yaml
- ADR-0005 Level-gated Guard — 허용 경로 Level 누적(L0 없음 / L1 ai-drafts·50_Journal / L2 +_patches·80_Outputs/drafts / L3 +40_IP/candidates), Bash Guard 추가(리다이렉션·writer·인라인 인터프리터·파괴적 git·`$(…)`·`cd`+쓰기 차단), Skill 비노출은 3겹(SKILL.md 자기검사 + CLAUDE.md 목록 + Guard), Vault `.claude/settings.json` 2차 방어
- ADR-0006 `_patches/` 형식 — patch 1 / target / kind(append|replace|frontmatter) / rationale / status, 적용은 Hub(P6)만
- P3 결정(기록): doctor fail-closed 규칙의 "claude 초안 위치" 기준을 ai-drafts 단일에서 §7.1 쓰기 범위 4곳(ai-drafts·50_Journal·80_Outputs/drafts·40_IP/candidates)으로 확장. `_COMMON.md` 가 모든 Skill 의 공통 규약(Vault/Level 확인 → 쓰기 범위 → Frontmatter v2 → doctor → 보고). `myelin interview-bank` 가 Pack 질문 은행을 Skill 에 공급.

## Backlog (Phase 범위 밖)
- P4: `.myelin/index.db` 색인 → doctor/stats 전체 스캔을 색인 기반으로 전환(대형 Vault); MCP 는 플러그인 번들 아님(ADR-0002 D7), write_draft 는 myelin.yaml 명시 허용 + Level ≥ 1
- P5: `tokens.schema.json`; accent 집합 확장 시 ADR-0003 §6 갱신
- P6: Hub Review Gate 가 `_patches` 적용(ADR-0006) + Guard 차단 이벤트 표시; 온보딩 마법사는 `init_vault` 공유
- P7: a3.security-consulting Sub-MOC·용어 확정, Org Pack 1종 추가
- P8: 위협 모델에서 Guard 한계 재평가(스크립트 파일 실행 부작용, `uv run myelin init` 등 CLI 경유 쓰기) · plugin/README marketplace 설치 한 줄 · Pack 번들 경로
