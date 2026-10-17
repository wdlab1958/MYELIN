# PHASE_STATE
current_phase: P1
status: in_progress            # in_progress | gate_pending | awaiting_approval
last_updated: 2026-10-18 08:40 KST
approved: "GO P1" (Brian, 2026-10-18 08:06)

## Done
- P0 — Bootstrap: Gate PASS 29/29 (docs/reports/P0.md)
- [x] P1-T1 scripts/gate.py 에 P1 Gate 검사 추가 (검사 중 예외 = FAIL)
- [x] P1-T2 pydantic, ruamel.yaml 도입 + ADR-0003
- [x] P1-T3 Frontmatter 모델 (§6.2) — extra 필드 보존, share+confidential 정책 검사, id 불변 검사
- [x] P1-T4 Note 파서 — wikilink(alias/heading/embed), 코드 블록 무시, 구조화 오류

## Next
- [ ] P1-T5 Pack / Domain 모델 (§5.2)
- [ ] P1-T6 Pack 로더 (의존성 해석, 순환·ID 충돌 감지)
- [ ] P1-T7 JSON Schema export
- [ ] P1-T8 packs/myelin.core
- [ ] P1-T9 packs/brian.physical-ai
- [ ] P1-T10 packs/org.security-consulting 초안
- [ ] P1-T11 fixtures: minimal vault 30+ 노트, 잘못된 Pack 10종

## Blockers
- (없음)

## Decisions (→ ADR)
- ADR-0001: uv workspace 모노레포, core에만 도메인 로직, 미정의 Gate = FAIL
- ADR-0002: Guard는 모든 예외 → exit 2, Vault 루트에 cwd 사용 금지, exec 형식 Hook (명세 §7.2 보정 7건)
- ADR-0003: ruamel.yaml (YAML 1.2, safe, 중복 키 금지)

## Backlog (Phase 범위 밖)
- phase-P0 태그 push — Brian 로컬에서 `git fetch origin && git tag -a phase-P0 2883bf2 -m "P0 Bootstrap" && git push origin phase-P0`
- 조직별 Org Pack(예: 소속 회사용)은 별도 private 저장소에서 관리 (공개 저장소에는 Example Org만)
- Hub에서 Guard 차단 이벤트 표시 (P6)
