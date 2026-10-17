# ADR-0002: Claude Code Plugin · Hook 사양 확인과 Guard 설계 보정

- 상태: Accepted (P3 착수 시 재확인)
- 일자: 2026-10-18
- Phase: P0
- 확인 출처: Claude Code 공식 문서 — Hooks reference (`code.claude.com/docs/en/hooks`),
  Plugin manifest reference (`code.claude.com/docs/en/plugins-reference`), 2026-10-18 열람

## 맥락
명세 Rev 2.0 §7.2의 Fail-closed Guard는 PreToolUse Hook으로 AI의 쓰기 경로를 강제한다.
명세의 Hook 예시는 "요지" 수준이었으므로 현행 사양과 대조해 확정한다.

## 확인된 사양 (요약)
1. **입력:** Hook은 stdin으로 JSON을 받는다. 공통 필드 `session_id`, `cwd`, `permission_mode`,
   `hook_event_name` 등, PreToolUse 전용 `tool_name`, `tool_input`, `tool_use_id`.
2. **종료 코드:** `0` = 성공(결정 없음이면 일반 권한 흐름), **`2` = 차단(stderr가 Claude에게 사유로 전달)**,
   **그 외(1 포함) = 비차단 오류 — 도구 호출이 그대로 진행된다.**
3. **JSON 결정:** exit 0 + `hookSpecificOutput.permissionDecision: "deny"` 로도 차단 가능. exit 2는 JSON으로 뒤집을 수 없다.
4. **matcher:** 영문·숫자·`_`·`|` 만 있으면 정확한 이름 목록(`Write|Edit`), 그 외 문자가 있으면 정규식.
   핸들러별 `if` 필드로 권한 규칙 문법(`Bash(rm *)`) 필터 가능.
5. **환경변수:** Hook 프로세스에 `CLAUDE_PROJECT_DIR`, `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA` 가 전달된다.
   `cwd` 는 Claude의 `cd`·worktree 이동을 따라가지만 `CLAUDE_PROJECT_DIR` 은 고정이다.
   이 변수들은 Bash 도구로 실행되는 명령의 환경에는 없다.
6. **실행 형식:** `args` 를 주면 셸 없이 exec 형식으로 실행된다 (경로 공백·인용 문제 없음).
7. **Plugin 레이아웃:** `.claude-plugin/plugin.json`(선택, `name` 만 필수, kebab-case),
   `skills/<name>/SKILL.md`, `hooks/hooks.json`(최상위 `"hooks"` 래퍼 필수), `.mcp.json`.
   이름이 `claude-`·`anthropic-` 로 시작하면 오류. **플러그인 루트의 `CLAUDE.md` 는 로드되지 않는다.**
8. **검증:** `claude plugin validate ./plugin` (`--strict` 로 경고도 실패 처리).

## 결정 — 명세 §7.2 대비 보정 사항
| # | 명세 Rev 2.0 | 보정 | 이유 |
|---|---|---|---|
| 1 | Guard가 예외 처리 없이 종료 | **모든 예외를 잡아 exit 2** | exit 1은 비차단 → 파싱 오류 시 쓰기가 통과됨. Fail-closed 위반 |
| 2 | Vault 루트 = `MYELIN_VAULT` 또는 `os.getcwd()` | `MYELIN_VAULT` → `CLAUDE_PROJECT_DIR` 순, **둘 다 없으면 차단** | `cwd` 는 `cd` 를 따라 이동하므로 경계로 쓸 수 없음 |
| 3 | 셸 형식 command | **exec 형식** (`command: "python3"`, `args: ["${CLAUDE_PLUGIN_ROOT}/scripts/guard_write.py"]`) | 경로 인용 문제 제거 |
| 4 | matcher `Write\|Edit\|MultiEdit` | `Write\|Edit\|MultiEdit\|NotebookEdit` | 노트북 편집 경로 누락 방지 |
| 5 | 경로 정규화 `resolve()` 후 비교 | 유지 + **심볼릭 링크로 Vault 밖을 가리키는 경우 차단**, 판단 불가 경로(빈 값·상대경로 해석 실패) 차단 | 경계 우회 방지 |
| 6 | Vault 운영 지침을 CLAUDE.md에 | Vault의 `CLAUDE.md` 는 유지(프로젝트 컨텍스트), **플러그인 지침은 Skill 본문에** | 플러그인 루트 CLAUDE.md 미로드 |
| 7 | Bash 우회는 permissions로 | 유지. P3에서 Vault용 `.claude/settings.json` 템플릿에 Bash 쓰기 명령 deny 규칙 포함 | Hook은 Write/Edit만 감시 |

## 결과
- P3 Gate에 다음 테스트를 포함한다: 잘못된 JSON·필드 누락·Vault 루트 미지정 → 모두 exit 2.
- P3 CI에 `claude plugin validate --strict ./plugin` 을 추가한다 (CI에 Claude Code CLI 설치 필요 — 불가 시 로컬 Gate로 대체하고 ADR 갱신).
- 사양은 바뀔 수 있으므로 P3 착수 시 이 ADR을 다시 대조한다.
