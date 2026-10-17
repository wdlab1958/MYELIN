# PHASE_STATE

current_phase: P1
status: in_progress   # in_progress | gate_pending | awaiting_approval
last_updated: 2026-10-18

> P0 완료(태그 `phase-P0`). 2026-10-18 Brian "GO P1" 승인으로 P1 착수.

## Done
- [x] P0-T1 모노레포 골격 생성 (10.1 구조) · git init · .gitignore
- [x] P0-T2 docs/spec/MYELIN_Rev2.0.md 정본 등재 + docs/phases/P0~P8.md 분리
- [x] P0-T3 CLAUDE.md(부록 A) · PHASE_STATE.md(부록 B) 작성
- [x] P0-T4 uv workspace · 패키지 4종 골격(myelin-core/cli/mcp/hub-api) · ruff/mypy/pytest 설정
- [x] P0-T5 Makefile(gate/test/lint/typecheck) · scripts/gate.py Gate 체계
- [x] P0-T6 GitHub Actions CI (lint + typecheck + test + gate P=0)
- [x] P0-T7 ADR-0001 기술 스택 · ADR-0002 Claude Code Plugin/Hook 현행 사양 확인 메모
- [x] P0-T8 design/tokens.json 시드(8.1) · plugin/ · theme/ · tests/fixtures 자리표시
- [x] P0-T9 make gate P=0 통과 · docs/reports/P0.md · git tag phase-P0 · 멈추고 승인 요청

## Next
- [ ] P1-T1 Frontmatter v2 Pydantic 모델 (6.2 정본: id/type/domain/status/origin/confidence/classification/share/source/created/reviewed/tags)
- [ ] P1-T2 Note 파서 (YAML frontmatter + body, wikilink 추출) + 라운드트립 테스트
- [ ] P1-T3 Pack 스키마 Pydantic 모델 (5.2: pack/version/kind/maintainer/requires/domains[])
- [ ] P1-T4 Domain 모델 (id/name/accent/description/sub_mocs/note_types/taxonomy_seed/templates/interview_bank/classification_default/compose_targets)
- [ ] P1-T5 Pack 로더 — 디렉터리 탐색, requires 의존성 해석(semver), 순환·누락 오류
- [ ] P1-T6 JSON Schema export (frontmatter.schema.json, pack.schema.json) + CLI 없이 함수로 제공
- [ ] P1-T7 packs/myelin.core 작성 (note types, 기본 템플릿, 공통 taxonomy)
- [ ] P1-T8 packs/brian.physical-ai 작성 (5.5 D1~D4, Sub-MOC, interview bank 초안)
- [ ] P1-T9 packs/a3.security-consulting 초안 작성 (5.2 예시 기준)
- [ ] P1-T10 tests/fixtures/vaults/basic — 30+ 노트 fixture (모든 type·status·origin 조합 포함)
- [ ] P1-T11 잘못된 Pack fixture 10종 + 각기 명확한 오류 메시지 테스트
- [ ] P1-T12 커버리지 ≥ 90% 확인 · make gate P=1 · reports/P1.md · tag phase-P1

## Blockers
- (없음) — CI green은 GitHub 원격 push 후 확인 필요 (로컬에서는 동일 명령 `make check` + `make gate P=0` 통과)

## Decisions (→ ADR)
- ADR-0001: 기술 스택 (정본 §4.4 확정; uv workspace, hatchling, ruff/mypy strict)
- ADR-0002: Claude Code Plugin/Hook 현행 사양 (D1~D7: NotebookEdit matcher 추가, onFailure block, exit 2 단일 차단 수단, Vault 루트 결정 순서, `Edit(...)` deny 규칙만 유효, Bash hook 보강, MCP 비번들)

## Backlog (Phase 범위 밖)
- P3: Bash용 PreToolUse hook (ADR-0002 D6) — 정본 §7.2는 deny 규칙만 언급, 접두어 매칭 한계로 hook 보강 필요
- P3: `claude plugin validate --strict` 를 P3 Gate에 추가 (ADR-0002 §7)
- P5: `design/tokens.json` JSON Schema(`tokens.schema.json`) 작성 — P0 시드는 `$schema` 참조만 둠
- P8: plugin/README에 marketplace 설치 한 줄 추가 (validate advice)
