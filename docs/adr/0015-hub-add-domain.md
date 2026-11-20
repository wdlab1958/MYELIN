# ADR-0015: Hub 에서 Domain 추가 — `POST /api/domains`

- 상태: Accepted · 일자: 2026-11-21 · Phase: P9
- 근거: Brian 보고(2026-11-21) — Hub 도우미가 "Domain Packs › Add Domain › Create" 를 안내했으나 그런 메뉴가 없었다. Domain 추가는 CLI `myelin add-domain <ID>` 로만 가능했고, Hub 에서 Pack 을 저장해도 Vault 의 Domain 은 늘지 않았다. Brian 결정: "Hub 에 버튼 구현". 정본 §5.4(3+1), ADR-0009(Hub 쓰기 정책), Engineering Rule "Pack 은 데이터".

## 결정

1. **ADR-0009 §2 의 쓰기 동작에 `add_domain` 을 더한다(7종).** `POST /api/domains` `{id, pack?}` — `X-Myelin-Intent: user-click` 필수(없으면 403), 정확히 하나의 commit `[myelin:add-domain] <ID>`.
2. **코드 경로는 CLI 와 같다.** `myelin_core.scaffold.add_domain` 을 그대로 호출한다(MOC · Domain 템플릿 · taxonomy · CLAUDE.md · `myelin.yaml` `domains.extra` · Obsidian 색 그룹). Hub 는 Domain 을 *정의*하지 않는다 — Pack 에 선언된 Domain 만 추가할 수 있다. Domain 정의는 여전히 Pack(데이터)이고, 새 Domain 에 코드 변경은 없다.
3. **화면은 두 단계.** ① Domain Packs 편집기에서 개인 Pack 저장(선언) → ② Pack 카드의 `+ Domain 추가 · <ID>` 버튼(추가). 버튼은 "Pack 에 선언됐지만 Vault 에 없는 Domain" 마다 하나(`GET /api/packs` 의 `domains[].configured`). ID 자유 입력 칸은 두지 않는다 — 서버가 아는 선언만 고르게 해 오타·경로 조작 여지를 없앤다.
4. **Fail-closed · 덮어쓰기 금지.** ID 는 `DOMAIN_ID_RE` 만(422). 선언한 Pack 없음 404 · 이미 설정됨 / 여러 Pack 이 선언(Pack 미지정) / `10_Domains/<ID>/_MOC.md` 가 이미 있음 409 · 로더가 거부한 Pack 422. 이 경우 아무것도 쓰지 않는다. 기존 노트는 건드리지 않는다.
5. **All-or-nothing.** 다른 쓰기와 같이 직렬화(`_serialised`)하고, 중간 단계나 commit 이 실패하면 스냅샷한 파일을 되돌리고 이 요청이 만든 파일(MOC · `<ID>-*` 템플릿 · 빈 Domain 폴더)을 지운 뒤 설정을 다시 읽는다.
6. **스테이징은 건드린 경로만**(ADR-0009 §4). CLI `add-domain` 의 `git add -A`(formal F3, Backlog)는 이 ADR 범위 밖이며 그대로 남는다 — Hub 경로는 F3 을 갖지 않는다.
7. **Level 과 무관.** Level 은 AI 자율성 단계이고 Domain 추가는 사람의 클릭이다(Settings 저장과 같은 급).

## 결과
- 도우미 지식(`assistant_kb.md`)을 실제 화면(두 단계, 버튼 이름)으로 고치고 "없는 버튼"을 명시했다.
- 테스트: API 3건(1 commit·무관 파일 미포함·재시작 없이 반영 / 거부 시 무변경 / commit 실패 롤백), 클릭 헤더 감사에 추가, e2e 1건.
- 위협 모델 T23.
- 제거(Domain 삭제)는 제공하지 않는다 — 노트가 딸린 되돌리기 어려운 동작이라 별도 결정이 필요하다.
