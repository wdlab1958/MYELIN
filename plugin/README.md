# MYELIN for Claude Code

`myelin init` 으로 만든 Obsidian Vault에서 쓰는 Claude Code 플러그인입니다.

## 설치

```
/plugin marketplace add wdlab1958/MYELIN
/plugin install myelin@myelin
```

그다음 **Vault 폴더에서** Claude Code를 실행합니다.

## Skills — 모두 사람이 명시적으로 호출합니다

| 명령 | 최소 Level | 하는 일 | 쓰는 곳 |
|---|---|---|---|
| `/myelin:ingest <파일·URL·메모>` | 1 | 외부 자료 → literature 초안 | `00_Inbox/ai-drafts/` |
| `/myelin:distill <Inbox 노트>` | 1 | 원자 노트(evergreen) 초안으로 분해 | `00_Inbox/ai-drafts/` |
| `/myelin:interview <Domain ID>` | 1 | 질문 은행으로 경험을 묻고 lesson 초안 | `00_Inbox/ai-drafts/` |
| `/myelin:review [주]` | 1 | doctor·stats 기반 주간 리뷰 | `50_Journal/reviews/` |
| `/myelin:link <노트·Domain>` | 2 | 링크·MOC 변경 **제안** (patch) | `_patches/` |
| `/myelin:compose <목적>` | 2 | verified 노트로 산출물 초안 | `80_Outputs/drafts/` |
| `/myelin:ip-scan [Domain]` | 3 | Cross-domain 노트에서 특허 후보 | `40_IP/candidates/` |

Level은 Vault의 `myelin.yaml` 에서 사람이 정합니다.

## 안전장치

- **Vault 안 Guard (주 장치)** — `myelin init` 이 `.claude/settings.json` 과 `.claude/hooks/myelin_guard.py` 를 만듭니다.
  Level이 허용한 폴더의 `.md` 외에는 Claude가 쓰지 못하고, `40_IP/` 와 `classification: confidential` 노트는 읽지 못합니다
  (Claude가 읽으면 내용이 Anthropic으로 전송되기 때문 — `llm.route` 가 `local` 인 기본 설정).
- **이 플러그인의 Hook (보조)** — 다른 프로젝트에서 작업하던 세션이 Vault 안으로 쓰려는 경우를 같은 규칙으로 막습니다.
  Vault와 무관한 파일에는 관여하지 않습니다.
- 판단할 수 없는 입력은 차단합니다 (fail-closed). Hook에는 `python3` (3.9+) 가 필요합니다.

알려진 한계: `Grep` 결과 줄은 막지 못합니다. 정말 민감한 내용은 별도 Vault에 두세요.
