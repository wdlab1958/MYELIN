# ADR-0001: 기술 스택

- 상태: Accepted · 일자: 2026-10-18 · Phase: P0
- 근거 문서: `docs/spec/MYELIN_Rev2.0.md` §4.4 기술 스택, §10.1 저장소 구조

## 맥락

MYELIN은 하나의 코어 라이브러리(스키마·파서·Pack 로더·doctor·색인)를 CLI·MCP 서버·Hub API가 공유해야 한다(§4.4 "단일 core 라이브러리를 CLI·MCP·Hub가 공유"). Domain은 코드가 아닌 YAML Pack이며(§3 Thin Additive Routing Shell), Hook 스크립트는 Claude Code가 외부 의존성 없이 실행해야 한다.

## 결정

| 영역 | 선택 | 비고 |
|---|---|---|
| 언어/런타임 | Python 3.12 | Hook·CLI·MCP·API 단일 언어 |
| 패키지 관리 | **uv workspace** (`pyproject.toml` 루트, members = `packages/*`) | 루트는 `package = false`, 각 멤버는 hatchling 빌드 |
| 모델/검증 | Pydantic v2 | Frontmatter v2(§6.2)·Pack(§5.2)·myelin.yaml(§5.3) 모델 + JSON Schema export |
| YAML | ruamel.yaml | 주석·키 순서 보존(Vault 파일을 사람이 함께 편집) |
| CLI | Typer | `myelin init/add-domain/doctor/stats` |
| 색인 | SQLite FTS5 (`<Vault>/.myelin/index.db`, git ignore) | 선택적 로컬 임베딩은 P4 이후 |
| MCP | MCP Python SDK, stdio | Vault 루트 밖 접근 차단 |
| Plugin | Claude Code Plugin (skills/commands/hooks) | Hook은 **표준 라이브러리만** (ADR-0002) |
| Hub | FastAPI + React 18 · Vite · TypeScript · Tailwind(Emboss preset) | localhost 기본, 인증은 Team 모드 |
| Theme | Obsidian CSS Theme, `design/tokens.json`에서 생성 | 토큰 단일 원천, 색 하드코딩 금지 |
| 품질 | ruff(lint+format) · mypy `--strict` · pytest(+cov) | `make check`, CI GitHub Actions |
| Gate | `scripts/gate.py` (`make gate P=n`) | Phase별 체크 선언; 미구현 Phase는 fail-closed로 FAIL |

## 대안과 기각 이유

- **Poetry / pip-tools 멀티 레포**: 4개 패키지의 교차 의존을 로컬에서 editable로 묶는 비용이 크다. uv workspace가 단일 lock으로 해결.
- **Node 단일 스택(Hub와 통일)**: Hook·MCP·CLI가 Python 생태계(Pydantic·ruamel)에 더 적합하고, Brian의 기존 AgentForge 계열과 연계(§4.3 Offline)가 Python이다. Hub web만 TS.
- **TOML/JSON Pack**: YAML이 주석·멀티라인(인터뷰 질문 은행)에 유리하고 Obsidian frontmatter와 동일 문법.

## 결과

- 저장소 루트 `pyproject.toml`에 ruff/mypy/pytest 설정을 집중한다. 패키지별 설정 분산 금지.
- Hub web(P6)은 별도 `package.json`을 갖되, 색/그림자/반경은 P5 생성물(Tailwind preset)만 import한다.
- 스키마 변경·필드 추가는 ADR 선행(CLAUDE.md).
