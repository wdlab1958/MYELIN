# MYELIN 정본 Rev 2.1 부록 — 설계 철학 갭 보완 요구사항 (2026-10-18)

본 부록은 Rev 2.0 을 대체하지 않고 **추가**한다. 2026-10-18 평가에서 드러난 "설계 철학 ↔ 구현" 갭을 닫기 위해, 철학의 세 의도를 각각 장치(device)로 요구사항화한다. 번호는 Rev 2.0 의 절 번호를 잇는다.

## §11.3 복리 지표 — "쓸수록 빨라진다" 를 재는 장치 (의도 1)

Rev 2.0 §11.1 의 KPI 는 모두 양·위생 지표였다. 다음을 **필수** 지표로 추가한다.

| KPI | 정의 | 목표 |
|---|---|---|
| `reuse_ratio` | verified 노트 중 강도 ≥ 2(아래 §11.4) 인 비율 | ≥ 0.30 |
| `reuse_lag_days` | `80_Outputs/**` 산출물의 `created` − 재료 노트의 `created` 의 중앙값 | ≤ 30 |
| `compose_sources_avg` | 산출물 1건당 verified 재료 노트 수의 평균 | ≥ 3 |

Hub Dashboard 는 세 지표와 목표 판정(달성/목표 이탈)을 표시한다. 익명 지표 페이로드(§11.2)에는 개수·비율만 포함한다.

## §11.4 미엘린 강도 — verified 는 시작이지 끝이 아니다 (의도 1)

노트의 **강도(strength)** 를 0~3 으로 정의한다. 0 = verified 아님, 1 = verified, 2 = 피인용(inbound) ≥ 2 또는 산출물 재료로 1회 이상 사용, 3 = Commons 에서 1회 이상 인용되었거나 (inbound ≥ 5 이고 산출물 재료 ≥ 2). 임계값은 ADR-0012 에 둔다. Hub 는 노트 목록·검색 결과에 강도를 **텍스트 라벨**로 표시하고, Dashboard 에 강도 분포를 보인다. 링의 색만으로 구분하지 않는다(§8.3 가드레일 4).

## §7.3 환류 — 순환의 되돌아오는 반쪽 (의도 1)

`/compose` 산출물은 `## 환류 후보` 절을 가진다(재료 노트에 없어서 새로 정리한 주장·교훈·결정). `/distill <산출물 경로>` 는 이 절과 본문에서 lesson/evergreen/adr 초안을 `00_Inbox/ai-drafts/` 에 만든다(`source` 에 산출물 링크, `tags: [refeed]`). `/review` 는 환류 후보가 있으나 되돌아오지 않은 산출물을 "환류 대기" 로 보고한다. 쓰기 범위·Level 은 기존 Skill 을 따른다(새 Skill 을 추가하지 않는다).

## §7.4 승격은 읽은 사람이 한다 (의도 2)

Hub Review Gate 의 Promote 는 **본문을 연 뒤에만** 활성화된다(읽음 확인 장치). 승격률 상한(§11.1 0.70) 이탈은 Dashboard 에 "목표 이탈" 로 표시한다.

## §4.3 기밀 라우팅 장치화 (의도 2·3)

세션은 `MYELIN_LLM=local` 환경변수가 있을 때만 **로컬**이다. 외부 세션의 Claude Code 는 `40_IP/**` 와 `classification: confidential` 노트를 Read/Grep/Glob/Write 할 수 없다(PreToolUse Guard + settings.json 2차 방어). MCP 서버는 로컬 프로세스가 아니면 `mcp.expose_confidential: true` 를 무시한다. `myelin.yaml llm.route` 는 이 장치의 설정이지 문장이 아니다. 상세·잔여 위험은 ADR-0011.

## §3.1 Claude Code 밖의 커밋도 장치가 본다 (의도 2)

`myelin init` 은 Vault git 저장소에 pre-commit 훅(`90_System/hooks/pre-commit` → `.git/hooks/`)을 설치한다. 훅은 `myelin doctor --staged` 로 스테이징된 노트만 검사해, `origin: claude` 노트가 Level 허용 범위 밖에 있거나 `reviewed` 없는 verified 라면 커밋을 거부한다. 기존 Vault 는 `myelin doctor --install-hook` 으로 설치한다. 이로써 Obsidian·다른 AI 도구에서 온 변경도 커밋 시점에 같은 정책을 거친다.

## §9.3 기여가 평판이 되는 집계 (의도 3)

Commons 노트의 `author`·`published_from` 은 실명으로 보존된다(Rev 2.0 §9.1). 여기에 **인용 집계**를 추가한다: 각 Vault 는 익명 지표에 `cited_commons_ids`(인용한 Commons 노트 id 목록)를 보내고, Commons 집계는 노트별 `reuse`(인용 합)와 `top_contributors`(author 별 published·cited 수)를 낸다. Hub 의 Commons 제안은 체크 한 번으로 push 와 PR 까지 간다(§9.1 완성). `commons.remote` 는 clone 의 origin 으로 사용한다.

## §9.4 두 정체성의 명시 (의도 3)

Hub 는 "Commons 기여 = 실명, 지표 = owner 해시 익명" 임을 Review Gate 와 Settings 에서 문장으로 밝힌다. 조직은 개인 Vault 를 열람하지 않는다는 보장은 현재 "Hub 는 localhost 전용" 에 의존하며, Team 모드 도입 시 본 부록을 개정한다.
