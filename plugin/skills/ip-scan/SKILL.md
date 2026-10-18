---
name: ip-scan
description: Cross-domain verified 노트에서 특허 후보를 찾아 40_IP/candidates 에 idea-ip 초안을 만든다. 로컬 LLM 라우팅 전제. Level 3 전용.
argument-hint: "[--domains D1,D4] [--since 2026-09-01]"
allowed-tools: Read, Glob, Grep, Bash(myelin *), Write
disable-model-invocation: true
---

# /ip-scan — 특허 후보 추출 (Level 3, 사용자 호출 전용)

공통 규약: `plugin/skills/_COMMON.md`. 최소 Level **3** · 쓰기 범위 **`40_IP/candidates/`**.

## 전제 (반드시 먼저 확인)
- `myelin.yaml` 의 `llm.route` 에 `"40_IP/**": local` 과 `confidential: local` 이 있어야 한다. 현재 세션이 외부 Claude 라면 **40_IP 의 기존 파일을 읽지 않는다** — "ip-scan 은 로컬 LLM 세션에서 실행하세요" 라고 안내하고 멈춘다. (판단 불가 = 중단)
- 사용자가 직접 호출한 경우에만 동작한다(`disable-model-invocation`).

## 절차
1. `domain` 이 2개 이상인 `status: verified` 노트를 모은다(`--since` 이후 `reviewed`).
2. 각 노트 조합에서 **문제–해결–효과** 구조가 성립하는지 본다. 성립하는 것만 후보.
3. 후보마다 `90_System/templates/idea-ip.md` 로 `40_IP/candidates/<아이디어 한 문장>.md` 를 만든다. `classification: confidential` 고정, `share: false`, `origin: claude`, `status: draft`, `source` 에 근거 노트 링크, `tags: [ip, candidate]`.
4. 선행기술은 **Vault 내부 literature 노트** 로만 비교한다(외부 검색 금지).
5. 보고는 **제목 목록만** 출력한다(본문·청구항 후보는 노트 안에만). `myelin doctor` 로 confidential+share 모순이 없음을 확인.
