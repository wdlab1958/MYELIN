# ADR-0011: 기밀 라우팅 장치화 — 외부 LLM 세션의 40_IP/confidential 접근 차단과 Vault 커밋 승인 장치

- 상태: Accepted · 일자: 2026-10-18 · Phase: P9 (v1.1)
- 근거: 정본 §3 "AI drafts, humans promote — 장치로 강제한다", §4.3 Offline/`llm.route`, §5.3 `llm.route: {confidential: local, "40_IP/**": local}`, §7.1 /ip-scan "로컬 LLM 라우팅", §12 "기밀 유출 → LLM 라우팅"; ADR-0002 D4~D6; ADR-0005; ADR-0007 §3; QA 격차 보고 H3(`docs/reports/QA/gap-report-2026-10-18.md`)
- 관련 파일: `plugin/hooks/guard_read.py` · `guard_common.py` · `guard_bash.py` · `hooks.json` · `myelin_core/settings_template.py` · `myelin_core/scaffold.py`(`install_git_hook`, `90_System/hooks/pre-commit`) · `myelin_core/doctor.py`(`run_doctor_staged`) · `myelin_cli/app.py`(`doctor --staged | --install-hook`) · `myelin_mcp/service.py` · `myelin_mcp/server.py`

## 맥락

정본은 "기밀은 외부 LLM 에 보내지 않는다" 를 `llm.route` 로 선언하지만, v1.0 까지 이 설정은 Vault `CLAUDE.md` 에 한 문장으로 렌더링될 뿐 어디에서도 집행되지 않았다. 외부 Claude Code 세션은 `Read`/`Grep`/`Glob`/Bash 로 `40_IP/**` 와 `classification: confidential` 노트를 자유롭게 읽을 수 있었고, Level 3 Vault 에서는 `40_IP/candidates` 에 쓸 수도 있었다(`LEVEL_ALLOW[3]`). `/ip-scan` SKILL.md 의 "로컬 세션이 아니면 멈춘다" 는 규칙(소프트 가드)이었다. 또 Guard 는 Claude Code 안에만 존재하므로, Obsidian Git·터미널·다른 에이전트가 Vault 에 커밋하면 "AI 초안은 사람이 승격한다" 는 원칙이 장치 없이 규칙으로만 남았다.

MCP(ADR-0007 §3)는 `mcp.expose_confidential: true` 를 "로컬 LLM 세션에서만 켜라" 는 가이드로 처리했다 — 역시 규칙이다.

## 결정

### 1. 세션 판정 — LOCAL / EXTERNAL

- 세션(또는 MCP 서버 프로세스)은 환경 변수 **`MYELIN_LLM=local`** 이 정확히 그 값으로 설정되어 있을 때만 **LOCAL** 이다. 그 외(미설정·빈 값·`Local`·`LOCAL`·`local `·`true`)는 모두 **EXTERNAL** 이다(fail-closed: 판정 불가 = 외부).
- 이 변수는 **운영자(사람)가 로컬 모델에 연결된 에이전트를 기동할 때** 설정한다. Vault 안의 파일(`myelin.yaml`·`CLAUDE.md`)이나 AI 가 쓸 수 있는 어떤 경로도 세션 판정에 영향을 주지 않는다 — AI 가 스스로를 LOCAL 로 승격할 수 없게 하기 위함이다.
- 단일 정의: `myelin_core.levels.LLM_ENV / LLM_LOCAL / is_local_session()`. Guard 는 표준 라이브러리만 쓰므로 `guard_common.py` 가 복사본을 두고 `tests/plugin/test_guard_sync.py::test_llm_routing_constants_in_sync` 가 동기화를 고정한다.

### 2. EXTERNAL 세션의 금지 행위 (Guard, 하드 차단)

EXTERNAL 세션에서 다음은 **exit 2 + 한국어 사유** 로 차단된다(ADR-0002 D3).

