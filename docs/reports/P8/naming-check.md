# MYELIN 이름 확인 기록 (P8-T5) — 상표 · 도메인 · GitHub 조직명

- 일자: 2026-10-18 · 수행: Claude Code (자동 조회) · **법률 자문이 아니다**. 사내 배포 전 변리사 검토 권고.
- 정본 §2.2: "KIPRIS 상표 검색(제9류 소프트웨어, 제42류 SaaS)과 도메인·GitHub 조직명 확인을 P8 체크리스트에 포함. 충돌 시 대안은 MYELIN 을 유지한 결합형(예: MYELIN KOS) 또는 MindForge."

## 1. 상표

| 조회 | 결과 | 비고 |
|---|---|---|
| KIPRIS (국내, 제9류·제42류) | **직접 조회 미완료** — KIPRIS 검색은 대화형 웹 UI 라 자동 조회로 결과를 확보하지 못함. 웹 검색에서는 "MYELIN/미엘린" 국내 출원 기록을 찾지 못함 | **사람이 kipris.or.kr 에서 "MYELIN"·"미엘린" 을 제9류·제42류로 직접 검색하고 출원인·출원일을 이 표에 기입할 것** |
| USPTO (미국) | **충돌 가능성 있음** — "MYELIN" 명칭의 **진행 중인 출원**(Granica Computing, Inc., 2026-08-19 출원, 심사 중)이 확인됨. 별도 Justia 기록은 제9류(데이터 처리 장치·컴퓨터 등) 지정 | 미국 소프트웨어 분야에서 동일 명칭 선출원이 존재. 사내 배포(국내)에는 직접 영향이 작지만, 해외 공개·오픈소스화 시 리브랜딩 리스크 |

출처: [USPTO/trademarkregistration.app 50060430](https://trademarkregistration.app/Trademark/Details/50060430) · [Justia MYELIN 90255133](https://trademark.justia.com/902/55/myelin-90255133.html) · [KIPRIS 안내(mondaq)](https://www.mondaq.com/intellectual-property/1843242/korean-patent-search-a-complete-guide-to-kipris-and-koreas-patent-database)

## 2. 도메인 (dig NS + whois, 2026-10-18)

| 도메인 | 상태 |
|---|---|
| myelin.io | **등록됨** (NameBake LLC) |
| myelin.ai | **등록됨** (101domain) |
| myelin.kr | **등록됨** (NS gabia) |
| myelin.dev | **등록됨** (NS cloudflare) |
| myelinos.com | **등록됨** (Namecheap) |
| myelin-os.dev | NS 없음 — **등록 가능성 있음** (레지스트라에서 확인) |

## 3. GitHub

| 이름 | 상태 |
|---|---|
| github.com/myelin | **사용 중** (개인 계정, 뉴질랜드 출신 엔지니어, 공개 저장소 67개) |
| github.com/wdlab1958/myelin | 정본 §10.1 의 저장소 경로 — 조직이 아닌 개인 계정 하위 저장소이므로 **조직명 충돌 없음** |

## 4. 판정과 권고
- **사내 배포(Team 모드, 비공개 저장소)**: 그대로 **MYELIN** 사용 가능. 국내 상표 출원 여부는 KIPRIS 직접 조회 후 확정.
- **대외 공개·상표 출원 시**: 미국 선출원(Granica)과 주요 도메인 점유를 고려해 정본 §2.2 의 대안 적용 — 결합형 **"MYELIN KOS"**(Knowledge OS) 또는 **"WDLAB MYELIN"** 으로 출원·도메인(`myelin-os.dev` 등) 확보. 최종 대안은 MindForge.
- 릴리스 노트 "알려진 제약" 에 "브랜드명은 사내용 가칭, 대외 공개 시 재검토" 를 명시한다.
