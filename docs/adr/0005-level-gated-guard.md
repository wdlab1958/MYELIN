# ADR-0005: Level-gated Fail-closed Guard (Write/Edit + Bash)

- 상태: Accepted · 일자: 2026-10-18 · Phase: P3
- 근거: 정본 §3 Fail-closed / Phase-gated Autonomy, §7.1 Skill 표, §7.2 Guard, ADR-0002 D4·D6

## 맥락

정본 §7.2 의 Guard 는 고정 ALLOW 4경로를 막는다. 그러나 §7.1 은 Skill 마다 최소 Level 과 쓰기 범위를 다르게 둔다(/link → `_patches` L2, /compose → `80_Outputs/drafts` L2, /ip-scan → `40_IP/candidates` L3). Level 1 사용자의 Vault 에서 `_patches` 쓰기가 허용되면 "단계적 개방" 이 장치가 아니라 규칙에 머문다. 또 Hook 은 Write/Edit 만 보므로 Bash 우회가 남는다(§7.2 "Guard의 한계와 보완").

## 결정

1. **허용 경로는 Level 에 따라 누적**한다 (`LEVEL_ALLOW`, 단일 정의는 `myelin_core.levels`, Guard 는 표준 라이브러리만 쓰므로 복사본을 두고 테스트로 동기화):
   - L0 `()` — 읽기 전용, 모든 쓰기 차단
   - L1 `00_Inbox/ai-drafts`, `50_Journal`
   - L2 + `_patches`, `80_Outputs/drafts`
   - L3 + `40_IP/candidates`
   정본 §7.2 ALLOW(4경로) 는 L2 와 같다. `40_IP/candidates` 는 §7.1 /ip-scan 쓰기 범위를 반영해 L3 에 추가.
2. **Level 은 Vault `myelin.yaml` 의 `level:` 줄**에서 읽는다(정규식, YAML 라이브러리 없음). 없거나 0~3 이 아니면 차단.
3. **Vault 루트** = `MYELIN_VAULT` → `CLAUDE_PROJECT_DIR` → 이벤트 `cwd` → `os.getcwd()` 중 `myelin.yaml` 이 있는 첫 경로. 없으면 차단 (ADR-0002 D4).
4. **경로 판정** = `Path.resolve()`(symlink 해소) 후 Vault 상대경로가 허용 디렉터리 아래인지. `..` 가 포함된 원문 경로, 숨김 파일(`.`로 시작), 빈 경로, NUL 은 차단.
5. **Bash Guard** (`guard_bash.py`) 를 추가한다. 리다이렉션·writer 명령(tee/sed -i/mv/cp/rm/…)의 대상 경로를 4 의 규칙으로 판정하고, 판단 불가 입력은 차단: `$(…)`·백틱·변수, `cd`+쓰기, 인라인 인터프리터(`python -c`, `bash -c`, …), 파싱 실패, `sudo`/`env`. 파괴적·외향 git(checkout/restore/reset/clean/stash/rm/mv/rebase/merge/pull/push/switch/worktree) 차단, `git commit/add/status/diff/log` 허용.
6. **Hook 설정**: `onFailure: "block"`, `timeout: 10`. Hook 자체 오류·예외도 차단(`except Exception → exit 2`).
7. **Skill 비노출은 소프트 가드**: Plugin Skill 파일은 정적이라 Vault 별로 숨길 수 없다. 대신 (a) 모든 SKILL.md 가 시작 시 `myelin skills --json` 으로 Level 을 확인하고 미달이면 중단, (b) Vault `CLAUDE.md` 가 Level 별 사용 가능 Skill 만 나열, (c) Guard 가 하드 차단. 부록 B 의 "Level 0 에서는 Skill 자체를 비노출" 은 이 세 겹으로 해석한다.
8. **2차 방어**: `myelin init` 이 Vault `.claude/settings.json` 을 생성한다 — `Edit(./10_Domains/**)` 등 사람 승인 영역 deny(`Write(...)` 는 평가되지 않으므로 `Edit(...)` 만), Bash 접두어 deny, `git commit` 은 ask.

## 결과

- 알려진 한계: 스크립트 파일 실행(`python script.py`)의 부작용은 검사하지 않는다(인라인 코드만 차단). `uv run myelin …` 등 CLI 호출은 허용된다 — `myelin init/add-domain` 은 사람 승인 영역을 쓰지만 CLI 자체가 fail-closed(덮어쓰기 금지)이고 Vault 밖 생성은 Guard 범위 밖이다. P8 위협 모델에서 재평가.
- Guard 테스트(`tests/plugin/`)는 서브프로세스로 실제 hook 을 실행하며 Level 0~3 × 경로 유형 × 우회 입력을 100% 차단/허용 표로 고정한다.
