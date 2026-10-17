# PHASE_STATE

current_phase: P1
status: awaiting_approval   # in_progress | gate_pending | awaiting_approval
last_updated: 2026-10-18

> P0 완료(`phase-P0`). P1 Gate 통과(`make gate P=1`), 보고서 `docs/reports/P1.md`, 태그 `phase-P1`.
> **다음 Phase(P2)는 Brian의 "GO P2" 승인 후에만 착수한다.** 승인 시 current_phase를 P2, status를 in_progress로 바꾸고 아래 Next를 이어간다.

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

## Next (P2 — 승인 대기)
- [ ] P2-T1 Typer CLI 골격 `myelin` (init/add-domain/doctor/stats) + --vault 옵션
- [ ] P2-T2 myelin.yaml(5.3) 모델·로더 (owner/language/packs/domains/level/llm/commons)
- [ ] P2-T3 대화형 init 마법사 — 이름, 3+1 Domain, Pack 선택, Level (비대화형 플래그 동일)
- [ ] P2-T4 Vault 스캐폴더 — 6.1 폴더 구조, 기존 파일 존재 시 중단(fail-closed, 덮어쓰기 금지)
- [ ] P2-T5 템플릿·MOC·taxonomy 렌더러 (Pack → 10_Domains/<ID>/_MOC.md, 90_System/*)
- [ ] P2-T6 Vault CLAUDE.md 렌더러 (Pack 규칙 자동 생성 + 개인 섹션 보존)
- [ ] P2-T7 add-domain — Pack에서 Domain 추가, 기존 노트 불변
- [ ] P2-T8 doctor 규칙 8종 (스키마 위반 / fail-closed 링크 위반 / 고아 노트 / confidential+share 모순 / 깨진 링크 / id 중복 / 미등록 domain / 날짜 역전)
- [ ] P2-T9 stats — 11.1 지표 7종 산출 (JSON/표)
- [ ] P2-T10 golden snapshot 테스트 (init 결과 디렉터리 트리+내용 일치)
- [ ] P2-T11 doctor fixture 시드 위반 100% 검출 · 오탐 0 · init < 10초 벤치
- [ ] P2-T12 make gate P=2 · reports/P2.md · tag phase-P2

## Blockers
- (없음) — CI green은 GitHub 원격 push 후 확인 필요

## Decisions (→ ADR)
- ADR-0001: 기술 스택 · ADR-0002: Claude Code Plugin/Hook 현행 사양
- ADR-0003: 스키마 검증 정책 — Frontmatter 미지 필드 허용·보존 / Pack 미지 필드 금지 / 교차 필드 모순은 doctor 규칙(`consistency_issues()`) / accent 닫힌 집합 / 스칼라→리스트 관용
- P1 결정(ADR 불필요, 기록만): 측 파일 스키마 2종 추가 — `taxonomy.yaml`(terms[term, aliases, definition, domain]) · `interviews.yaml`(questions[id, prompt, domain, sub_moc, follow_ups, yields]). 정본 §5.2가 파일명만 지정하고 내용 스키마를 비워 두어 최소 형식으로 확정. 템플릿 placeholder는 `{{id}} {{date}} {{domain}} {{origin}} {{classification}} {{title}} {{source}} {{description}} {{sub_mocs}}` (P2 렌더러가 치환)

## Backlog (Phase 범위 밖)
- P2: doctor 규칙에 `Frontmatter.consistency_issues()` 4종 + 미지 필드 info 보고 포함 (ADR-0003)
- P2: `tests/fixtures/vaults/seeded-violations` 생성(doctor 100% 검출 Gate용) — basic 은 clean 유지
- P2: 템플릿 placeholder 치환 시 `domain` 은 YAML 리스트 형식으로 렌더
- P3: Bash용 PreToolUse hook (ADR-0002 D6), `claude plugin validate --strict` Gate 추가
- P5: `tokens.schema.json`; accent 집합 확장 시 ADR-0003 §6 갱신
- P7: a3.security-consulting Sub-MOC·용어 팀 챔피언과 확정, Org Pack 1종 추가
- P8: plugin/README marketplace 설치 한 줄
