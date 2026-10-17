# MYELIN — Repository Rules for Claude Code

## Context
- 제품: MYELIN Personal Knowledge OS. 정본 명세: `docs/spec/MYELIN_Rev2.0.md`
- Owner: Brian (이원대). 응답·문서는 한국어, 코드·식별자·커밋 타입은 영어.
- 현재 상태는 항상 `PHASE_STATE.md` 가 정본이다. 기억이나 추측으로 진행 상태를 판단하지 않는다.

## Session Protocol
1. 세션 시작 시 `PHASE_STATE.md` → `docs/phases/P{current}.md` 순으로 읽는다.
2. 현재 Phase 범위 밖 작업은 하지 않는다. 필요하면 `PHASE_STATE.md` 의 Backlog에 기록한다.
3. Task 하나 = 검증 가능한 변경 하나. 테스트 작성 → 구현 → `make check` 통과 → `PHASE_STATE.md` 갱신 → commit.
4. Phase 종료: `make gate P=n` → `docs/reports/P{n}.md` 작성 → `git tag phase-P{n}` → **멈추고 승인 요청**.
5. Brian이 "GO P{n+1}" 이라고 하기 전에는 다음 Phase를 시작하지 않는다.
6. `PHASE_STATE.md` 의 `status` 가 `awaiting_approval` 이면 어떤 구현도 시작하지 않는다.

## Engineering Rules
- **Fail-closed**: 판단할 수 없는 입력은 거부한다. 사용자 데이터(Vault)를 덮어쓰지 않는다.
- 스키마 변경은 ADR 선행 (`docs/adr/NNNN-*.md`).
- Pack은 데이터다. Domain 추가에 코드 변경이 필요해지면 설계를 재검토하고 ADR을 쓴다.
- UI는 `design/tokens.json` 토큰만 사용한다. 색·그림자 하드코딩 금지.
- 테스트 없는 기능은 commit하지 않는다. Vault fixture는 `tests/fixtures/vaults/`.
- Python 3.12+, 타입 힌트 필수(`mypy --strict` 통과), `ruff` 통과.
- Claude Code Hook/Plugin 사양은 `docs/adr/0002-claude-code-plugin-spec.md` 를 따른다. 사양이 바뀌었다고 판단되면 ADR을 먼저 갱신한다.

## Commands
- `uv sync` — 의존성 설치
- `make check` — lint + type + test
- `make gate P=n` — Phase n의 Gate 판정 (`scripts/gate.py`)

## Commit
- 형식: `P{n}: <type>(<scope>): <summary>`  예) `P3: feat(guard): block symlink escape`
- type: feat | fix | test | docs | chore | refactor
