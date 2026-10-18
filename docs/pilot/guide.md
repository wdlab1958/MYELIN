# MYELIN 파일럿 운영 가이드 (P7)

명세 §9.2 Pilot: 자원자 5~10명 + 팀별 챔피언, 3주. 목표는 **온보딩 15분 검증**과 **Org Pack 2종 확정**.

## 0. 시작 전 — 반드시 사람이 정할 것
| 항목 | 내용 | 결정 주체 |
|---|---|---|
| 정책 3종 (명세 §9.1) | 지식 소유권(업무 노트 vs 개인 연구, 퇴사 시 처리) · 외부 AI 사용 범위(고객 데이터·진단 결과의 Claude 처리) · 직무발명(40_IP 절차) | HR · 법무 · 보안 |
| Claude 플랜 | 회사 승인 플랜 사용 (개인 플랜 금지 여부) | 보안 |
| Commons 저장소 | 조직 내부 git 서버의 **비공개** 저장소 (`myelin commons init`) | 운영자 |
| 챔피언 | Domain별 1명 — Org Pack 확정, Commons PR 검토 | 팀장 |

정책이 정해지기 전에는 Commons를 켜지 않는다(`commons.enabled: false` 기본). 개인 Vault 사용만으로 파일럿을 시작할 수 있다.

## 1. 일정 (3주)
| 주 | 할 일 | 산출물 |
|---|---|---|
| 1주 | 60분 워크숍(`workshop.md`) → 각자 설치·온보딩 → 첫 verified 노트 | `results.yaml` 온보딩 시간 |
| 2주 | 매일 업무 1건 /ingest·/distill → Review Gate 승격. 챔피언은 Org Pack 초안 다듬기 | 주간 verified 수 (opt-in 지표) |
| 3주 | Commons 첫 공개(정책 합의된 경우만), 피드백 인터뷰 | `feedback.md`, Org Pack 2종 v0.2 |

## 2. 온보딩 시간 측정 — Gate 증거
Gate 기준: **5명 이상이 설치 시작 → 첫 verified 노트까지 15분 이내**.

1. 참가자는 설치를 시작할 때 시각을 적는다 (예: `2026-10-20T10:00`).
2. 온보딩 마법사에서 "로컬 git으로 기록"을 켠다 (기본값).
3. 첫 노트를 Review Gate에서 승격한 뒤:
   ```bash
   uv run python scripts/pilot_time.py ~/MyVault --install-start 2026-10-20T10:00
   ```
   출력된 분(숫자)만 운영자에게 알려 준다. 노트 내용은 전달하지 않는다.
4. 운영자는 `results.template.yaml` 을 `results.yaml` 로 복사해 기록한다. 이름 대신 `P01` 같은 코드를 쓴다.

> `results.yaml` 과 `feedback.md` 는 사람의 결과물이다. 운영자가 실제 측정값으로만 채운다 —
> Gate(`make gate P=7`)는 이 파일들이 있어야 통과한다.

## 3. 지표 (opt-in)
- 참가자가 Settings에서 "익명 지표 수집 동의"를 켜면 `myelin metrics <Vault> --out metrics.json` 으로 파일을 만든다.
- 내용을 본인이 확인한 뒤 운영자에게 직접 보낸다. MYELIN은 아무것도 자동 전송하지 않는다.
- 구간화된 숫자만 있다 (명세 §11.2, ADR-0009).

## 4. Org Pack 확정 (P7-T5)
- 공개 저장소의 `packs/org.security-consulting`, `packs/org.incident-response` 는 **예시 초안**이다.
- 챔피언이 조직 private 저장소로 복사해 Sub-MOC·용어·질문 은행·템플릿을 고친다 — 코드 수정 없이 YAML·Markdown만.
- Hub "Domain Packs" 화면의 편집기로 `pack.yaml` 을 검증한 뒤, Commons `registry/packs.yaml` 에 `status: pilot` 으로 등록한다.
- 확정 기준: 파일럿 참가자 3명 이상이 2주간 그 Pack의 Domain으로 verified 노트를 만들었다.

## 5. 안전 수칙 (참가자 안내용)
- Vault는 각자의 PC에. MYELIN 소스 폴더·공개 git 저장소 안에 만들지 않는다 (`myelin init` 이 막는다).
- 고객 자료 원본은 Vault에 넣지 않는다. 교훈만 비식별해서 적는다.
- `classification: confidential` 과 `40_IP/` 는 Claude로 보내지 않는다 (Guard·MCP가 막는다).
- Commons 공개는 자동 검사 + 본인 확인 5항목 + 별도 "보내기" 확인 + 챔피언 리뷰를 모두 거친다.
