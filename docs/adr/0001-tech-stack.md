# ADR-0001: 기술 스택과 저장소 구조

- 상태: Accepted
- 일자: 2026-10-18
- Phase: P0

## 맥락
MYELIN은 CLI·MCP 서버·Hub API가 같은 Vault 모델(스키마·파서·Pack 로더)을 공유한다.
1인 개발(Brian + Claude Code)이므로 언어·도구 수를 최소화해야 하고, 세션 간 연속 작업을 위해
상태와 검증이 저장소 안에서 결정론적으로 판정되어야 한다.

## 결정
- **모노레포 + uv workspace.** `packages/` 아래 4개 Python 패키지, 단일 lock 파일.
  - `myelin-core` 에만 도메인 로직을 둔다. CLI·MCP·Hub API는 얇은 어댑터.
- **Python 3.12+**, Pydantic v2(P1부터), Typer(P2), MCP Python SDK(P4), FastAPI(P6).
- **품질 도구:** ruff(lint+format), mypy `--strict`, pytest(`--import-mode=importlib`).
- **Hub 프런트엔드:** React 18 + Vite + TypeScript + Tailwind, Emboss 토큰 preset만 사용 (P5·P6).
- **색인:** SQLite FTS5, Vault 외부 `.myelin/` (P4).
- **Gate:** `make gate P=n` = `make check` + `scripts/gate.py`.
  정의되지 않은 Phase의 Gate는 실패로 판정한다 (fail-closed). 각 Phase는 착수 시 자기 Gate를 먼저 추가한다.
- **상태 인계:** `PHASE_STATE.md` 가 진행 상태의 정본.

## 결과
- 세션이 끊겨도 `PHASE_STATE.md` + Gate로 진행 상태를 복원할 수 있다.
- Node 툴체인은 P5·P6에서만 추가된다. 그 전까지 CI는 Python만 필요하다.
- 패키지 의존성은 각 Phase에서 실제로 필요해질 때 추가한다 (P0는 의존성 0).
