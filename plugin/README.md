# MYELIN for Claude Code (plugin)

Layout follows `docs/adr/0002-plugin-spec.md`.

| 경로 | 내용 |
|---|---|
| `.claude-plugin/plugin.json` | manifest |
| `skills/<skill>/SKILL.md` | `/myelin:ingest` `/myelin:distill` `/myelin:interview` `/myelin:review` `/myelin:link` `/myelin:compose` `/myelin:ip-scan` |
| `hooks/hooks.json` | PreToolUse: `Write|Edit|MultiEdit|NotebookEdit` → `guard_write.py`, `Bash` → `guard_bash.py` |
| `hooks/guard_common.py` | Vault 탐색(`MYELIN_VAULT` → `CLAUDE_PROJECT_DIR` → cwd), Level 읽기, 경로 해석(symlink·`..`), Level별 허용 경로 |

## 동작 (ADR-0005)
- 허용 경로는 Vault `myelin.yaml` 의 `level` 에 따라 누적: L1 `00_Inbox/ai-drafts`, `50_Journal` · L2 + `_patches`, `80_Outputs/drafts` · L3 + `40_IP/candidates`. L0 은 모든 쓰기 차단.
- 판단 불가(비JSON, 경로 없음, Vault 없음, `$(…)`, `cd`+쓰기, 인라인 인터프리터)는 **차단**(exit 2). 사유가 Claude 에게 전달된다.
- Skill 은 시작 시 Level 을 확인하고(`myelin skills --json`) 최소 Level 미달이면 중단한다. Guard 가 하드 가드, Skill 안내가 소프트 가드, Vault `.claude/settings.json` 의 deny 규칙이 2차 방어.

## 설치
```
/plugin install myelin --marketplace wdlab1958/myelin
```
(Claude Code 2.1.275+, 저장소 `.claude-plugin/marketplace.json` 기준. 로컬 체크아웃: `claude plugin marketplace add <repo path>` 후 동일.)

## 로컬 테스트
```bash
claude --plugin-dir ./plugin            # 세션 한정 로드
claude plugin validate ./plugin --strict
MYELIN_VAULT=/path/to/vault echo '{"tool_name":"Write","tool_input":{"file_path":"10_Domains/x.md"}}' | python3 plugin/hooks/guard_write.py; echo $?
```
