# PHASE_STATE
current_phase: P1
status: awaiting_approval      # in_progress | gate_pending | awaiting_approval
last_updated: 2026-10-18 09:10 KST
approved: "GO P1" (Brian, 2026-10-18 08:06)
gate: P1 PASS (docs/reports/P1.md)

## Done
- P0 — Bootstrap: Gate PASS 29/29 (docs/reports/P0.md)
- [x] P1-T1 scripts/gate.py 에 P1 Gate 검사 추가 (검사 중 예외 = FAIL)
- [x] P1-T2 pydantic, ruamel.yaml 도입 + ADR-0003
- [x] P1-T3 Frontmatter 모델 (§6.2) — extra 필드 보존, share+confidential 정책 검사, id 불변 검사
- [x] P1-T4 Note 파서 — wikilink(alias/heading/embed), 코드 블록 무시, 구조화 오류
- [x] P1-T5 Pack / Domain / Taxonomy / InterviewBank 모델 — 필드 단위 오류 위치
- [x] P1-T6 Pack 로더·해석기 — 참조 파일 검증, 경로 탈출 차단, 순환·버전·누락·Domain 충돌
- [x] P1-T7 JSON Schema export (schemas/ 4종)
- [x] P1-T8 packs/myelin.core (템플릿 9종)
- [x] P1-T9 packs/brian.physical-ai (D1~D4, taxonomy 16항목, interview 10문항)
- [x] P1-T10 packs/org.security-consulting 초안
- [x] P1-T11 fixtures: minimal vault 35 노트(생성기 포함), 잘못된 Pack 13종

## Next (P2 — "GO P2" 승인 후 시작)
- [ ] P2-T1 scripts/gate.py 에 P2 Gate 검사 추가
- [ ] P2-T2 Typer 도입, 명령 골격 (init / add-domain / doctor / stats)
- [ ] P2-T3 init: 대화형 + 비대화형, 3+1 Domain 선택, Level, 기존 파일 있으면 중단
- [ ] P2-T4 렌더링: 폴더·MOC·템플릿·taxonomy.md·Vault CLAUDE.md·myelin.yaml (+ myelin.yaml 스키마 ADR)
- [ ] P2-T5 템플릿 id 생성: tp.user.slug Templater 사용자 스크립트 제공 또는 init 렌더링 (ADR-0004 결과)
- [ ] P2-T6 add-domain (기존 파일 불변, ruamel round-trip)
- [ ] P2-T7 doctor 규칙 8종
- [ ] P2-T8 stats (§11.1 지표)
- [ ] P2-T9 fixtures: violations/ vault + init golden snapshot

## Blockers
- (없음)

## Decisions (→ ADR)
- ADR-0001: uv workspace 모노레포, core에만 도메인 로직, 미정의 Gate = FAIL
- ADR-0002: Guard는 모든 예외 → exit 2, Vault 루트에 cwd 사용 금지, exec 형식 Hook (명세 §7.2 보정 7건)
- ADR-0003: ruamel.yaml (YAML 1.2, safe, 중복 키 금지)
- ADR-0004: P1 스키마 보강 12건 (Domain label, accent 6종, Pack extra=forbid, taxonomy/interview 스키마 등)

## Backlog (Phase 범위 밖)
- phase-P0, phase-P1 태그 push — 세션 git 경로에서 태그 push 차단. Brian 로컬에서 push
- 조직별 Org Pack(예: 소속 회사용)은 별도 private 저장소에서 관리 (공개 저장소에는 Example Org만)
- Hub에서 Guard 차단 이벤트 표시 (P6)
- accent amber·slate 토큰 값 정의 (P5)
