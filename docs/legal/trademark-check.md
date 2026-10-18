# 상표 · 이름 확인 기록 — MYELIN (P8-T5, 명세 §2.2·§12)

```yaml
checked: 2026-10-18
checked_by: Claude (웹 검색 사전 조사)        # 법적 판단 아님
reviewed_by:                                    # ← 사람(Brian 또는 변리사)이 KIPRIS 확인 후 이름·날짜 기입
decision:                                       # 유지(MYELIN) | 결합형(MYELIN KOS 등) | 대안(MindForge)
```

> 이 문서는 **사전 조사 기록**이다. 상표 등록 가능성·침해 위험 판단은 사람(변리사)의 일이다.
> Gate P8의 `HUMAN trademark/name clearance reviewed` 항목은 위 `reviewed_by` 가 채워져야 통과한다.

## 1. KIPRIS (한국) — 제9류 · 제42류
**자동 확인 불가.** KIPRIS 웹(www.kipris.or.kr)은 스크립트 기반 검색이라 이 작업 환경에서 조회하지 못했다.
KIPRIS Plus Open API는 발급 키가 필요하다. 아래 절차로 사람이 확인하고 결과를 표에 적는다.

| 검색어 | 일치 방식 | 상품분류(TC) | 행정상태 | 결과 (건수 · 출원인 · 상태) |
|---|---|---|---|---|
| MYELIN | 완전일치 | 09 (소프트웨어) | 전체 | |
| MYELIN | 완전일치 | 42 (SaaS·IT 서비스) | 전체 | |
| MYELIN | 부분일치 | 09, 42 | 전체 | |
| 마이엘린 · 미엘린 · 마이얼린 | 부분일치 | 09, 42 | 전체 | |
| MYELIN KOS (대안) | 완전일치 | 09, 42 | 전체 | |
| MindForge · 마인드포지 (대안) | 완전일치 | 09, 42 | 전체 | |

절차: 지식재산정보 상세검색 → 권리별검색 → **상표** 탭 → 상표명칭(TN) + 상품분류(TC) AND →
행정상태 "전체"(출원 중 포함) → 결과마다 외관·호칭·관념 유사성, 지정상품·유사군, 상태 확인.
간이 확인: 헬프미 무료 상표 검색(trademark.help-me.kr/marksearch) — 최종 판단은 KIPRIS 원문으로.

## 2. 해외·시장 사전 조사 (웹 검색, 2026-10-18)
| 이름 | 무엇 | 분류 근접도 | 메모 |
|---|---|---|---|
| **Myelin (myelin.io)** | Kubernetes 위 ML 워크로드 플랫폼, GitHub `myelinio` 조직 · CLI `myelin` | **높음** (제9·42류 소프트웨어, 같은 CLI 이름) | myelin.io 도메인은 현재 판매 중 표시 — 활동 여부 불명확. G2·Crunchbase 프로필 존재 |
| **Neuromyelin** | 업무 정보 캡처·질의응답 지식관리 SaaS | **높음** (지식관리 — 같은 시장) | Capterra 등 등록. 제조사·국가 정보 없음 |
| Myelin AI (`myelinai.github.io`), Myelin Research Group (`github.com/myelin-ai`) | AI 솔루션 소개 페이지 · 연구 그룹 | 중간 | 상표 출원 여부 미확인 |
| 마이엘린(미엘린) | 신경 수초 — 일반 의학 용어 | — | 일반명사라 식별력 판단 대상 |

## 3. GitHub 조직명
- 이 프로젝트: `github.com/wdlab1958/MYELIN` (WDLAB 조직 아래 저장소) — 현재 이름으로 운영 가능.
- `github.com/myelin`(단독 조직·사용자명): 이 작업 환경의 GitHub 접근 범위 밖이라 확인하지 못함 → 사람 확인 필요.
- 이미 쓰이는 이름: `myelinio`(myelin.io), `myelin-ai`(연구 그룹).
- CLI 이름 `myelin` 은 myelin.io의 CLI와 겹친다 → PyPI 패키지명·명령어 충돌 가능성도 같이 확인할 것 (`pip index versions myelin`).

## 4. 판단을 위한 메모 (권고 아님)
- 같은 분류(소프트웨어·지식관리)에 "Myelin" 계열 이름이 최소 2건 보인다 → **KIPRIS 확인 전에는 조직 외부 배포·홍보를 미루는 것이 안전**하다.
- 명세 §2.2의 대안 순서: ① MYELIN 유지 ② 결합형(MYELIN KOS 등) ③ MindForge.
- 공개 저장소는 이미 MYELIN 이름으로 공개되어 있다. 이름을 바꾸게 되면 저장소 이름·CLI·Pack 이름 `myelin.core`·플러그인 이름이 함께 바뀐다 (v1.x 마이그레이션 필요).

## 출처
- KIPRIS 검색 방법 — 헬프미: https://www.help-me.kr/blog/article/kipris-trademark-search-guide/
- myelin.io 예제 저장소: https://github.com/myelinio/myelin-examples · GitHub 조직: https://github.com/myelinio
- Myelin.io 리뷰(G2): https://www.g2.com/products/myelin-io/reviews · Crunchbase: https://www.crunchbase.com/organization/myelin-io
- Neuromyelin (Capterra): https://www.capterra.co.uk/software/1110498/Neuromyelin
- Myelin AI: https://myelinai.github.io/ · Myelin Research Group: https://github.com/myelin-ai
- myelin.io 도메인: https://myelin.io/
