# ADR-0017: 고객정보 가드 — 쓰기 전 결정적 검사

- 상태: Accepted · 일자: 2026-11-26 · Phase: P10 (WBS 2.5.5)
- 근거: MYELIN 의 Skill 작업은 Claude Code(외부 LLM 세션)를 거친다. One Cycle Dev. Framework 수행 중 생긴 지식을 담을 때 고객 식별 정보·고객 코드·자격증명이 노트에 남으면 안 된다. 기존 장치는 Commons 공개 시점의 비식별 스캔(ADR-0010)뿐이라 Vault 에 들어오는 시점에는 검사가 없었다. 지침: [`docs/guides/knowledge-management-policy.md`](../guides/knowledge-management-policy.md).

## 결정

1. **LLM 을 쓰지 않는 패턴 검사**(`myelin_core.infoguard`). 판정은 두 단계다.
   - **block** — 자격증명(개인키 블록, AWS·GitHub·Slack 토큰, JWT, Bearer 헤더, URL 내 계정, `password=…` 류 대입), 주민등록번호, 고객명 목록 적중. 쓰기를 거부한다.
   - **flag** — 긴 코드 블록(기본 30줄 초과: 고객 코드일 수 있다), IP 주소, 내부 URL. 사람이 확인(ack)해야 Inbox 밖으로 나간다.
2. **부르는 곳** — Inbox 밖에 저장하거나 다른 도구를 대신해 초안을 만드는 모든 경로:
   | 경로 | block | flag |
   |---|---|---|
   | Hub 승격(00_Inbox → 10_Domains) | 422 | `guard_ack` 없으면 409 |
   | Hub patch 적용(추가되는 줄만 판정) | 422 | — |
   | MCP `write_draft` | 거부(파일 미생성) | Review Gate 에 맡김 |
   | `myelin onecycle import-findings` | 해당 finding 미생성, exit 1 | `guard-flag` 태그와 안내문을 넣어 생성 |
   | Commons 공개(`check_publishable`) | 차단 | 긴 코드 블록 차단 |
   | `myelin doctor --staged`(pre-commit) — 00_Inbox 밖의 노트 | 커밋 거부 | 표시만 |
   | `myelin guard scan` | exit 1 | `--strict` 면 exit 1 |
3. **설정** — 내장 규칙은 항상 적용된다. `<Vault>/90_System/infoguard.yaml`(`max_code_block_lines`·`block_patterns`·`flag_patterns`·`terms`·`names_file`, 모르는 키 거부), 고객명 목록 `<Vault>/.myelin/customer-names.txt`·`names_file`·`$MYELIN_CUSTOMER_NAMES`(한 줄에 하나), 그리고 기존 `90_System/deid.yaml` 의 `terms`. **고객명 목록 자체가 고객 정보**이므로 기본 위치는 git 에 올라가지 않는 `.myelin/` 이다.
4. **Fail-closed** — 정책 파일을 읽을 수 없거나 형식이 틀리면 쓰기를 거부한다(빈 목록으로 조용히 통과하지 않는다).
5. **적중 내용은 가린다** — 보고·로그·오류 메시지는 앞 몇 글자와 `***` 만 보여 준다. 가드가 비밀값을 다시 퍼뜨리지 않는다.
6. `myelin.yaml` 스키마는 바꾸지 않는다(별도 파일). `doctor` 의 규칙 8종과 JSON 출력도 그대로다 — 가드 결과는 stderr 와 종료 코드로만 나간다.

## 결과
- 테스트: `test_infoguard.py`(반드시 막을 표본 10 · 반드시 통과할 표본 12 · 마스킹 · 정책 fail-closed · 배포 템플릿/fixture 무적중), Hub `test_guard_onecycle_hub.py`, CLI `test_guard_scan_*`·`test_pre_commit_guard_*`, MCP `test_write_draft_refuses_secrets_and_customer_names`.

## 남은 한계
- 패턴 검사다. 목록에 없는 고객명·별칭, 형식이 없는 비밀값, 30줄 이하로 나눈 고객 코드는 잡지 못한다. 사람의 Review Gate 와 지침이 1차 통제이고 가드는 보조 장치다.
- 이미 Vault 에 있는 노트는 소급 검사하지 않는다(`myelin guard scan --vault` 로 직접 돌린다). Obsidian 에서 직접 쓴 노트는 커밋 시점(pre-commit)에야 걸린다.
- 오탐·미탐 비율을 실제 프로젝트 노트로 측정하지 않았다.
