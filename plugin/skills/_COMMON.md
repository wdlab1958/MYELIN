# MYELIN Skill 공통 규약 (모든 SKILL.md 가 참조)

1. **Vault 확인** — 작업 디렉터리에 `myelin.yaml` 이 있어야 한다. 없으면 "MYELIN Vault 가 아닙니다. `myelin init`" 을 안내하고 멈춘다.
2. **Level 확인** — `myelin skills --json` 으로 현재 Level 과 이 Skill 의 `enabled` 를 읽는다. `enabled: false` 면 쓰기를 시도하지 말고 "Level N 에서는 /<skill> 을 쓸 수 없습니다 (최소 Level M). myelin.yaml 의 level 은 사람이 올립니다." 라고만 답한다.
3. **쓰기 범위** — 각 Skill 에 적힌 디렉터리에만 새 파일을 만든다. 그 밖의 경로(특히 `10_Domains/`, `40_IP/`, `90_System/`, `myelin.yaml`, `CLAUDE.md`)는 절대 Write/Edit 하지 않는다. 변경이 필요하면 `_patches/` 제안(ADR-0006, Level ≥ 2). Guard 가 위반을 차단하며, 차단 메시지를 받으면 우회하지 말고 사람에게 보고한다.
4. **Frontmatter v2** — 템플릿은 `90_System/templates/<type>.md`. placeholder 를 모두 채운다: `id` = `YYYYMMDD-HHMM-<slug>` (slug 는 소문자·숫자·하이픈), `created` = 오늘, `origin: claude`, `status: draft`, `domain` 은 Vault 에 설정된 Domain ID 만, `classification` 은 Domain 의 기본값(모르면 `internal`), `share: false`, `confidence` 는 근거 수준에 맞게.
5. **검증** — 파일을 만든 뒤 `myelin doctor` 를 실행해 새 파일에 error 가 없음을 확인하고, 결과 요약(생성 파일 목록 + doctor 결과)을 보고한다.
6. **기밀** — `classification: confidential` 노트나 `40_IP/` 내용은 외부 LLM 컨텍스트로 보내지 않는다(요약·인용 금지). 로컬 LLM 라우팅은 `myelin.yaml llm.route`.
7. **커밋** — 사람이 요청한 경우에만 `git add <생성 파일> && git commit -m "[myelin:<skill>] <요약>"`. `git push`·`reset`·`checkout` 은 하지 않는다.
8. **용어** — `90_System/taxonomy.md` 의 대표 용어로 정규화하고, 새 용어는 본문에 `(용어 제안)` 으로 표시한다.
