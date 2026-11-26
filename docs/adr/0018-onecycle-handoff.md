# ADR-0018: One Cycle 인계 수신 — `source_platform` 초안과 findings 가져오기

- 상태: Accepted · 일자: 2026-11-26 · Phase: P10 (WBS 3.6, 3.5)
- 근거: One Cycle Dev. Framework 에서 MYELIN 은 받는 쪽이다. 지금까지 자동 인계는 Proof-Skills → MYELIN 하나였고 LLMOps·SSC·ARGUS 의 결과는 사람이 직접 적었다. 인계는 파일(USB·공유 폴더)로 하며 망분리 환경에서도 같아야 한다.

## 결정

1. **초안 노트는 별도 경로가 필요 없다.** 다른 플랫폼은 `<Vault>/00_Inbox/ai-drafts/` 에 새 Markdown 파일만 만든다(덮어쓰기·`myelin.yaml` 수정·git 실행 금지). frontmatter 에 `source_platform: llmops|ssc|argus|proof-skills` 를 넣는다. Frontmatter v2 는 모르는 키를 보존하므로(ADR-0003) 이 초안은 보통의 AI 초안이다 — Review Gate, doctor, pre-commit, 고객정보 가드가 그대로 적용되고 승격 뒤에도 `source_platform` 이 남는다. ARGUS 재진단 요청(`onecycle.rediagnosis-request/v1`)의 Markdown 사본도 같은 초안이다.
2. **Domain 은 Pack(데이터)** — `packs/wdlab.onecycle` 이 `LLMOPS`·`SSC`·`ARGUS` 를 선언한다(`PROOF-SKILLS` 는 Proof-Skills 가 배포하는 `wdlab.proof-skills`). 필요한 Domain 만 `myelin add-domain` 으로 더한다.
3. **라우팅 규칙** — 초안에 `domain` 이 없으면 `source_platform` 의 Domain 이 Vault 에 있을 때 그리로 승격한다(`myelin_core.onecycle.route_domain`). 없으면 지금처럼 사람이 고른다(422). 모르는 값은 어디로도 보내지 않는다.
4. **가져오기** — `myelin onecycle import-findings <file.json> --vault <Vault>` 가 `onecycle.findings/v1` 파일의 finding 하나당 초안 하나를 만든다.
   - 결정적 코드(LLM 없음). 파일의 값만 옮기고 판단을 보태지 않는다. `simulated: true` 는 본문 머리와 태그·`confidence: low` 로 드러낸다.
   - 스키마 위반·빈 `findings`·중복 id·읽을 수 없는 파일은 거부(exit 2), **아무것도 쓰지 않는다**.
   - 새 파일만 만든다(`open("x")`). finding id 표식(`source: ["onecycle:<id>"]`)이 초안·승격본·기각본 어디에든 있으면 다시 만들지 않는다(멱등).
   - 노트마다 고객정보 가드를 거친다(ADR-0017).
   - git 과 `myelin.yaml` 은 건드리지 않는다. 승격은 사람이 Hub 에서 한다.
5. 스키마 정본 사본은 `docs/onecycle/`(바이트 동일성 테스트), 표본은 `docs/onecycle/samples/`(가상 데이터, `simulated: true`).

## 결과
- 테스트: `test_onecycle.py`(스키마 사본 일치·표본 검증·잘못된 입력 17종·멱등·덮어쓰기 금지·가드·적대적 제목·라우팅), Hub `test_guard_onecycle_hub.py`, CLI `test_onecycle_import_findings_cli`.
- 절차: [`docs/onecycle/HANDOFF.md`](../onecycle/HANDOFF.md).

## 남은 한계
- MYELIN 은 내보내는 쪽이 아니다(findings 파일을 만들지 않는다).
- 다섯 플랫폼의 실제 내보내기 파일을 이어서 돌려 본 것은 아니다 — 스키마와 표본으로 검증했다.
- `date-time` 형식은 MYELIN 이 JSON Schema 보다 엄격하게 본다(`T` 가 있는 ISO 8601 만).
