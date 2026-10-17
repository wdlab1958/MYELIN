# PHASE_STATE

current_phase: P2
status: awaiting_approval   # in_progress | gate_pending | awaiting_approval
last_updated: 2026-10-18

> P0·P1 완료(`phase-P0`, `phase-P1`). P2 Gate 통과(`make gate P=2`), 보고서 `docs/reports/P2.md`, 태그 `phase-P2`.
> **다음 Phase(P3)는 Brian의 "GO P3" 승인 후에만 착수한다.** 승인 시 current_phase를 P3, status를 in_progress로 바꾸고 아래 Next를 이어간다.

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

## Next (P3 — 승인 대기)
- [ ] P3-T1 plugin/.claude-plugin/plugin.json + skills 디렉터리 골격 (ADR-0002 사양 준수)
- [ ] P3-T2 hooks/hooks.json + guard_write.py (표준 라이브러리만, 판단 불가 → exit 2)
- [ ] P3-T3 Guard 테스트 — 허용 외 경로·Vault 밖·심볼릭 링크·`..` 경로·빈 file_path·비JSON 입력 차단 100%
- [ ] P3-T4 Vault용 .claude/settings.json 템플릿 (Bash 우회 deny 규칙) + CLI init에 포함
- [ ] P3-T5 Level별 Skill 개방 로직 (myelin.yaml level 0~3 → Skill 노출/비활성)
- [ ] P3-T6 /ingest SKILL.md + fixture e2e (literature 초안이 doctor 통과)
- [ ] P3-T7 /distill SKILL.md + fixture e2e
- [ ] P3-T8 /interview SKILL.md + Pack interview_bank 연동
- [ ] P3-T9 /link SKILL.md (_patches 제안 형식 정의) · /compose · /review · /ip-scan SKILL.md
- [ ] P3-T10 Level 0에서 쓰기 Skill 비활성 확인 테스트 · make gate P=3 · reports/P3.md · tag phase-P3

## Blockers
- (없음) — CI green은 GitHub 원격 push 후 확인 필요

## Decisions (→ ADR)
- ADR-0001 기술 스택 · ADR-0002 Plugin/Hook 사양 · ADR-0003 스키마 검증 정책
- ADR-0004 myelin.yaml 스키마 — `domains.extra` 추가(+1 자리), primary만 필수, 미지 필드 금지, `add-domain`은 extra에만 추가
- P2 결정(기록): doctor "미등록 domain"의 기준 = 설정 Domain ∪ 설정 Pack이 선언한 Domain(Pack 해석 불가 시 설정만). 고아 노트 판정은 00_Inbox·99_Archive·moc 제외. 템플릿 placeholder 9종(`{{id}} {{date}} {{domain}} {{origin}} {{classification}} {{title}} {{source}} {{description}} {{sub_mocs}}`)은 90_System/templates 에 그대로 복사되고 치환은 Skill(P3)/Hub(P6)가 노트 생성 시 수행. 테스트 훅 `MYELIN_NOW`(ISO) 로 생성 시각 고정.
- Vault `CLAUDE.md`·`90_System/taxonomy.md` 는 `<!-- myelin:personal:start/end -->` 블록을 재생성 시 보존.

## Backlog (Phase 범위 밖)
- P3: Vault용 `.claude/settings.json` 템플릿(`Edit(...)` deny)을 `myelin init` 산출물에 추가 (ADR-0002 D5) → golden 갱신
- P3: Bash용 PreToolUse hook (ADR-0002 D6), `claude plugin validate --strict` Gate 추가
- P3: Skill이 템플릿 placeholder를 치환해 ai-drafts 노트를 만들 때 `render_template()` 재사용
- P4: `.myelin/index.db` 색인 → doctor/stats 의 전체 스캔을 색인 기반으로 전환(대형 Vault)
- P5: `tokens.schema.json`; accent 집합 확장 시 ADR-0003 §6 갱신
- P6: Hub 온보딩 마법사는 `myelin_cli.app.init` 과 동일 로직(`MyelinConfig` + `init_vault`) 공유
- P7: a3.security-consulting Sub-MOC·용어 팀 챔피언과 확정, Org Pack 1종 추가
- P8: plugin/README marketplace 설치 한 줄 · `uv tool install` 배포 시 Pack 번들 경로(`default_pack_roots`) 확정
