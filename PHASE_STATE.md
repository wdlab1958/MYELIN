# PHASE_STATE
current_phase: P2
status: awaiting_approval      # in_progress | gate_pending | awaiting_approval
last_updated: 2026-10-18 09:40 KST
approved: "GO P2" (Brian, 2026-10-18 08:26)
gate: P2 PASS (docs/reports/P2.md)

## Done
- P0 — Bootstrap: Gate PASS 29/29 (docs/reports/P0.md)
- P1 — Core Model & Domain Pack: Gate PASS 7/7 (docs/reports/P1.md)
- [x] P2-T1 scripts/gate.py 에 P2 Gate 검사 추가
- [x] P2-T2 Typer CLI: init / add-domain / doctor / stats / packs
- [x] P2-T3 init: 대화형(--interactive) + 비대화형, 3+1 Domain, Level, 비어 있지 않은 경로면 중단
- [x] P2-T4 렌더링: 폴더·MOC·템플릿·taxonomy.md·interviews.md·Vault CLAUDE.md·myelin.yaml·lock + ADR-0005
- [x] P2-T5 템플릿 id: tp.date.now("YYYYMMDD-HHmm-ssSSS") — 사용자 스크립트 불필요 (myelin.core 1.1.0)
- [x] P2-T6 add-domain: 노트 불변, myelin.yaml round-trip(주석·순서·들여쓰기 보존), CLAUDE.md 마커 구간만 갱신
- [x] P2-T7 doctor 8규칙 + location 규칙 (소스 안 = error, 다른 git·공개 원격 = warning)
- [x] P2-T8 stats (§11.1, --json)
- [x] P2-T9 fixtures: golden/brian (CLI 실행 결과), violations/ + expected (9건)
- [x] P2-T10 개인정보 보호: init 위치 거부, README "Privacy model" 절

## Next (P3 — "GO P3" 승인 후 시작)
- [ ] P3-T1 scripts/gate.py 에 P3 Gate 검사 추가, ADR-0002를 현행 Claude Code 문서와 재대조
- [ ] P3-T2 plugin/.claude-plugin/plugin.json (name: myelin)
- [ ] P3-T3 scripts/guard_write.py — 표준 라이브러리만, 모든 예외 → exit 2, Vault 루트 = MYELIN_VAULT → CLAUDE_PROJECT_DIR
- [ ] P3-T4 hooks/hooks.json — exec 형식, matcher Write|Edit|MultiEdit|NotebookEdit
- [ ] P3-T5 Guard 테스트: 허용/허용 외/Vault 밖/심볼릭 링크/../잘못된 JSON/필드 누락/루트 미지정
- [ ] P3-T6 Skills: ingest, distill, interview, link, compose, review, ip-scan
- [ ] P3-T7 Level 0~3 개방 로직 (myelin.yaml level)
- [ ] P3-T8 Vault용 .claude/settings.json 템플릿 (Bash 쓰기 deny) — init 렌더링에 포함
- [ ] P3-T9 fixture e2e: /ingest·/distill 결과물이 myelin doctor 통과

## Blockers
- (없음)

## Decisions (→ ADR)
- ADR-0001: uv workspace 모노레포, core에만 도메인 로직, 미정의 Gate = FAIL
- ADR-0002: Guard는 모든 예외 → exit 2, Vault 루트에 cwd 사용 금지, exec 형식 Hook (명세 §7.2 보정 7건)
- ADR-0003: ruamel.yaml (YAML 1.2, safe, 중복 키 금지)
- ADR-0004: P1 스키마 보강 12건 (Domain label, accent 6종, Pack extra=forbid, taxonomy/interview 스키마 등)
- ADR-0005: myelin.yaml·lock 스키마, 파일 쓰기 규칙(노트 불변·round-trip·마커), 템플릿 id, Vault 위치 정책

## Backlog (Phase 범위 밖)
- phase-P0, phase-P1 태그 push — 세션 git 경로에서 태그 push 차단. Brian 로컬에서 push
- 조직별 Org Pack(예: 소속 회사용)은 별도 private 저장소에서 관리 (공개 저장소에는 Example Org만)
- Hub에서 Guard 차단 이벤트 표시 (P6)
- accent amber·slate 토큰 값 정의 (P5)
- 템플릿 id 식(tp.date.now "YYYYMMDD-HHmm-ssSSS")을 실제 Obsidian+Templater에서 확인 (P5/P6 수동 점검)
- 휠 패키지에 packs 포함 (myelin_cli/_packs) — P8 패키징
