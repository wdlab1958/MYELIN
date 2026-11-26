# THIRD_PARTY_LICENSES — MYELIN

- 프로젝트 라이선스: **Apache-2.0** (`LICENSE`, `NOTICE` 참조)
- 생성일: 2026-11-26 · **법무 검토 전** (아래 표는 설치된 패키지 메타데이터를 옮긴 것이며 법률 검토를 거친 문서가 아니다)
- 범위: **직접 의존성만**. 전이 의존성은 `uv.lock` 과 `packages/myelin-hub/web/package-lock.json` 에 고정되어 있으며 이 문서에서 개별 검토하지 않았다.
- 방법
  - Python: 루트와 `packages/*/pyproject.toml` 의 `dependencies`, `[dependency-groups] dev`, `[build-system] requires` 를 목록으로 삼고, 저장소 `.venv` 에 설치된 배포판의 `importlib.metadata` (`License-Expression` → `License` → `Classifier: License ::`) 값을 읽었다.
  - JavaScript: `packages/myelin-hub/web/package.json` 의 `dependencies`, `devDependencies` 를 목록으로 삼고, `node_modules/<pkg>/package.json` 의 `version`, `license` 필드를 읽었다.
  - 메타데이터로 확인하지 못한 항목은 "미확인"으로 적었다.

## 1. Python — 런타임 (직접 의존성 6개)

| 패키지 | 설치 버전 | 라이선스 (메타데이터) | 쓰는 곳 |
|---|---|---|---|
| pydantic | 2.14.1 | MIT | myelin-core |
| ruamel.yaml | 0.19.1 | MIT | myelin-core |
| typer | 0.27.3 | MIT | myelin-cli |
| mcp | 2.3.0 | MIT | myelin-mcp |
| fastapi | 0.143.3 | MIT | myelin-hub-api |
| uvicorn | 0.54.0 | BSD-3-Clause | myelin-hub-api |

## 2. Python — 개발·빌드 (배포물에 포함되지 않음, 6개)

| 패키지 | 설치 버전 | 라이선스 (메타데이터) | 용도 |
|---|---|---|---|
| pytest | 9.1.1 | MIT | 테스트 |
| pytest-cov | 7.1.0 | MIT | 커버리지 |
| ruff | 0.17.1 | MIT | lint, format |
| mypy | 2.4.0 | MIT | 타입 검사 |
| httpx | 0.28.1 | BSD-3-Clause | Hub API 테스트 클라이언트 |
| hatchling (>=1.25) | 미확인 (`.venv` 에 설치되어 있지 않음, 빌드 시에만 내려받음) | 미확인 (메타데이터로 확인하지 못함) | wheel 빌드 백엔드 |

## 3. JavaScript — Hub 웹 런타임 (번들에 포함, 3개)

| 패키지 | 설치 버전 | 라이선스 (`package.json`) |
|---|---|---|
| react | 18.3.1 | MIT |
| react-dom | 18.3.1 | MIT |
| react-router-dom | 6.30.6 | MIT |

## 4. JavaScript — 개발·빌드 (9개)

| 패키지 | 설치 버전 | 라이선스 (`package.json`) |
|---|---|---|
| @playwright/test | 1.64.1 | Apache-2.0 |
| @types/react | 18.3.31 | MIT |
| @types/react-dom | 18.3.7 | MIT |
| @vitejs/plugin-react | 4.7.0 | MIT |
| autoprefixer | 10.6.1 | MIT |
| postcss | 8.5.30 | MIT |
| tailwindcss | 3.4.19 | MIT |
| typescript | 5.9.3 | Apache-2.0 |
| vite | 5.4.21 | MIT |

## 5. 패키지가 아닌 항목

| 항목 | 저장소에 포함되는가 | 라이선스 | 비고 |
|---|---|---|---|
| `formal/tools/`, `formal/ci/` 스크립트 | **포함** (사본) | MIT (WDLAB proof-skills v0.1.1 — 파일 머리말과 `formal/README.md` 표기) | 2026-11-16 에 복사 |
| TLA+ tools (`tla2tools.jar` v1.8.0), `CommunityModules-deps.jar` | 포함하지 않음. `formal/ci/setup_tla.sh` 가 내려받는다 | MIT (TLA+ 프로젝트 표기. 이 문서에서 jar 내부를 검증하지는 않았다) | 형식 검증 재실행 때만 필요 |
| Lean 4 툴체인 (`leanprover/lean4:v4.34.0`) | 포함하지 않음. elan 으로 설치 | Apache-2.0 (Lean 프로젝트 표기) | Lean 증명 재검사 때만 필요. Mathlib 은 쓰지 않는다 |
| Java 런타임 (OpenJDK 21) | 포함하지 않음 | GPL-2.0 with Classpath Exception | TLC 실행용 도구. 연결·재배포하지 않는다 |
| 글꼴 | **포함하지 않음** | 해당 없음 | `design/tokens.json` 은 글꼴 **이름**(Pretendard, Inter, JetBrains Mono, 시스템 글꼴)만 지정한다. 글꼴 파일(woff, ttf, otf)과 CDN 링크는 저장소에 없다. 사용자 PC 에 설치된 글꼴이 쓰인다 |
| 로컬 LLM 모델 (Hub 도움말 챗봇) | **포함하지 않음** | 미확인 (모델마다 다름) | `assistant.py` 는 사용자가 Ollama 에 설치한 모델 중 우선순위 목록(`exaone3.5:7.8b`, `qwen2.5:7b`, `qwen2.5:14b`, `qwen3:8b`, `gemma3:4b`, `exaone3.5:2.4b`, `qwen2.5:3b`, `llama3.2:3b`)에서 첫 모델을 고른다. 모델 라이선스 확인은 설치한 사용자의 책임이다 |
| Ollama | 포함하지 않음 | 미확인 (이 문서에서 확인하지 않음) | 사용자가 따로 설치 |
| Obsidian | 포함하지 않음 | 독점 소프트웨어 (자체 약관) | 사용자가 따로 설치. 상업적 이용 조건은 Obsidian 약관을 확인할 것 |
| `python-docx`, `openpyxl` | 포함하지 않음, 의존성으로 선언되지 않음 | 미확인 | `docs/guides/user-guide-v2.0/gen_guide.py` (가이드 문서 생성기)만 사용 |

## 6. 주의 필요

- **직접 의존성 24개(Python 12, JavaScript 12) 가운데 copyleft(GPL, LGPL, AGPL, MPL) 또는 비상업 조건 라이선스는 발견되지 않았다.** 확인된 23개는 MIT, BSD-3-Clause, Apache-2.0 이다.
- 미확인 1개: `hatchling` (빌드 백엔드, 배포물에 포함되지 않음).
- OpenJDK 는 GPL-2.0 with Classpath Exception 이지만 형식 검증 도구를 돌릴 때 쓰는 외부 런타임이며 MYELIN 과 함께 배포하지 않는다.
- 로컬 LLM 모델에는 비상업·사용 제한 조건이 붙은 것이 있다. 위 우선순위 목록의 모델별 조건은 **확인하지 않았다**. 업무에 쓰기 전에 모델별 라이선스를 확인해야 한다.
- Obsidian 은 오픈소스가 아니다. 회사 업무용 사용 조건은 Obsidian 약관을 따른다.
- 전이 의존성은 검토하지 않았다. 배포 전에 lock 파일 기준 전수 점검이 필요하다.
