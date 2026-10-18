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

## Privacy model

**도구는 공개, 지식은 각자의 기기에.** 이 저장소에는 코드와 Pack 템플릿만 있습니다. 여러분의 노트는 여기에 올라오지 않습니다.

| 구분 | 무엇 | 어디에 |
|---|---|---|
| 공개 (이 저장소) | 코드, Domain Pack 템플릿, 명세 | GitHub |
| 개인 | Vault(노트), `myelin.yaml`, 색인 `.myelin/` | 각자의 PC·디바이스 |
| 선택적 공유 | 직접 공개 승인한 노트만 | 조직 내부 Git (Team Commons, opt-in) |

- **Local-first, 완전 로컬은 아닙니다.** Vault 파일은 로컬에 있지만, Claude에게 노트 정리를 맡기면
  그 노트 내용은 **여러분의 Claude 계정을 통해 Anthropic으로 전송되어 처리**됩니다.
  데이터 처리 정책은 각자 사용하는 Claude 플랜의 정책을 따릅니다.
- `classification: confidential` 노트와 `40_IP/` 는 로컬 LLM으로만 처리하도록 라우팅합니다 (`myelin.yaml` 의 `llm.route`).
- `myelin init` 은 **이 저장소(소스 폴더)나 다른 git 저장소 안에는 Vault를 만들지 않습니다** — fork에 개인 노트가 push되는 사고를 막기 위해서입니다.
- `myelin doctor` 는 Vault가 공개 코드 호스팅(GitHub 등)을 원격으로 둔 git 안에 있으면 경고합니다. Vault를 git으로 백업한다면 **비공개 저장소**를 쓰세요.
- Hub(P6)는 기본적으로 `localhost` 에서만 열리고, MCP 서버(P4)는 로컬 stdio로 동작합니다.

## Claude Code에서 쓰기

```
/plugin marketplace add wdlab1958/MYELIN
/plugin install myelin@myelin
```
Vault 폴더에서 Claude Code를 실행하고 `/myelin:ingest`, `/myelin:distill`, `/myelin:interview`, `/myelin:review` 등을 씁니다.
Claude가 쓸 수 있는 곳은 Vault의 `myelin.yaml` `level` 이 정하고, Vault 안 Guard Hook이 실제로 막습니다 — [plugin/README.md](plugin/README.md).

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
