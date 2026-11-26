# 설치 · 운영 가이드 — 사내(on-premise) · 망분리

> 기준: v1.4.0 (2026-11-26). MYELIN 은 고객에게 파는 상품이 아니라 One Cycle Dev. Framework 의 정보 자산을 개발자·운영자가 관리하는 개인 지식 관리 서비스다. 개인 PC 한 대에 설치하는 로컬 도구이며 서버·DB·컨테이너가 없다.
> 빠른 시작은 [README §3](../README.md), 관리자용 요약은 [`guides/admin-guide.md`](guides/admin-guide.md).

## 1. 사전 요구 사항

| 항목 | 버전 | 용도 |
|---|---|---|
| OS | Linux (Ubuntu 24.04 에서 개발·시험). macOS 는 시험하지 않았다. Windows 는 미지원(hook·권한 검사가 POSIX 기준) | |
| Python | 3.12 (asyncio 가 정상 동작하는 배포판 CPython — `scripts/install.sh` 가 자가 검사) | core · CLI · MCP · Hub API |
| [uv](https://docs.astral.sh/uv/) | 0.9 이상 (0.9.16 에서 확인) | 의존성 설치 |
| git | 2.40 이상 (2.43 에서 확인) | Vault 이력, pre-commit 장치 |
| Node.js | 22 (22.23 에서 확인) | Hub 웹 UI 빌드에만 필요. 빌드된 `dist/` 를 옮기면 대상 PC 에는 불필요 |
| Obsidian | 선택 (`scripts/install_obsidian.sh`, Debian/Ubuntu) | Vault 편집기 — 별도 라이선스(THIRD_PARTY_LICENSES.md) |
| Claude Code | 2.1.295 이상, 선택 (`--claude`) | Skill(`/myelin:*`)·MCP. **외부 LLM 세션이다** — §4 |
| Ollama | 선택 | Hub 도우미 챗봇(로컬). 없으면 내장 지식 모드로 동작 |
| Java 21 · tla2tools · Lean 4.34 | 선택 | `formal/` 재검증에만 필요 |

**하드웨어** — 별도 측정값은 없다. 개발 PC(일반 노트북급)에서 동작하며, 확인된 수치는 색인 검색 벤치 하나다: 5,000 노트 fixture 에서 검색 p95 < 300 ms(`make perf`, P4 Gate). 디스크는 저장소 + `.venv` + `node_modules` 로 약 1 GB 를 잡는다(측정값 아님). 로컬 LLM(Ollama)을 쓰면 그 모델의 요구 사양이 따로 든다.

## 2. 설치 (인터넷 연결 PC)

```bash
git clone <저장소> myelin && cd myelin
scripts/install.sh --vault ~/Vaults/me            # uv sync → Hub 빌드 → 런처(~/.local/bin) → Obsidian 테마
myelin-hub --vault ~/Vaults/me                    # http://127.0.0.1:8787 → 온보딩 마법사
```
`--claude` 를 주면 Claude Code plugin·MCP 를 등록한다(opt-in). `--dry-run` 으로 할 일만 볼 수 있다. 설치는 멱등이며 사용자 파일을 덮어쓰지 않는다.

## 3. 망분리(air-gapped) 설치

설치 스크립트의 `uv sync` 와 `npm install` 은 인터넷이 필요하다. 망분리 PC 에는 **연결된 PC 에서 준비한 묶음**을 옮긴다. 아래 절차는 표준 도구 사용법에 따른 것이며, **이 저장소에서 실제 망분리 PC 로 수행해 검증하지는 않았다** — 처음 적용할 때 시험 PC 에서 먼저 확인한다.

연결된 PC(대상과 같은 OS·CPU·Python 3.12):
```bash
git clone <저장소> myelin && cd myelin
uv export --all-packages --frozen --no-emit-workspace --no-hashes --format requirements-txt -o requirements-offline.txt
python3.12 -m pip download -r requirements-offline.txt hatchling editables -d wheelhouse/
make web                                   # packages/myelin-hub/web/dist 생성 (Node 는 여기서만 필요)
tar czf ../myelin-offline.tgz --exclude=.venv --exclude=node_modules .
```
망분리 PC:
```bash
mkdir myelin && tar xzf myelin-offline.tgz -C myelin && cd myelin
python3.12 -m venv .venv
.venv/bin/pip install --no-index --find-links wheelhouse/ -r requirements-offline.txt
.venv/bin/pip install --no-index --find-links wheelhouse/ --no-deps \
    -e packages/myelin-core -e packages/myelin-cli -e packages/myelin-mcp -e packages/myelin-hub/api
.venv/bin/myelin --version && .venv/bin/myelin-hub --vault ~/Vaults/me
```
- `uv export` 줄은 이 저장소에서 실행해 확인했다(개발 의존성 포함 목록이 나온다). 그 뒤의 `pip download` → 오프라인 `pip install` 은 실행해 보지 않았다.
- editable 설치에는 빌드 백엔드 `hatchling`(+`editables`)이 wheelhouse 에 있어야 한다(위 명령에 포함).
- 망분리 환경에서는 Claude Code(외부 LLM)를 쓸 수 없으므로 Skill·MCP 없이 **CLI + Hub + Obsidian** 으로 쓴다. 다른 플랫폼의 결과는 파일로 받는다([`onecycle/HANDOFF.md`](onecycle/HANDOFF.md)).
- Hub 도우미는 로컬 Ollama 가 없으면 내장 지식 모드로 답한다(외부 통신 없음).

## 4. 비밀값 · 첫 실행 · 데이터 경로

- **기본 계정·기본 비밀번호·내장 키가 없다.** Personal 모드는 loopback 전용·무인증이다(같은 PC 의 다른 로그인 사용자는 접근할 수 있으므로 공유 호스트에서 띄우지 않는다).
- 첫 실행은 Hub 온보딩 마법사 또는 `myelin init` 이다. 기존 Vault 는 덮어쓰지 않는다.
- **외부로 나가는 것** — Claude Code 세션을 쓸 때 비기밀 노트 내용. `classification: confidential` 과 `40_IP/**` 는 `MYELIN_LLM=local` 세션에서만 읽힌다(ADR-0011). 고객 식별 정보·고객 코드·자격증명은 **기록 자체를 하지 않는다** — [`guides/knowledge-management-policy.md`](guides/knowledge-management-policy.md), 프로젝트 시작 시 고객명 목록을 `<Vault>/.myelin/customer-names.txt` 에 등록.
- **Team 모드(선택, ADR-0016)** — 팀이 검토 대기열을 함께 볼 때만:
  ```bash
  myelin-hub --new-token alice --role write        # 토큰은 한 번만 출력된다. 서버에는 SHA-256 만 둔다
  install -m 600 /dev/null ~/.config/myelin/team-auth.yaml   # 권한 600 이 아니면 기동 거부
  # team-auth.yaml:
  #   allowed_hosts: [hub.team.example]
  #   users:
  #     - { name: alice, role: write, token_sha256: <위 출력> }
  myelin-hub --vault ~/Vaults/me --host 0.0.0.0 --auth-file ~/.config/myelin/team-auth.yaml \
             --tls-cert hub.crt --tls-key hub.key
  ```
  인증 파일·`allowed_hosts`·TLS(또는 `--behind-tls-proxy`) 중 하나라도 없으면 비-loopback 주소에 바인딩하지 않는다. 기밀 노트는 Team 채널로 나가지 않고, 접근 기록은 `<Vault>/.myelin/hub-access.log` 에 남는다. 토큰 폐기는 파일에서 줄을 지우면 다음 요청부터 적용된다.

## 5. 백업 · 복구

상태는 두 곳뿐이다.

| 대상 | 내용 | 백업 |
|---|---|---|
| **Vault 폴더** (`~/Vaults/<이름>`) | 노트(Markdown)·`myelin.yaml`·`.git` 이력·개인 Pack | 폴더 통째로 복사(또는 `git bundle create vault.bundle --all`). Vault 는 원격으로 push 하지 않는다(ADR-0014) — 백업은 사내 암호화 저장소에 |
| `<Vault>/.myelin/` | 색인 `index.db`(재생성 가능), `guard.log`, `hub-access.log`, `customer-names.txt`, 지표 이벤트 | git 에 들어가지 않는다. `customer-names.txt` 와 로그가 필요하면 따로 복사 |

복구: 폴더를 되돌려 놓고 `myelin doctor --vault <v>` 로 확인한다. `index.db` 는 지워도 다음 실행에서 다시 만든다. pre-commit 장치가 빠졌으면 `myelin doctor --install-hook`.
저장소(코드) 쪽에는 보존할 상태가 없다 — 다시 clone 하고 설치하면 된다.

## 6. 업그레이드 · 마이그레이션

```bash
git pull && scripts/install.sh --vault <v>     # 멱등. 테마는 .bak 백업 후 갱신
myelin doctor --vault <v>
```
- v1.3.x → **v1.4.0**: Vault 포맷(Frontmatter v2, `myelin.yaml`) 변경 없음 — 마이그레이션 불필요. 색인은 변경 감지 기준이 바뀌어 첫 실행에서 일부 노트를 한 번 다시 읽는다(자동).
- 동작이 달라지는 점: ① `myelin add-domain`·`myelin obsidian setup` 은 자기가 바꾼 파일만 커밋한다(작업 트리의 다른 변경은 그대로 남는다). ② 자격증명·주민번호·등록된 고객명이 든 초안은 승격·커밋이 거부된다. 긴 코드 블록·IP 가 든 초안은 승격 때 확인을 한 번 더 묻는다. ③ 실행 중인 MCP 서버가 `myelin.yaml` 변경(권한 철회)을 다음 호출부터 반영한다.
- 실행 중인 Hub·MCP 서버는 자동으로 새 코드를 읽지 않는다 — 재시작해야 적용된다. Hub 웹 UI 는 `make web` 으로 다시 빌드한다.
- 버전의 단일 원천은 `packages/myelin-core/src/myelin_core/_version.py` 이며 `scripts/sync_version.py --check` 로 나머지 표기를 검사한다. Claude Code plugin 은 별도 버전(`plugin/.claude-plugin/plugin.json`)이다.

## 7. 설치 확인

```bash
myelin --version                 # myelin 1.4.0
myelin doctor --vault <v>        # 0 errors
myelin guard scan --vault <v>    # 0 blocked
curl -s http://127.0.0.1:8787/api/health
```
