# MYELIN v1.0 위협 모델 (STRIDE)

- 일자: 2026-10-18 · 범위: v1.0 (Personal 모드 + Team Commons opt-in)
- 기계 판독 목록: [`threats.yaml`](threats.yaml). Gate P8이 다음을 확인한다.
  - High 항목이 모두 `mitigated` 인지
  - `mitigated` 항목마다 실행되는 테스트가 증거로 붙어 있는지
  - STRIDE 6개 범주가 모두 다뤄졌는지

## 1. 지켜야 할 것 (자산)
| 자산 | 왜 |
|---|---|
| 개인 Vault의 노트 | 개인의 경험·판단. 업무 노트에는 고객 정보가 섞일 수 있다 |
| `40_IP/` · `classification: confidential` | 직무발명·고객 기밀 — 외부 AI로 나가면 안 된다 |
| verified 상태의 진실성 | AI 초안이 사람 검토 없이 "검증됨"이 되면 지식 품질이 무너진다 |
| `myelin.yaml` · `.claude/` | Claude의 권한(Level)과 기밀 경계(`llm.route`)를 정한다 |
| Commons의 공개 노트 | 조직 내부 공유물 — 고객 식별정보가 섞이면 안 된다 |

## 2. 신뢰 경계와 데이터 흐름
```
 [사람] ─브라우저─▶ Hub (127.0.0.1, 세션 토큰) ──▶ Vault 파일 · Vault git
                                     └──(제안: 로컬 브랜치)──▶ Commons clone ─(push, 별도 확인)─▶ 조직 git 서버
 [Claude Code] ─도구 호출─▶ Guard Hook ─허용 경로만─▶ Vault (ai-drafts, _patches …)
 [Claude Desktop 등] ─stdio─▶ MCP 서버 ─보호 노트 제외 색인─▶ 검색·읽기 (쓰기는 opt-in)
 [Pack 저장소] ─init/add-domain─▶ 템플릿·사전·질문 은행 복사 (Templater 허용 목록)
```

| 경계 | 바깥에 있는 것 | 기본 정책 |
|---|---|---|
| 기기 ↔ Anthropic | Claude 대화 | confidential·40_IP 는 보내지 않는다 (Guard·MCP·라우팅) |
| 기기 ↔ 조직 git | Commons 원격 | push 는 두 번째 사람 확인 뒤에만 |
| 브라우저 ↔ Hub | 다른 웹사이트, 같은 PC의 다른 사용자 | Host·Origin·의도 헤더·세션 토큰 |
| Vault ↔ Claude | 프롬프트 인젝션된 문서 | Level별 쓰기 경로, 사람 영역 Edit deny |
| Vault ↔ Pack | 남이 만든 Pack | Pack = 데이터. 실행 가능한 템플릿 표현식 거부 |

## 3. 결과 요약
| 범주 | 항목 | High | 조치 완료 | 수용 |
|---|---|---|---|---|
| S 위장 | S1, I5 | 1 | 2 | 0 |
| T 변조 | T1, T2, T3, T5, T6 | 3 | 4 | 1 |
| R 부인 | R1, R2 | 0 | 1 | 1 |
| I 정보 노출 | I1~I8 | 5 | 8 | 0 |
| D 서비스 거부 | D1, D2 | 0 | 2 | 0 |
| E 권한 상승 | E1, E2, E4 (+T1, T3, I7) | 2 | 3 | 0 |

**미조치 High 0건.** 일부 항목은 여러 범주에 걸쳐 있어(예: I7은 정보 노출과 권한 상승) 범주별 수의 합이 항목 수보다 크다.

## 4. 이번 점검(P8)에서 새로 찾아 고친 것
| id | 발견 | 조치 |
|---|---|---|
| **T3** | Pack 템플릿은 Obsidian Templater가 실행한다. 남의 Pack에 `<%* … %>`·`tp.user`·`tp.system`·`tp.web` 이 있으면 Vault를 연 순간 **임의 코드가 실행**될 수 있다 | Pack 로더가 템플릿 표현식을 허용 목록(`tp.date.now`, `tp.date.today`, `tp.file.title`)만 받는다. 위반이나 템플릿 안의 링크 파일은 Pack 검증 실패로 처리하고, invalid fixture #14를 추가했다 |
| **I5** | Hub는 127.0.0.1에만 열리지만 **같은 PC의 다른 OS 사용자**도 그 포트에 접속해 GET으로 노트를 읽을 수 있었다 | 실행마다 임의 세션 토큰을 만들어 터미널 링크로만 전달한다. 브라우저는 이를 HttpOnly·SameSite=Strict 쿠키로 바꾸고, `/api` 는 쿠키가 없으면 401 |

P6 독립 보안 검토의 6건(T2: stage 누수, CRLF 변형, 임시 파일 링크, glob pathspec, 대상 링크, 제어 문자)은 P6에서 이미 반영했다.

## 5. 수용한 위험
- **R2 — Guard 차단 이벤트를 기록하지 않는다.**
  - 지금은 차단 사유를 Claude에게 반환하기만 한다.
  - 개인 Vault에 감사 로그를 남기는 것 자체가 프라이버시 설계를 필요로 하므로 Backlog로 둔다.
- **T6 — 빌드 전용 의존성 경보.**
  - 대상: Tailwind 3이 쓰는 `braces`(DoS)와 esbuild dev 서버 CORS.
  - 사용자에게 배포되는 정적 번들에는 들어가지 않는다.
  - Vite 6+·Tailwind 4 전환은 Backlog로 둔다.
- **범위 밖.** 아래 위험은 OS·사용자 책임으로 본다.
  - 사용자 계정 자체의 탈취
  - 디스크 암호화 미사용
  - Obsidian 자체·다른 플러그인의 취약점
  - Claude 플랜의 데이터 처리 정책 (README Privacy model에 명시)

## 6. 다시 점검하는 방법
```bash
make gate P=8                                   # 위협 목록·증거 테스트·설치 측정
uv export --frozen --no-dev --no-emit-workspace --no-hashes > /tmp/req.txt && uvx pip-audit -r /tmp/req.txt
(cd packages/myelin-hub/web && npm audit --omit=dev)
```
2026-10-18 결과는 다음과 같다.
- **pip-audit:** 0건.
- **npm audit --omit=dev:** 0건.
- **npm audit (전체):** dev 의존성 경보만 있고, 이는 T6에서 수용했다.
