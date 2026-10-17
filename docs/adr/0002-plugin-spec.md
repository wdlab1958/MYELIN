# ADR-0002: Claude Code Plugin / Hook 현행 사양 확인 메모

- 상태: Accepted · 일자: 2026-10-18 · Phase: P0 (P3 Gate에서 테스트로 고정)
- 근거: 정본 §7.1~7.2 "Hook 입력 필드명·환경변수는 P0에서 현행 Claude Code 문서로 재확인하고 테스트로 고정한다"
- 확인 방법: code.claude.com/docs 현행 문서 조회 (2026-10-18). 로컬 Claude Code 2.1.302.
- 출처: https://code.claude.com/docs/en/plugins/manifest-reference.md · https://code.claude.com/docs/en/hooks.md · https://code.claude.com/docs/en/permissions.md · https://code.claude.com/docs/en/plugins/cli-reference.md · https://code.claude.com/docs/en/mcp.md · https://code.claude.com/docs/en/tools-reference.md · https://code.claude.com/docs/en/skills.md

## 1. Plugin 레이아웃 (확정)

```
plugin/
├── .claude-plugin/plugin.json   # manifest. 필수 필드는 name(kebab-case)만. 다른 구성요소는 이 폴더 밖에.
├── skills/<skill>/SKILL.md      # 자동 스캔. 호출명: /myelin:<skill>
├── commands/*.md                # 선택
├── hooks/hooks.json             # 자동 로드. 최상위 "hooks" 래퍼 필수
├── hooks/guard_write.py
└── .mcp.json                    # 선택: 플러그인 번들 MCP 서버
```

- manifest 선택 필드: `displayName, version, description, author{name,email,url}, homepage, repository, license, keywords, defaultEnabled, dependencies, settings, userConfig, skills, commands, agents, hooks, mcpServers, lspServers, outputStyles, workflows`.
- 사용자 지정 경로는 `./`로 시작, 플러그인 루트 안이어야 함. `hooks`/`mcpServers`는 기본 파일과 **merge**, `commands`/`agents`는 **replace**, `skills`는 **add**.
- SKILL.md frontmatter(모두 선택): `name, description, when_to_use, argument-hint, disable-model-invocation, user-invocable, allowed-tools, disallowed-tools, model, effort, context(fork), agent, hooks, paths, shell`. description+when_to_use 합계 1,536자에서 잘림.

## 2. Hooks 설정 (확정)

```json
{ "hooks": { "PreToolUse": [ { "matcher": "Write|Edit|MultiEdit|NotebookEdit",
  "hooks": [ { "type": "command", "command": "python3",
               "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/guard_write.py"],
               "timeout": 10, "onFailure": "block" } ] } ] } }
```

- **matcher 문법**: 영숫자·`_`·`-`·공백·`,`·`|`만 포함 → 정확한 도구명 목록(`|` 구분). 그 외 문자가 있으면 **JS 정규식(unanchored)** — `Edit.*`는 `NotebookEdit`도 매칭. `*`/빈 값/생략 = 전체.
- **MultiEdit**: 현행 tools reference에는 `Edit, Write, NotebookEdit`만 있고 MultiEdit은 "legacy". matcher에 남겨도 무해하므로 호환을 위해 포함하되 **NotebookEdit을 반드시 추가**한다 (정본 §7.2의 `Write|Edit|MultiEdit`에서 변경 → 결정 D1).
- `args` exec 형식 권장(셸 quoting 없음). 기본 timeout은 command hook **600초**(agent hook은 60초). Guard는 10초로 제한.
- `onFailure: "block"`(v2.1.295+)은 hook 자체 실패(비정상 종료·timeout)를 차단으로 처리 → fail-closed 보강 (결정 D2).

## 3. PreToolUse stdin JSON (확정, 테스트로 고정할 필드)

공통: `session_id, prompt_id, transcript_path, cwd, scratchpad_dir, permission_mode, effort, hook_event_name` (+ 서브에이전트 내 `agent_id, agent_type`).
PreToolUse: `tool_name, tool_input, tool_use_id` (MCP 도구는 `mcp_server{name,source}` 추가).

| tool_name | tool_input 필드 |
|---|---|
| Write | `file_path`(절대경로), `content` |
| Edit | `file_path`(절대경로), `old_string`, `new_string`, `replace_all`(bool) |
| NotebookEdit | `notebook_path`, … (Guard는 `file_path` 부재 시 `notebook_path`도 검사, 둘 다 없으면 차단) |
| Bash | `command`, `description`, `timeout`, `run_in_background` |

- `~`와 상대경로는 hook 호출 전에 **절대경로로 정규화**됨. Guard는 그래도 `resolve()`(symlink 해소) 후 Vault 상대경로를 계산한다.

## 4. 종료 코드 / JSON 결정 (확정)

- **exit 0**: 성공. stdout이 단일 JSON이면 파싱. 결정 없으면 일반 권한 흐름 계속.
- **exit 2**: 차단. stderr가 `PreToolUse:<Tool> hook error: […]` 형태로 Claude에 전달. stdout JSON이 allow여도 **exit 2가 우선**.
- 기타 exit: 비차단 오류, 도구 실행 진행 → `onFailure: "block"`으로 차단 전환.
- JSON 대안: `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow|deny|ask|defer","permissionDecisionReason":"…","updatedInput":{…}}}`. 다중 hook 결합 순위 deny > defer > ask > allow. `allow`는 권한 프롬프트만 생략하며 deny 규칙을 무효화하지 못함.
- **MYELIN 결정 D3**: Guard는 **exit 2 + stderr 사유**를 유일한 차단 수단으로 사용한다(가장 단순·우선순위 최상). JSON 출력은 사용하지 않는다.

