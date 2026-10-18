# PHASE_STATE
current_phase: P4
status: awaiting_approval      # in_progress | gate_pending | awaiting_approval
last_updated: 2026-10-18 09:45 KST
approved: "GO P4" (Brian, 2026-10-18 09:12)
gate: P4 PASS (docs/reports/P4.md)

## Done
- P0 — Bootstrap: Gate PASS 29/29 (docs/reports/P0.md)
- P1 — Core Model & Domain Pack: Gate PASS 7/7 (docs/reports/P1.md)
- P2 — CLI Scaffolder: Gate PASS 7/7 (docs/reports/P2.md)
- P3 — Plugin + Guard: Gate PASS 8/8 (docs/reports/P3.md)
- [x] P4-T1 P4 Gate (tests, read-only default, 5k 성능, 가이드)
- [x] P4-T2 MCP SDK 2.x (MCPServer) stdio 서버 + ADR-0006
- [x] P4-T3 SQLite FTS5 trigram 색인 (.myelin/index.db), 증분 갱신(mtime·size), 정책 변경 시 재색인
- [x] P4-T4 tools: search_notes, get_note, query_frontmatter, list_domains, vault_stats
- [x] P4-T5 읽기 정책(core/policy.py) = Guard 판정 — 보호 노트는 색인 자체에서 제외
- [x] P4-T6 write_draft — mcp.write_drafts 일 때만 등록, Guard check() 재사용, 덮어쓰기 금지
- [x] P4-T7 경로 이탈·심볼릭 링크·비노트 경로 차단 테스트
- [x] P4-T8 bench_mcp.py — 5,000 노트 p95 ≈ 18ms
- [x] P4-T9 docs/guides/mcp.md (Claude Code / Claude Desktop)

## Next (P5 — "GO P5" 승인 후 시작)
- [ ] P5-T1 scripts/gate.py 에 P5 Gate 검사 추가
- [ ] P5-T2 design/tokens.json — 명세 §8.1 전 토큰 + accent 6종(amber·slate 값 정의)
- [ ] P5-T3 생성기: tokens → CSS 변수 · Tailwind preset · Obsidian theme.css (단일 원천)
- [ ] P5-T4 대비 검사 스크립트 (텍스트 4.5:1, 네온 위 텍스트는 --ink 만)
- [ ] P5-T5 컴포넌트 스펙 + 정적 갤러리 (Card, Buttons, Input, Nav, Chip, Orb, Review Row)
- [ ] P5-T6 lint: 하드코딩 색·그림자 금지
- [ ] P5-T7 theme/obsidian-myelin-emboss (manifest.json, theme.css)
- [ ] P5-T8 갤러리 스크린샷 → Brian 승인

## Blockers
- (없음)

## Decisions (→ ADR)
- ADR-0001: uv workspace 모노레포, core에만 도메인 로직, 미정의 Gate = FAIL
- ADR-0002: Guard는 모든 예외 → exit 2, Vault 루트에 cwd 사용 금지, exec 형식 Hook (명세 §7.2 보정 7건)
- ADR-0003: ruamel.yaml (YAML 1.2, safe, 중복 키 금지)
- ADR-0004: P1 스키마 보강 12건 (Domain label, accent 6종, Pack extra=forbid, taxonomy/interview 스키마 등)
- ADR-0005: myelin.yaml·lock 스키마, 파일 쓰기 규칙(노트 불변·round-trip·마커), 템플릿 id, Vault 위치 정책 (+P3 보정: doctor 범위)
- ADR-0006: MCP 서버 — SDK 2.x stdio, trigram 색인, 보호 노트 색인 제외, write_draft opt-in

## Backlog (Phase 범위 밖)
- phase-P0, phase-P1 태그 push — 세션 git 경로에서 태그 push 차단. Brian 로컬에서 push
- 조직별 Org Pack(예: 소속 회사용)은 별도 private 저장소에서 관리 (공개 저장소에는 Example Org만)
- Hub에서 Guard 차단 이벤트 표시 (P6)
- accent amber·slate 토큰 값 정의 (P5)
- 템플릿 id 식(tp.date.now "YYYYMMDD-HHmm-ssSSS")을 실제 Obsidian+Templater에서 확인 (P5/P6 수동 점검)
- 휠 패키지에 packs 포함 (myelin_cli/_packs) — P8 패키징