| 도구 | 차단 조건 | 구현 |
|---|---|---|
| Read | `file_path` 가 symlink 해소 후 `<Vault>/40_IP/` 안이거나(40_IP 자체 포함, 미존재 파일 포함), `.md` 이면서 첫 `---` 블록의 최상위 `classification:` 이 `confidential` 인 노트 | `guard_read.py` → `check_read_target` |
| Grep · Glob | `path` 가 `40_IP/` 안 · `path` 가 Vault 루트/조상 디렉터리 또는 **생략(→ cwd)** 이면서 `40_IP/` 에 (`.gitkeep` 외) 파일이 하나라도 있음 — 사유에 "`path` 를 40_IP 밖으로 지정하라" 고 안내 · `path` 가 단일 파일이면 Read 규칙 적용 | `guard_read.py` → `check_search_root` |
| Grep (추가) | `path` 디렉터리(또는 Vault 전체) 아래 어디에든 confidential 노트(또는 40_IP 로 향하는 symlink)가 있으면 차단 — 내용 검색은 본문을 노출하기 때문. Glob 은 이름만 노출하므로 이 추가 규칙을 적용하지 않는다 | `find_confidential_note` |
| Write · Edit · NotebookEdit · Bash 쓰기 | 대상이 `40_IP/**` 이면 **Level 과 무관하게** 차단. Level 3 은 LOCAL 세션에서만 `40_IP/candidates` 를 연다 | `guard_common.check_allowed` → `require_local_for_ip` |
| Bash 읽기 | 토큰에 `40_IP`(대소문자·NFC 무관) 포함 · 비옵션 토큰(글로브 확장 포함, 중괄호 `{a,b}` 전개)이 40_IP 안이나 confidential 노트로 해소 · 재귀 내용 검색(`grep -r`, `rg`, `ag`, `ack`, `ugrep`, `git grep`)의 루트가 Vault 루트/조상/cwd 이면서 40_IP 에 파일이 있거나 confidential 노트가 있음 · 이름 나열(`find`, `fd`, `tree`, `ls -R`)의 루트가 Vault 를 덮으면서 40_IP 에 파일 · `git show`/`git diff`/`git log -p` 의 patch 출력은 `-- <40_IP 밖 경로>` 로 제한하지 않으면 차단(`--stat`/`--name-only` 등 이름만 출력은 허용) · `REF:path` 객체 지정도 path 부분 판정 | `guard_bash.py` → `_check_external_reads` |

- frontmatter 파싱은 표준 라이브러리만 사용한다: BOM 제거 → 첫 줄 `---` → 다음 `---`/`...` 까지 → 최상위 `classification:` 줄. **닫히지 않은 블록·중복 키·빈 값·알 수 없는 값(`public`/`internal`/`confidential` 외)·UTF-8 아님 → 차단**(판단 불가 = 차단). frontmatter 가 없는 `.md`(CLAUDE.md, README) 와 `.md` 가 아닌 파일은 분류를 가질 수 없으므로 허용한다.
- Vault 밖 경로는 이 장치의 범위가 아니다(허용). Vault 를 찾을 수 없으면 ADR-0002 D4 대로 차단한다.
- LOCAL 세션에서는 `guard_read.py` 가 즉시 허용하고, Bash 읽기 장치도 꺼진다. 쓰기 Guard(ADR-0005)는 그대로 적용된다.
- Grep·Glob 은 Linux/macOS 기본 도구 집합에 없어 Claude 가 Bash 의 `grep`/`find`/`rg` 로 검색한다(현행 tools reference). 따라서 Bash 읽기 장치는 선택이 아니라 필수다.
- hooks.json: matcher `Read|Grep|Glob` 은 ADR-0002 §2 의 "영숫자·`|` 만 → 정확한 도구명 목록" 규칙을 따른다. `timeout: 10`, `onFailure: "block"`.

### 3. MCP — `expose_confidential` 은 LOCAL 프로세스에서만 유효

- `VaultService.expose_confidential` = `myelin.yaml mcp.expose_confidential` **AND** `is_local_session()`. EXTERNAL 프로세스에서 플래그가 켜져 있으면 기동 시 stderr 에 경고(`routing_warning()`)를 한 번 출력하고 `false` 로 동작한다(검색 제외 + 본문 `[confidential — body withheld …]` + 역링크 비노출).
- 도구 설명(description)과 서버 instructions 는 EXTERNAL 에서 기밀의 존재를 언급하지 않는다(`"confidential"`, `"40_IP"` 문자열 없음 — 존재 자체가 정보다). LOCAL+opt-in 일 때만 instructions 에 "기밀 포함, 외부 전달 금지" 문장이 붙는다.
- ADR-0007 §3 의 "local 클라이언트 = 소유자 opt-in" 해석을 "**opt-in AND 프로세스 환경 `MYELIN_LLM=local`**" 로 강화한다. 가이드(`docs/guides/mcp-setup.md`)의 로컬 세션 설정 예시는 이 변수를 함께 넘겨야 한다.

### 4. settings.json 2차 방어

