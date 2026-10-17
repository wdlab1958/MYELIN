# MYELIN — Personal Knowledge OS

> 쓸수록 빨라지는 나의 지식 신경망 · *Knowledge that fires faster.*

Obsidian + Claude 기반 개인 지식 운영체계. 정본 명세: [`docs/spec/MYELIN_Rev2.0.md`](docs/spec/MYELIN_Rev2.0.md) (WDLAB-MYELIN-SPEC Rev 2.0).

| 구성 | 경로 | Phase |
|---|---|---|
| myelin-core (스키마·파서·Pack 로더·doctor·색인) | `packages/myelin-core` | P1, P4 |
| MYELIN CLI (`myelin init/add-domain/doctor/stats`) | `packages/myelin-cli` | P2 |
| MYELIN for Claude Code (Plugin + Fail-closed Guard) | `plugin/` | P3 |
| MYELIN MCP | `packages/myelin-mcp` | P4 |
| MYELIN Emboss (tokens → CSS/Tailwind/Obsidian theme) | `design/`, `theme/` | P5 |
| MYELIN Hub (FastAPI + React) | `packages/myelin-hub/{api,web}` | P6 |
| MYELIN Packs | `packs/` | P1, P7 |

## 개발

```bash
make sync        # uv sync
make check       # lint + typecheck + test
make gate P=0    # Phase gate
```

작업 규칙: [`CLAUDE.md`](CLAUDE.md) · 진행 상태: [`PHASE_STATE.md`](PHASE_STATE.md) · Phase 계획: [`docs/phases/`](docs/phases/)
