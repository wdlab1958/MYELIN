# ADR-0013: Hub 도움말 어시스턴트(우측 하단 말풍선 챗봇) — 읽기 전용 · 로컬 LLM 전용

- 상태: Accepted · 일자: 2026-10-19 · Phase: P9
- 근거: Brian 요청 "Hub 우측 하단 말풍선 → 모달 → 질문에 답하는 챗봇, SSC Platform · ARGUS-X · WDLAB-LLMOps · AlphaForge 와 같은 방식". 정본 §2.3 Hub, §4.4 Personal 모드(localhost · 무인증), ADR-0009 Hub 쓰기 정책, ADR-0011 기밀 라우팅.
- 선행 사례의 공통 구조: 플로팅 버튼 → 모달 → `POST …/chat`(최근 대화) → 서버가 플랫폼 지식을 시스템 프롬프트로 주입 → 로컬 LLM(Ollama) → 답변. 입력 가드(인젝션·비밀값 거부), AI 자기고지, LLM 장애 시 200 으로 안내 폴백.

## 결정

### 1. 범위 — 안내만, 행위 없음
- 어시스턴트는 MYELIN 의 개념·사용법·절차와 **이 Vault 의 상태**(소유자·Level·Domain·KPI 이탈·검토 대기·관련 노트)를 답한다.
- 어떤 도구도 실행하지 않고 Vault 를 바꾸지 않는다. `POST /api/assistant/chat` 은 읽기이므로 ADR-0009 의 클릭 헤더를 **요구하지 않는다**(헤더가 있어도 무시). 승격·적용·공개 요청에는 "어느 버튼/Skill 로 사람이 하면 되는지" 만 안내한다.
- 대화는 서버에 저장하지 않는다(요청 본문에 최근 12개 메시지를 실어 보낸다).

### 2. 지식 — 내장 지식 파일 + Vault 검색 발췌
- 내장 지식은 코드가 아니라 패키지 데이터 `myelin_hub_api/assistant_kb.md`(한국어, 17절: 개요·폴더·Frontmatter·Domain/Pack·Level/Skill·Hub 화면·Review Gate·패치·Claude Code·기밀 라우팅·Commons·강도/KPI·환류·Obsidian·CLI·문제 해결·도우미 소개)이다. `## 제목` + `keywords:` 줄 + 본문. 질문의 키워드 부분 일치(짧은 ASCII 키워드는 단어 경계)로 상위 3절을 고른다.
- Vault 발췌는 기존 FTS 색인(`VaultIndex.search`)을 쓰되, 자연어 질문을 그대로 AND 검색하지 않고 조사·불용어를 뗀 검색어별로 찾아 합친다(여러 검색어에 걸린 노트 우선, 최대 5건, 발췌 280자). 답변에는 근거 노트가 Obsidian 링크로 붙는다.

### 3. LLM — 로컬 Ollama 전용, 기밀은 ADR-0011 과 같은 기준
- 엔드포인트는 `MYELIN_ASSISTANT_URL`(기본 `http://127.0.0.1:11434`), 모델은 `MYELIN_ASSISTANT_MODEL`(기본: 설치된 모델 중 exaone3.5:7.8b → qwen2.5:7b → … 순, 임베딩·비전 모델 제외), 제한 시간 `MYELIN_ASSISTANT_TIMEOUT`(기본 60초). Ollama `/api/chat`, stream 없음, temperature 0.2, 최대 700 토큰.
- **엔드포인트 호스트가 loopback(127.0.0.1 · localhost · ::1)이 아니면 EXTERNAL** 로 보고 `classification: confidential` 노트와 `40_IP/**` 를 검색·컨텍스트에서 제외한다. ADR-0011 의 "기밀은 외부 LLM 에 가지 않는다" 를 Hub 에도 같은 판정으로 적용한 것이다(`/api/assistant/status.local` 로 확인).
- 답변이 한자 줄로 흐르면(qwen 계열) 그 줄을 제거하고 알린다.

### 4. 폴백 — 지식 기반(kb) 모드
- Ollama 연결 실패·모델 없음·호출 실패는 **200 으로** 내장 지식 절(상위 2절)과 관련 노트를 그대로 답한다(`mode: "kb"`, `notice` 에 사유). 오프라인에서도 쓸 수 있고 e2e 는 이 모드로 고정해 결정적이다(`global-setup.ts` 가 `MYELIN_ASSISTANT_URL=http://127.0.0.1:9`).
- 헤더 칩이 모드를 텍스트로 보여 준다: "로컬 LLM · <모델>" / "지식 기반 모드".

### 5. 입력 가드
- 시스템 프롬프트·내부 지시문 출력, 비밀값(API 키·토큰·환경변수·비밀번호), 지시 변경("이전 지시 무시", "너는 이제"), 주민등록번호·계좌번호 요청은 LLM 호출 전에 거부 문구로 답한다(`mode: "refused"`). 개념 설명(보안·Guard·기밀 등급)은 거부 대상이 아니다.
- 메시지 40개·본문 4,000자 상한(422), 마지막 메시지는 user(400).

### 6. UI
- `components/Assistant.tsx`: 우측 하단 고정 버튼(말풍선 아이콘 + "도우미" 텍스트) → `role="dialog"` 모달(배경 클릭·ESC·닫기, 한글 IME 조합 중 Enter/ESC 무시), 환영 메시지 + 추천 질문 4개, 답변의 근거 노트 목록, 하단 고지 "AI 도우미는 안내만 합니다". Emboss 토큰만 사용, Primary 버튼 없음(화면당 1개 규칙 유지). Review 의 토스트는 말풍선 위로 올렸다.

## 결과
- 새 파일: `assistant.py`, `assistant_kb.md`, `components/Assistant.tsx`; `app.py` 에 `GET /api/assistant/status`, `POST /api/assistant/chat`.
- 테스트: `packages/myelin-hub/api/tests/test_assistant.py`(지식 파일 형식·절 매칭·검색어 추출·loopback 판정·모델 선택·한자 제거·인젝션·kb/LLM 모드·폴백·기밀 제외·환경 설정) + e2e "도움말 챗봇" 시나리오(위치·모달·답변·인용 링크·읽기 전용·ESC).
- 위협 모델 T22 추가.

## 잔여 위험 · 대안
- 7B 로컬 모델은 내장 지식 밖을 지어낼 수 있다 → 프롬프트가 "지식에 없으면 없다고 말하라" 와 '근거:' 줄을 요구하고, kb 모드 답변은 항상 원문 그대로다. 중요한 결정은 가이드·`myelin doctor` 로 확인한다(하단 고지).
- Claude API 등 외부 LLM 사용은 채택하지 않았다: Hub 는 무인증 localhost 서비스이고, 외부 전송은 ADR-0011 의 기밀 라우팅을 다시 열게 된다. 필요해지면 `llm.default: claude` 와 연계해 EXTERNAL 판정(기밀 제외)을 그대로 적용하는 어댑터를 추가한다.
- 대화 저장·피드백(👍/👎) 집계는 범위 밖(Backlog).