- Claude Code 현행 문서(permissions.md, 2026-10-18 확인): `Read(path)` deny 규칙은 Read 와 **best-effort 로 Grep·Glob·LSP** 에 적용되고, 같은 경로의 Edit/Write 도 막는다. **`Grep(...)`/`Glob(...)` 경로 규칙은 수용되지만 평가되지 않는다**(문서 명시: "Use `Read(docs/**)` in place of `Glob(docs/**)`"). `Write(...)` 와 같은 처지다(ADR-0002 D5).
- 따라서 `myelin init` 이 생성하는 `.claude/settings.json` 에 **`Read(./40_IP/**)`** 한 줄을 추가하고, `Grep(...)`/`Glob(...)` 규칙은 작성하지 않는다. 이 규칙은 세션 종류를 모르므로 LOCAL 세션에도 적용된다 — 로컬 세션 운영자는 `settings.local.json`(git 무시) 에서 `allow` 로 덮어쓰거나, Guard 만으로 운영한다. hook 결정은 deny 규칙을 무효화하지 못한다(문서 "PreToolUse hook decisions don't bypass permission rules").
- `classification: confidential` 노트는 경로가 아니라 내용 속성이므로 경로 규칙으로 표현할 수 없다. 이 부분은 Guard 만이 담당한다.

### 5. Vault git pre-commit 장치 — Claude Code 밖에서도 "사람이 승격"

- `init_vault` 스캐폴드가 **`90_System/hooks/pre-commit`**(POSIX sh, 마커 `myelin-pre-commit`)을 만든다. 내용: `exec ${MYELIN_BIN:-myelin} doctor --staged --vault "${MYELIN_VAULT:-$(git rev-parse --show-toplevel)}"`. CLI 를 찾지 못하면 **커밋 거부(exit 1, fail-closed)**.
- `install_git_hook(root: Path) -> Path`(core `scaffold.py`)가 이 파일을 `git rev-parse --git-path hooks`/pre-commit 으로 복사하고 755 로 만든다. 스캐폴드 사본이 없으면 템플릿에서 재생성하고, 마커가 없는 **다른 pre-commit 이 이미 있으면 덮어쓰지 않는다**(ScaffoldError). CLI `init`(`_git_commit_vault` 가 저장소를 만들 때)과 **`myelin doctor --install-hook`**(기존 Vault 재설치)이 호출한다. CLI 가 커밋할 때는 `MYELIN_BIN="<sys.executable> -m myelin_cli"` 를 넘겨 hook 이 같은 CLI 를 실행하게 한다.
- **`myelin doctor --staged`**: `git diff --cached --name-only -z --diff-filter=ACMR` 로 스테이지된 파일을 얻고 **인덱스 blob(`git show :path`)** 을 검사한다(작업 트리가 아님). 노트(`.md`, `90_System`·`_patches`·숨김 디렉터리·`CLAUDE.md` 제외)만 대상이며 ERROR 급 규칙만 적용한다: `schema` · `confidential-share` · `temporal`(verified 인데 reviewed 없음 — origin claude 면 사유에 명시) · `domain` · **`ai-scope`**: `origin: claude` 노트가 **설정된 Level 의 AI 쓰기 범위**(`allowed_dirs(level)` 중 `_patches` 제외) 밖에 있으면 상태와 무관하게 오류. 단, 사람이 거부해 보관한 `99_Archive/**` + `status: deprecated` 는 허용(Hub Reject 의 결과). 링크 그래프 규칙(broken-link·orphan·verified→미검증 AI 링크)은 전체 Vault 가 필요하므로 커밋 게이트에 넣지 않는다. 오류가 있으면 exit 1, git 저장소가 아니면 exit 2.
- Hub 의 커밋은 사람 클릭의 결과이며 Promote 는 `origin: mixed` + `reviewed` 를 설정하므로 통과한다(테스트 `test_staged_ok_exit_0[Promote/Reject shape]`, 실제 git 커밋 `test_real_git_commit_is_rejected_then_accepted`). Hub 의 `ensure_git`(hub 코드)은 아직 `install_git_hook` 를 호출하지 않는다 — 필요한 변경은 두 줄(`from myelin_core.scaffold import install_git_hook` · `git init` 직후 `install_git_hook(v.root)`), 별도 Hub 변경으로 반영한다.
- 사람의 의도적 우회는 git 표준인 `git commit --no-verify` 로 남겨 둔다. 이는 AI 가 Bash 로 실행할 수 없다(`guard_bash` 는 `git commit` 을 허용하지만 `--no-verify` 는 문자열 그대로 통과하므로 **`guard_bash._check_git` 에 `--no-verify`/`-n` 차단을 추가해야 한다** → 본 ADR 과 함께 반영: `git commit --no-verify` 는 사람만).

## 대안과 기각

