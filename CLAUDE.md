# MYELIN — Repository Rules for Claude Code

## Context
- 제품: MYELIN Personal Knowledge OS. 정본 명세: `docs/spec/MYELIN_Rev2.0.md` (WDLAB-MYELIN-SPEC Rev 2.0, 2026-10-18).
- Owner: Brian (이원대). 응답·문서는 한국어, 코드·식별자는 영어.
- 저장소 구조: 정본 §10.1 (Monorepo). Phase 계획: §10.3, `docs/phases/P0~P8.md`.

## Session Protocol
1. 시작 시 `PHASE_STATE.md` → `docs/phases/P{current}.md` 를 읽고, 남은 Task를 Task 목록으로 복원한다.
2. 현재 Phase 범위 밖 작업은 하지 않는다. 필요하면 PHASE_STATE의 Backlog에 기록.
3. Task 완료마다: 테스트 → PHASE_STATE 갱신 → commit.
4. Phase 종료: `make gate P=n` → `docs/reports/P{n}.md` 작성 → `git tag phase-P{n}` → **멈추고 승인 요청**.
5. 다음 Phase는 Brian이 "GO P{n+1}" 을 줄 때만 시작한다. 승인 없이 다음 Phase 착수 금지.
6. 되돌리기 어려운 설계 결정은 `docs/adr/NNNN-*.md` 로 기록한다 (ADR 선행).

## Engineering Rules
- Fail-closed: 판단 불가 입력은 거부. 사용자 데이터 덮어쓰기 금지 (`myelin init` 은 기존 Vault를 덮어쓰지 않는다).
- 스키마 변경은 ADR 선행. Pack은 데이터이므로 Domain 추가에 코드 변경이 필요하면 설계 재검토 (Thin Additive Routing Shell).
- UI는 `design/tokens.json` 토큰만 사용. 색 하드코딩 금지.
- 테스트 없는 기능 merge 금지. fixtures는 `tests/fixtures/vaults`.
- Python 3.12 · uv workspace · Pydantic v2 · Typer · ruamel.yaml · pytest · ruff · mypy(strict). 단일 `myelin-core` 를 CLI·MCP·Hub가 공유한다.
- Hook 스크립트(`plugin/hooks/*.py`)는 표준 라이브러리만 사용한다.
- 비밀·고객 데이터·개인 Vault 내용을 저장소에 커밋하지 않는다. fixtures는 합성 데이터만.

## Commands
- `make test` — 전체 테스트 · `make lint` — ruff · `make typecheck` — mypy · `make gate P=<n>` — Phase Gate · `make phases` — 정본에서 docs/phases 재생성

## Commit
- 형식: `P{n}: <type>(<scope>): <summary>` 예) `P3: feat(guard): block symlink escape`
- type: feat · fix · test · docs · chore · refactor · ci
- AI가 생성한 Vault 커밋(제품 런타임)은 `[myelin:<skill>]` 접두사 (정본 §3) — 저장소 커밋 규칙과 구별한다.
