# PHASE_STATE
current_phase: P5
status: awaiting_approval      # in_progress | gate_pending | awaiting_approval
last_updated: 2026-10-18 09:50 KST
approved: "GO P5" (Brian, 2026-10-18 09:22)
gate: P5 PASS (docs/reports/P5.md) — 갤러리 디자인은 Brian 승인 대기

## Done
- P0 — Bootstrap: Gate PASS 29/29 (docs/reports/P0.md)
- P1 — Core Model & Domain Pack: Gate PASS 7/7 (docs/reports/P1.md)
- P2 — CLI Scaffolder: Gate PASS 7/7 (docs/reports/P2.md)
- P3 — Plugin + Guard: Gate PASS 8/8 (docs/reports/P3.md)
- P4 — MCP Server: Gate PASS 6/6 (docs/reports/P4.md)
- [x] P5-T1 P5 Gate (산출물 최신·대비·lint·테스트·테마·스크린샷 해시)
- [x] P5-T2 design/tokens.json — 명세 값 4건 대비 미달 → 조정 (ADR-0007), accent 6종 완성
- [x] P5-T3 design/build.py — tokens → tokens.css · resolved.json · tailwind.preset.js · Obsidian theme.css
- [x] P5-T4 --contrast: 텍스트 18쌍 ≥ 4.5:1, 네온 5종 텍스트 금지 보고
- [x] P5-T5 components.css + gallery/index.html (Card·KPI·Button·Input·Nav·Chip·Orb·Review Row)
- [x] P5-T6 --lint: 색 리터럴·네온 글자색 금지 (design/src, gallery, Hub web/src)
- [x] P5-T7 theme/obsidian-myelin-emboss (manifest + theme.css, 라이트 전용) + 설치 안내
- [x] P5-T8 갤러리 스크린샷 (Playwright) → docs/reports/P5/gallery.png — **Brian 승인 대기**

## Next (P6 — "GO P6" 승인 후 시작)
- [ ] P6-T1 scripts/gate.py 에 P6 Gate 검사 추가
- [ ] P6-T2 Hub API (FastAPI, 127.0.0.1 바인딩, core·index 재사용) + ADR-0008
- [ ] P6-T3 API: stats, domains, inbox/drafts, promote/reject(→ git commit), packs
- [ ] P6-T4 web: Vite + React + TS + Tailwind(Emboss preset) — 색은 토큰만 (lint)
- [ ] P6-T5 화면: Dashboard, My Domains, Inbox/Review Gate, Domain Packs, Settings
- [ ] P6-T6 온보딩 마법사 (CLI init 로직 재사용)
- [ ] P6-T7 Playwright e2e: 온보딩 → 첫 노트 verified 승격, 승격 시 git commit
- [ ] P6-T8 사용자 행위 없는 Vault 쓰기 0 검증, 화면별 스크린샷

## Blockers
- (없음)

## Decisions (→ ADR)
- ADR-0001: uv workspace 모노레포, core에만 도메인 로직, 미정의 Gate = FAIL
- ADR-0002: Guard는 모든 예외 → exit 2, Vault 루트에 cwd 사용 금지, exec 형식 Hook (명세 §7.2 보정 7건)
- ADR-0003: ruamel.yaml (YAML 1.2, safe, 중복 키 금지)
- ADR-0004: P1 스키마 보강 12건 (Domain label, accent 6종, Pack extra=forbid, taxonomy/interview 스키마 등)
- ADR-0005: myelin.yaml·lock 스키마, 파일 쓰기 규칙(노트 불변·round-trip·마커), 템플릿 id, Vault 위치 정책 (+P3 보정: doctor 범위)
- ADR-0006: MCP 서버 — SDK 2.x stdio, trigram 색인, 보호 노트 색인 제외, write_draft opt-in
- ADR-0007: Emboss 토큰 단일 원천, 명세 색 4건 대비 조정, 가드레일을 검사(contrast·lint)로

## Backlog (Phase 범위 밖)
- phase-P0, phase-P1 태그 push — 세션 git 경로에서 태그 push 차단. Brian 로컬에서 push
- 조직별 Org Pack(예: 소속 회사용)은 별도 private 저장소에서 관리 (공개 저장소에는 Example Org만)
- Hub에서 Guard 차단 이벤트 표시 (P6)
- 템플릿 id 식(tp.date.now "YYYYMMDD-HHmm-ssSSS")을 실제 Obsidian+Templater에서 확인 (docs/manual/P3-e2e.md #14)
- Obsidian에 Emboss 테마 적용 모습 확인 (Brian 수동)
- 다크 모드 토큰 (v1.0 이후)
- 휠 패키지에 packs 포함 (myelin_cli/_packs) — P8 패키징
