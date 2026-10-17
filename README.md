# MYELIN — Personal Knowledge OS

> 쓸수록 빨라지는 나의 지식 신경망 · *Knowledge that fires faster.*

MYELIN은 **Obsidian Vault를 지식의 정본으로, Claude를 가공 엔진으로** 쓰는 개인 지식 운영체계입니다.
누구나 자기 업무·연구 Domain을 **Domain Pack(YAML)** 으로 설정하고, 매일의 경험을 재사용 가능한 지식으로 전환합니다.

MYELIN is a personal knowledge operating system that uses an Obsidian vault as the source of truth
and Claude as the processing engine. You declare your own domains as YAML **Domain Packs**,
and MYELIN turns daily experience into reusable, verified knowledge — with fail-closed guardrails
so AI drafts never overwrite what you have verified.

> **Status: P0 (Bootstrap) 완료 — 아직 사용 가능한 기능은 없습니다.**
> 구현은 Phase P0~P8로 진행 중이며, 진행 상황은 [`PHASE_STATE.md`](PHASE_STATE.md) 에서 볼 수 있습니다.
> *Early development: the repository skeleton is in place; features land phase by phase.*

## 핵심 원칙

- **Vault는 개인 소유** — 로컬 Markdown + YAML. 벤더 종속 없음, Git으로 버전 관리.
- **Fail-closed** — Claude의 쓰기는 지정된 초안 영역으로만. Claude Code Hook이 그 외 경로를 실제로 차단합니다.
- **HITL 승격** — AI 초안이 `verified` 가 되는 것은 사람의 승인으로만.
- **Domain은 데이터** — 새 Domain 추가에 코드 변경이 필요 없습니다.

## 구성 (예정)

| 경로 | 구성요소 | Phase |
|---|---|---|
| `packages/myelin-core` | 스키마 · 파서 · Pack 로더 · doctor · 색인 | P1 |
| `packages/myelin-cli` | `myelin` CLI (init / add-domain / doctor / stats) | P2 |
| `plugin/` | MYELIN for Claude Code (Skills + Fail-closed Guard) | P3 |
| `packages/myelin-mcp` | MYELIN MCP 서버 (읽기 전용 기본) | P4 |
| `design/`, `theme/` | Emboss 디자인 시스템 · Obsidian Theme | P5 |
| `packages/myelin-hub` | MYELIN Hub (FastAPI + React) | P6 |
| `packs/` | Domain Packs — core / reference / org(example) | P1, P7 |

## 문서

- 명세 (Rev 2.0 공개판): [`docs/spec/MYELIN_Rev2.0.md`](docs/spec/MYELIN_Rev2.0.md) · [docx](docs/spec/MYELIN_Rev2.0.docx)
- Phase 계획: [`docs/phases/`](docs/phases/) · 보고서: [`docs/reports/`](docs/reports/)
- 설계 결정: [`docs/adr/`](docs/adr/)

## 개발

Python 3.12+, [uv](https://docs.astral.sh/uv/) 필요.

```bash
git clone https://github.com/wdlab1958/MYELIN.git
cd MYELIN
uv sync          # 의존성 설치
make check       # lint + type + test
make gate P=0    # Phase Gate 판정
```

Claude Code로 개발에 참여할 때는 [`CLAUDE.md`](CLAUDE.md) 의 Session Protocol을 따릅니다.

## License

[Apache License 2.0](LICENSE) © 2026 Brian (이원대), WDLAB
