# PHASE_STATE
current_phase: P3
status: awaiting_approval      # in_progress | gate_pending | awaiting_approval
last_updated: 2026-10-18 09:50 KST
approved: "GO P3" (Brian, 2026-10-18 08:52)
gate: P3 PASS (docs/reports/P3.md)

## Done
- P0 — Bootstrap: Gate PASS 29/29 (docs/reports/P0.md)
- P1 — Core Model & Domain Pack: Gate PASS 7/7 (docs/reports/P1.md)
- P2 — CLI Scaffolder: Gate PASS 7/7 (docs/reports/P2.md)
- [x] P3-T1 ADR-0002 재대조 → Rev 2 (Hook 주 장치를 Vault settings로, 읽기 차단, Level별 허용, 다층 권한)
- [x] P3-T1b P3 Gate (claude plugin validate는 local-only — CI는 SKIP 표시)
- [x] P3-T2 plugin.json (myelin 0.1.0) + 저장소 루트 marketplace.json — claude plugin validate --strict 통과
- [x] P3-T3 Guard (myelin_core/resources/myelin_guard.py): 쓰기 Level 게이트 + 40_IP·confidential 읽기 차단
- [x] P3-T4 plugin hooks/hooks.json (보조 Guard — 비-Vault 경로는 통과)
- [x] P3-T5 Guard 테스트 (별도 프로세스 실행) + in-process 테스트 + 사본 일치 테스트
- [x] P3-T6 Skills 7종 (출력 계약 블록, 모두 disable-model-invocation)
- [x] P3-T7 Level 0~3 — Guard 허용 경로 + Skill 사전 점검, 최소 Level-1에서 차단 확인
- [x] P3-T8 init이 Vault .claude/settings.json(권한 + Hook) + Guard 사본 생성 → golden 갱신
- [x] P3-T9 Skill 출력 계약 e2e + docs/manual/P3-e2e.md (실제 Claude 수동 체크리스트 14항목)
- [x] (보정) doctor 범위: 50_Journal·80_Outputs·00_Inbox/clips 제외, Inbox raw capture 허용 — ADR-0005 보정

## Next (P4 — "GO P4" 승인 후 시작)
- [ ] P4-T1 scripts/gate.py 에 P4 Gate 검사 추가
- [ ] P4-T2 MCP Python SDK 도입, stdio 서버 골격 (ADR-0006: SDK·전송·보안 경계)
- [ ] P4-T3 SQLite FTS5 색인 (.myelin/index.db), 증분 갱신 — doctor 스캔 범위와 동일
- [ ] P4-T4 tools: search_notes, get_note, query_frontmatter, list_domains, vault_stats
- [ ] P4-T5 Guard와 같은 읽기 정책: 40_IP·confidential 은 결과에서 제외 (llm.route)
- [ ] P4-T6 write_draft — myelin.yaml 명시 허용 + Level·경로 규칙은 Guard 로직 재사용
- [ ] P4-T7 경로 이탈·심볼릭 링크 차단 테스트
- [ ] P4-T8 5,000 노트 fixture 생성기 + 성능 테스트 (search p95 < 300ms)
- [ ] P4-T9 Claude Desktop / Claude Code 연결 가이드

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