- `myelin.yaml llm.default: local` 로 세션 판정: Vault 파일은 Hub 설정 화면·사람 편집으로 바뀌고 Guard 가 `myelin.yaml` 쓰기를 막더라도 "로컬이라고 적어 두면 외부 세션도 기밀을 읽는" 상태를 만든다. 세션 속성은 세션을 띄운 사람만 알 수 있으므로 환경 변수로 한정했다.
- Grep/Glob 전체 차단: 기밀이 없는 Vault 에서 과도하다. 40_IP 비어 있고 confidential 노트가 없으면 전체 검색을 허용한다.
- Grep 때 confidential 노트 스캔 생략(40_IP 만 판정): 비용은 노트당 첫 64 KB 읽기(5,000 노트 ≈ 수백 ms) 로 10 초 timeout 안이며, 생략하면 "기밀은 외부로 가지 않는다" 가 40_IP 안에서만 참이 된다. 채택.
- MCP 에서 EXTERNAL 일 때 기동 거부: 읽기 전용 비기밀 접근은 정상 용도이므로 거부 대신 "경고 + false 동작".
- pre-commit 을 Python 으로 작성: hook 은 어떤 셸 환경에서도 실행돼야 하고 Python 경로를 알 수 없다. POSIX sh 로 CLI 를 호출하는 얇은 껍질로 한정했다.

## 잔여 위험 (정직하게)

1. **Bash 로 Vault 밖 스크립트 실행**(`python3 /tmp/x.py`)·패키지 설치 등은 ADR-0005 와 같이 범위 밖이다. 스크립트 내용은 검사하지 않는다.
2. **인덱스 DB**(`.myelin/index.db`)에는 기밀 본문이 들어 있다. git 무시·바이너리이므로 ripgrep 기본 설정은 건너뛰지만 `grep -a`/`sqlite3` 로 읽을 수 있다. `.myelin` 토큰 차단은 Hub·CLI 운영을 깨므로 넣지 않았다 — Backlog: LOCAL 이 아닐 때 색인에서 confidential 본문을 빼는 옵션.
3. **Glob/`ls`/`find` 로 40_IP 밖 confidential 노트의 제목**(파일명)은 노출된다. 제목도 아이디어일 수 있다. 본문 노출만 막는 것으로 선을 그었다.
4. **frontmatter 가 없는 `.md`** 는 분류를 알 수 없어 허용한다. doctor 가 schema 오류로 잡아 사람이 고치도록 한다.
5. **git 이력 뷰**: `git show`/`git log -p` 는 40_IP 파일이 있거나 confidential 노트가 있을 때 `-- <경로>` 제한을 요구한다. 그러나 `-- 10_Domains/D2` 처럼 **지금은** 기밀이 없는 경로의 과거 커밋에 기밀이 있었다면 노출된다(이력은 스캔하지 않음).
6. **`core.hooksPath`/`--no-verify`/hook 삭제** 는 사람 권한이다. 사람이 장치를 끄는 것은 막지 않는다(막을 수도 없다).
7. **중첩 Vault**(큰 저장소 안의 Vault): hook 은 저장소 최상위에 설치되고 `--vault` 는 `MYELIN_VAULT` 또는 최상위를 쓴다. 최상위가 Vault 가 아니면 `doctor --staged` 는 exit 2 로 커밋을 거부하므로 `MYELIN_VAULT` 를 설정해야 한다.
8. **Grep `path` 절대/상대 해석**: Claude Code 는 절대 경로를 넘기지만 상대 경로가 오면 이벤트 `cwd` 기준으로 해석한다. `cwd` 가 없고 `path` 도 없으면 차단한다.
9. 플러그인이 설치되지 않은 세션(T01 과 동일)은 settings.json 의 `Read(./40_IP/**)` 만 남는다.

## 결과

- 정본 §5.3 `llm.route` 의 두 항목(`confidential`, `40_IP/**`)이 이제 장치(Guard 3종 + settings.json + MCP)로 집행된다. 정본 Rev 2.1 에 "라우팅 = 세션 환경 변수 `MYELIN_LLM`" 해석을 반영한다(Backlog).
- 테스트: `tests/plugin/test_guard_read.py`(Read/Grep/Glob/Bash 읽기, symlink·`..`·NFD·env 변형·중첩 Vault), `tests/plugin/test_guard_write.py::test_level_matrix`(EXTERNAL 행 추가), `tests/plugin/test_guard_bash.py::test_level_matrix_bash`, `packages/myelin-mcp/tests/test_routing.py`, `packages/myelin-cli/tests/test_cli_devices.py`(hook 설치·`--staged`·실제 git 커밋 거부/허용·`--no-verify`·중첩 Vault). 위협 모델 T02·T05 갱신, T20·T21 추가.
