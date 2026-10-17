---
id: 20261018-0900-taxonomy
type: moc
domain: []
status: verified
origin: human
confidence: high
classification: internal
share: false
source: []
created: 2026-10-18
reviewed: 2026-10-18
tags: [taxonomy, system]
---
# Taxonomy — 용어 정규화 사전

> Pack의 `taxonomy.yaml`에서 생성. /distill 은 별칭을 대표 용어로 정규화한다. 수정은 Pack 또는 아래 개인 섹션에.

## myelin.core

| 용어 | 별칭 | Domain | 정의 |
|---|---|---|---|
| MYELIN | myelin, 미엘린 |  | Personal Knowledge OS. 쓸수록 빨라지는 나의 지식 신경망. |
| Vault | 볼트, 개인 Vault |  | 개인 소유 Obsidian Vault. Markdown + YAML 정본(SoR). |
| Domain | 도메인 |  | Pack에 선언된 지식 영역. 10_Domains/<ID>/ 폴더와 _MOC.md 를 가진다. |
| Domain Pack | Pack, 팩 |  | Domain 정의 YAML. Core / Reference / Org / Personal 네 유형. |
| MOC | Map of Content, 맵 |  | Domain 또는 주제의 진입 노트. 하위 노트를 구조화해 링크한다. |
| Fleeting | fleeting note, 임시 노트 |  | 가공 전 짧은 메모. 00_Inbox 에 머문다. |
| Literature | literature note, 문헌 노트 |  | 외부 출처(논문·문서·URL)의 핵심 주장과 인용 위치를 담은 노트. |
| Evergreen | evergreen note, 상록 노트, 원자 노트 |  | 하나의 개념을 자기 언어로 쓴 재사용 가능한 노트. verified 승격 대상. |
| Lesson | lesson learned, 교훈 |  | 경험에서 추출한 암묵지. /interview 의 산출물. |
| ADR | Architecture Decision Record, 설계 결정 기록 |  | 되돌리기 어려운 결정과 그 근거를 기록한 노트. |
| verified | myelinated, 검증 완료 |  | 사람이 Review Gate 에서 승격한 상태. Hub 에서 Lime 링으로 표시. |
| ai-draft | AI 초안, claude draft |  | origin claude 인 미검증 초안. 00_Inbox/ai-drafts 에만 생성된다. |
| Fail-closed | 페일클로즈드 |  | 판단 불가 입력은 거부. AI 쓰기는 ai-drafts·_patches 등 허용 경로만. |
| HITL | Human-in-the-loop, 사람 승인 |  | verified 승격·MOC 편집·Commons 공개는 사람만 수행한다. |
| Review Gate | 리뷰 게이트, 승격 게이트 |  | Hub 에서 ai-draft 를 verified 로 승격하는 유일한 경로. Git commit 으로 기록. |
| Commons | Team Commons, MYELIN Commons |  | 조직 공유 저장소. share true + verified + classification ≤ internal 노트만. |
| classification | 보안등급 |  | public / internal / confidential. confidential 은 로컬 LLM 라우팅·공개 불가. |

## brian.physical-ai

| 용어 | 별칭 | Domain | 정의 |
|---|---|---|---|
| LLMOps | LLM Ops, llmops | D1 | LLM 서비스의 평가·배포·관측·비용 운영 체계 |
| AX | AI Transformation, AI 전환 | D1 | 업무·조직을 AI 중심으로 재설계하는 방법론 |
| RAG | Retrieval-Augmented Generation, 검색증강생성 | D1 |  |
| Guardrail | 가드레일, guardrails | D1 | LLM 입력·출력에 대한 정책 강제 장치 |
| Prompt Injection | 프롬프트 인젭션, 프롬프트 주입 | D1 |  |
| WCET | Worst-Case Execution Time, 최악 실행 시간 | D2 |  |
| Hard Real-time | hard realtime, 하드 실시간 | D2 | 데드라인 위반이 곧 실패인 시스템 |
| HIL | Hardware-in-the-Loop, HILS | D2 |  |
| Safety-critical | 안전 필수, safety critical | D2 |  |
| ISR | Interrupt Service Routine, 인터럽트 핸들러 | D2 |  |
| Sim2Real | sim-to-real, 시뮬레이션-실기 전이 | D3 |  |
| MPC | Model Predictive Control, 모델 예측 제어 | D3 |  |
| VLA | Vision-Language-Action | D3 |  |
| Locomotion | 보행, 로코모션 | D3 |  |
| Domain Randomization | 도메인 랜덤화 | D3 |  |
| DFM | Design for Manufacturability, 제조성 설계 | D4 |  |
| Parametric Design | 파라메트릭 설계, parametric | D4 |  |
| Design Rule Engine | 설계 규칙 엔진, DRE | D4 |  |
| SolidWorks API | SW API, SldWorks API | D4 |  |
| Agentic CAD | AI×CAD, 에이전틱 CAD | D4 |  |

<!-- myelin:personal:start -->

## 개인 용어

<!-- myelin:personal:end -->