## 5. 환경변수 (확정)

`CLAUDE_PLUGIN_ROOT`(설치된 플러그인 디렉터리), `CLAUDE_PLUGIN_DATA`(`~/.claude/plugins/data/<id>/`), `CLAUDE_PROJECT_DIR`(세션 시작 프로젝트 루트), `CLAUDE_PLUGIN_OPTION_<KEY>`(userConfig), `CLAUDE_EFFORT`. `CLAUDE_ENV_FILE`은 PreToolUse에 **없음**.
- **MYELIN 결정 D4**: Vault 루트 결정 순서 = `MYELIN_VAULT` env → `CLAUDE_PROJECT_DIR` → `cwd`(stdin). 어느 것도 Vault(`myelin.yaml` 존재)가 아니면 **차단**(판단 불가 = fail-closed).

## 6. Bash 우회 보완 — permissions deny 규칙 (확정, 정본 §7.2 "Guard의 한계와 보완")

- 규칙 형식 `Tool(pattern)`, gitignore 스타일. 경로 앵커: `//abs`, `~/home`, `/settings-relative`(프로젝트 설정에서는 작업 디렉터리), `path|./path`(cwd 상대).
- **`Edit(path)` 규칙이 Edit·Write·NotebookEdit을 모두 포함**한다. `Write(path)` 규칙은 수용되지만 **평가되지 않음** → Vault용 `.claude/settings.json` 템플릿은 반드시 `Edit(...)`로 작성 (결정 D5).
  예) `"deny": ["Edit(./10_Domains/**)", "Edit(./40_IP/**)", "Edit(./90_System/**)", "Edit(./myelin.yaml)"]`
- `Read(path)` deny는 해당 경로의 Edit/Write도 차단(v2.1.208+/2.1.228+).
- Bash 패턴(`Bash(rm *)`, `Bash(git push *)`)은 명령 텍스트 접두어만 매칭 — `/bin/rm`, 파이프, heredoc 우회는 막지 못한다. **Bash 우회의 실질적 차단은 P3에서 Bash용 PreToolUse hook(명령 문자열의 리다이렉션·`tee`·`sed -i`·`mv`·`cp`·`rm` 대상 경로 검사)으로 보강**하고, deny 규칙은 2차 방어로 둔다 (결정 D6 → P3 Task에 반영).

## 7. 로드·검증 (확정)

- 세션 한정 로드: `claude --plugin-dir ./plugin` · 설치: `claude plugin install <plugin>@<marketplace> [--scope project]` · 마켓플레이스 파일 `.claude-plugin/marketplace.json`.
- 검증: `claude plugin validate ./plugin [--strict]` (exit 0 통과 / 1 실패 / 2 오류). manifest·skills·agents·commands·hooks 검사, MCP 항목은 v2.1.281+. 플러그인 루트의 `CLAUDE.md`는 경고.
- **P3 Gate에 `claude plugin validate --strict` 통과를 추가**한다.

## 8. MCP 등록 (확정)

- 플러그인 루트 `.mcp.json`의 `mcpServers` 또는 manifest `mcpServers`(인라인/경로). `${CLAUDE_PLUGIN_ROOT}`, `${CLAUDE_PLUGIN_DATA}`, `${CLAUDE_PROJECT_DIR}` 치환 지원.
- 플러그인 번들 MCP 도구명: `mcp__plugin_<plugin>_<server>__<tool>`. hook matcher는 이 전체 이름으로 작성.
- **MYELIN 결정 D7**: MYELIN MCP(P4)는 플러그인 번들이 아닌 **사용자 설정(별도 등록)** 을 기본으로 한다. Hub·Desktop·Code가 동일 서버를 공유해야 하고, write_draft 허용 여부가 Vault별 `myelin.yaml`에 묶이기 때문.

## 미확인 (P3에서 테스트로 보강)

- hook 입력 공통 필드 전체 표(예시에서만 확인) · matcher 대소문자 구분 · `MultiEdit` 포함 matcher가 `plugin validate`에서 경고를 내는지.
- 대응: P3-T3 Guard 테스트에 "알 수 없는 tool_name / 필드 누락 / 비JSON stdin → exit 2" 케이스 포함. 로컬 Claude Code 버전과 문서가 다르면 로컬 동작을 기준으로 fixture 갱신.

## 정본 대비 변경 요약

| # | 정본 §7.2 | 변경 | 사유 |
|---|---|---|---|
| D1 | matcher `Write\|Edit\|MultiEdit` | `Write\|Edit\|MultiEdit\|NotebookEdit` | MultiEdit은 legacy, NotebookEdit이 현행 쓰기 도구 |
| D2 | — | `onFailure: "block"`, `timeout: 10` | hook 자체 실패도 차단 |
| D3 | exit 2 | exit 2 유지, JSON 출력 미사용 | 우선순위 최상·단순 |
| D4 | `MYELIN_VAULT` or cwd | `MYELIN_VAULT` → `CLAUDE_PROJECT_DIR` → cwd, Vault 아니면 차단 | 판단 불가 = 차단 |
| D5 | settings.json permissions | `Edit(...)`만 사용 (`Write(...)` 미평가) | 문서 명시 |
| D6 | deny 규칙으로 Bash 보완 | + Bash PreToolUse hook | 접두어 매칭의 한계 |
| D7 | — | MCP는 플러그인 번들 아님 | 클라이언트 공유·Vault별 정책 |
