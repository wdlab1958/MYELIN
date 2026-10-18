# PHASE_STATE
current_phase: P8
status: in_progress            # in_progress | gate_pending | awaiting_approval
last_updated: 2026-10-18 11:00 KST
approved: "GO P7 & P8" (Brian, 2026-10-18 10:15) — P7 종료 후 P8 연속 진행 승인

## Done
- P0 — Bootstrap: Gate PASS 29/29 (docs/reports/P0.md)
- P1 — Core Model & Domain Pack: Gate PASS 7/7 (docs/reports/P1.md)
- P2 — CLI Scaffolder: Gate PASS 7/7 (docs/reports/P2.md)
- P3 — Plugin + Guard: Gate PASS 8/8 (docs/reports/P3.md)
- P4 — MCP Server: Gate PASS 6/6 (docs/reports/P4.md)
- P5 — Emboss Design System: Gate PASS 8/8 (docs/reports/P5.md)
- P6 — MYELIN Hub: Gate PASS 10/10 (docs/reports/P6.md)
- P7 — Commons & Org Pilot: 자동 7/7 PASS · **사람 증거 2건 PEND** (파일럿 온보딩 결과, 피드백 리포트) — phase-P7 태그 보류 (docs/reports/P7.md)

## Next (P8 — 승인됨: "GO P7 & P8")
- [ ] P8-T1 scripts/gate.py 에 P8 Gate 검사 추가
- [ ] P8-T2 위협 모델(STRIDE) 문서와 조치 — High 0
- [ ] P8-T3 설치 스크립트 · 설치 가이드 (+ 설치→첫 verified 자동 측정)
- [ ] P8-T4 사용자 · 관리자 가이드
- [ ] P8-T5 상표 · 도메인 확인 (KIPRIS 제9류·제42류, GitHub org명) 결과 기록
- [ ] P8-T6 릴리스 노트 (알려진 제약) · v1.0.0
- [ ] P8-T7 회고

## Blockers
- (P7 완료 조건) §9.1 정책 3종 합의 · 파일럿 5명+ 실측 `docs/pilot/results.yaml` · `docs/pilot/feedback.md` (status: final) · Org Pack 2종 챔피언 확정 — 사람

## Decisions (→ ADR)
- ADR-0001: uv workspace 모노레포, core에만 도메인 로직, 미정의 Gate = FAIL
- ADR-0002: Guard는 모든 예외 → exit 2, Vault 루트에 cwd 사용 금지, exec 형식 Hook (명세 §7.2 보정 7건)
- ADR-0003: ruamel.yaml (YAML 1.2, safe, 중복 키 금지)
- ADR-0004: P1 스키마 보강 12건 (Domain label, accent 6종, Pack extra=forbid, taxonomy/interview 스키마 등)
- ADR-0005: myelin.yaml·lock 스키마, 파일 쓰기 규칙(노트 불변·round-trip·마커), 템플릿 id, Vault 위치 정책 (+P3 보정: doctor 범위)
- ADR-0006: MCP 서버 — SDK 2.x stdio, trigram 색인, 보호 노트 색인 제외, write_draft opt-in
- ADR-0007: Emboss 토큰 단일 원천, 명세 색 4건 대비 조정, 가드레일을 검사(contrast·lint)로
- ADR-0008: Hub localhost 전용·사용자 행위 없는 쓰기 0, Review Gate는 status·reviewed만 변경 + git commit, llm.route는 Hub에서 변경 불가
- ADR-0009: Commons(로컬 clone 브랜치 제안 → 별도 확인 push), 공개 자격 차단·비식별 자동 차단·사람 확인 5항목, opt-in 익명 지표(파일만)

## Backlog (Phase 범위 밖)
- phase-P0, phase-P1 태그 push — 세션 git 경로에서 태그 push 차단. Brian 로컬에서 push
- 조직별 Org Pack(예: 소속 회사용)은 별도 private 저장소에서 관리 (공개 저장소에는 Example Org만)
- Hub에서 Guard 차단 이벤트 표시 — Guard 이벤트 기록(로그) 설계 선행
- Hub 좁은 화면(< 1280px) 레이아웃
- 템플릿 id 식(tp.date.now "YYYYMMDD-HHmm-ssSSS")을 실제 Obsidian+Templater에서 확인 (docs/manual/P3-e2e.md #14)
- Obsidian에 Emboss 테마 적용 모습 확인 (Brian 수동)
- 다크 모드 토큰 (v1.0 이후)
- 휠 패키지에 packs 포함 (myelin_cli/_packs) — P8 패키징
