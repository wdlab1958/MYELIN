# PHASE_STATE
current_phase: P9
status: in_progress            # in_progress | gate_pending | awaiting_approval
last_updated: 2026-10-18 12:05 KST
approved: "GO" — Desktop 기능 이식 (Brian, 2026-10-18 12:03)

## Done
- P0 — Bootstrap: Gate PASS 29/29 (docs/reports/P0.md)
- P1 — Core Model & Domain Pack: Gate PASS 7/7 (docs/reports/P1.md)
- P2 — CLI Scaffolder: Gate PASS 7/7 (docs/reports/P2.md)
- P3 — Plugin + Guard: Gate PASS 8/8 (docs/reports/P3.md)
- P4 — MCP Server: Gate PASS 6/6 (docs/reports/P4.md)
- P5 — Emboss Design System: Gate PASS 8/8 (docs/reports/P5.md)
- P6 — MYELIN Hub: Gate PASS 10/10 (docs/reports/P6.md)
- P7 — Commons & Org Pilot: 자동 7/7 PASS · **사람 증거 2건 PEND** (파일럿 온보딩 결과, 피드백 리포트) — phase-P7 태그 보류 (docs/reports/P7.md)
- P8 — Hardening & v1.0: 자동 6/6 PASS · 사람 증거 1건 PEND (상표) (docs/reports/P8.md)

## Next (P9 — Desktop 구현 기능 이식, v1.1)
- [x] P9-T1 scripts/gate.py 에 P9 Gate 검사 추가
- [ ] P9-T2 구조화 patch 형식(ADR-0010) — core 파서·적용 계획, /link 스킬 출력 계약 갱신
- [ ] P9-T3 Hub Review Gate에서 patch 미리보기·적용·반려 (사람 클릭 + git commit)
- [ ] P9-T4 개인 Pack → Org Pack 제안 (`myelin commons propose-pack`, 확인 + 비식별 + 브랜치)
- [ ] P9-T5 익명 지표 집계 (`myelin metrics aggregate`, 익명성 검사)
- [ ] P9-T6 install.sh 선택 설정: Obsidian 테마 복사, Claude Code 플러그인·MCP 등록 (opt-in 플래그)
- [ ] P9-T7 Gate · 보고서

## 사람 확인 대기 (v1.0.0 태그 조건)
- [ ] KIPRIS 제9·42류 검토 → docs/legal/trademark-check.md `reviewed_by`·`decision` → `make gate P=8` → tag phase-P8, v1.0.0
- [ ] §9.1 정책 3종 합의 → 파일럿 5명+ (docs/pilot/results.yaml, feedback.md) → `make gate P=7` → tag phase-P7
- [ ] 로컬에서 태그 push (phase-P0 … , v1.0.0)

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
- Claude Desktop 구현에만 있던 기능 검토·이식: Hub `_patches` 적용, pack-propose, metrics aggregate, install.sh 의 플러그인·MCP·테마 자동 설정 (docs/reports/compare-main-2026-10-18.md §4)
- phase-P0, phase-P1 태그 push — 세션 git 경로에서 태그 push 차단. Brian 로컬에서 push
- 조직별 Org Pack(예: 소속 회사용)은 별도 private 저장소에서 관리 (공개 저장소에는 Example Org만)
- Hub에서 Guard 차단 이벤트 표시 — Guard 이벤트 기록(로그) 설계 선행
- Hub 좁은 화면(< 1280px) 레이아웃
- 템플릿 id 식(tp.date.now "YYYYMMDD-HHmm-ssSSS")을 실제 Obsidian+Templater에서 확인 (docs/manual/P3-e2e.md #14)
- Obsidian에 Emboss 테마 적용 모습 확인 (Brian 수동)
- 다크 모드 토큰 (v1.0 이후)
- Vite 6+ · Tailwind 4 전환 (dev 의존성 경보, 위협 T6)
- Windows 기본 환경 검증 · 설치 스크립트
- 이름 결정에 따른 정리 (상표 출원 또는 마이그레이션)
- 레지스트리(PyPI) 배포 — 이름 결정 이후. v1.0은 git + lockfile 설치
