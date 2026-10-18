# Obsidian 기능 대 MYELIN(Obsidian + Claude) 기능 비교표

- 기준: Obsidian 1.x 코어 플러그인·공식 서비스(Sync, Publish)와 대표 커뮤니티 플러그인 / MYELIN v1.2.0(정본 Rev 2.0 + Rev 2.1 부록).
- 전제: MYELIN 은 Obsidian 을 **대체하지 않는다**. Obsidian 은 그대로 편집기·탐색기이고, MYELIN 은 그 Vault 위에 **구조(Vault 표준·Pack) · AI 작업(Claude Skill) · 통제(Guard·Review Gate·git) · 측정(KPI·강도) · 공유(Commons)** 층을 얹는다. Obsidian 플러그인은 만들지 않으며(정본), 연동은 테마와 frontmatter 규약으로 한다.
- "관계" 열: **그대로** = Obsidian 기능을 그대로 쓴다 · **확장** = Obsidian 기능 위에 규약·자동화를 더한다 · **대체** = Obsidian 커뮤니티 플러그인이 하던 일을 MYELIN 장치가 맡는다 · **신규** = Obsidian 에 없는 기능.

## 1. 기록과 구조

| 기능 영역 | Obsidian | MYELIN (Obsidian + Claude) | 관계 |
|---|---|---|---|
| 노트 형식 | 로컬 Markdown 파일, 폴더 자유 | 같은 Markdown. 폴더 표준 9종(`00_Inbox … 99_Archive`, `_patches`)과 노트 유형 9종 템플릿(`90_System/templates/`) | 확장 |
| 속성(Properties) | frontmatter 를 UI 로 편집, 형식 자유 | **Frontmatter v2** 스키마(id·type·domain·status·origin·confidence·classification·share·source·created·reviewed·tags). `myelin doctor` 가 검증, 미지 필드는 보존(ADR-0003) | 확장 |
| 템플릿 | 코어 Templates(치환 변수 소수), 커뮤니티 Templater | 유형별 템플릿을 Pack 이 제공, Claude Skill 이 템플릿대로 초안 생성. 사람이 수동으로 쓸 때는 Obsidian Templates 그대로 | 확장 |
| 데일리 노트 / 저널 | 코어 Daily notes | `50_Journal/` 표준 + `/myelin:review` 주간 리뷰 노트 자동 초안 | 확장 |
| 고유 ID | 코어 Unique note creator(시간 접두) | `id: YYYYMMDD-HHMM-slug` 규약, 중복 id 는 doctor 오류 | 확장 |
| 도메인 분류 | 폴더·태그로 사용자가 임의 구성 | **3+1 Domain 규칙**(Primary·Research·Growth + extra)과 **Pack(YAML)** 로 선언. Domain 추가에 코드 변경 없음, Sub-MOC 자동 생성 | 신규 |
| 캡처(외부 자료) | Web Clipper(브라우저 확장), 수동 복사 | `/myelin:ingest <파일·URL>` 이 literature 초안을 ai-drafts 에 생성(출처·요약·frontmatter 포함) | 확장 |
| 경험·교훈 기록 | 자유 기록 | `/myelin:interview` 가 Pack 의 인터뷰 질문 은행으로 lesson 노트 초안 생성 | 신규 |

## 2. 연결과 탐색

| 기능 영역 | Obsidian | MYELIN (Obsidian + Claude) | 관계 |
|---|---|---|---|
| 위키링크·백링크 | `[[링크]]`, Backlinks·Outgoing links 패널 | 같은 링크 규약 사용. 색인이 링크를 해석해 고아 노트·피인용 수·**미엘린 강도** 계산 | 확장 |
| MOC(Map of Content) | 사용자가 직접 작성 | Pack 이 Domain 별 `_MOC.md` 와 Sub-MOC 자동 생성, `/myelin:link` 가 MOC 갱신을 `_patches/` 제안으로 작성(사람이 Hub 에서 Apply) | 확장 |
| 그래프 뷰 | 코어 Graph view(전체·로컬) | 그래프는 Obsidian 그대로. Hub "My Domains" 는 Domain Orb·Sub-MOC 단위의 요약 뷰 | 그대로 + 보완 |
| 검색 | 코어 Search(전문·속성 연산자), Quick switcher | Obsidian 검색 그대로. 추가로 SQLite FTS5 색인(Hub 검색 API, MCP `search_notes`)으로 Claude 가 Vault 를 검색 | 확장 |
| 데이터베이스 뷰 | 코어 Bases(1.9+), 커뮤니티 Dataview | Hub 의 노트 표(status·origin·강도 필터)와 `myelin stats`. Dataview 수준의 임의 질의는 제공하지 않음 | 부분 대체 |
| 캔버스·슬라이드·Excalidraw | 코어 Canvas·Slides, 커뮤니티 Excalidraw | 해당 없음(Obsidian 그대로) | 그대로 |
| Obsidian URI | `obsidian://open`, `obsidian://new` | Hub 의 노트 제목·Sub-MOC 버튼이 URI 로 Obsidian 을 연다(MOC 가 없으면 새로 만들기) | 그대로 활용 |

## 3. AI

| 기능 영역 | Obsidian | MYELIN (Obsidian + Claude) | 관계 |
|---|---|---|---|
| AI 기본 내장 | 없음(코어에 AI 없음) | Claude Code 플러그인 Skill 7종: `/ingest /distill /interview /review /link /compose /ip-scan` | 신규 |
| AI 플러그인 | 커뮤니티(Copilot, Smart Connections 등): 채팅·요약·유사 노트 추천, Vault 어디든 쓸 수 있음 | AI 는 **`00_Inbox/ai-drafts/` 등 Level 별 허용 경로에만** 쓴다. 그 밖은 Guard 가 차단(exit 2). 승격은 사람 | 대체(통제형) |
| 원자 노트 분해 | 커뮤니티 Note refactor, 수동 | `/myelin:distill` 이 Inbox 노트를 주장 단위 evergreen 초안으로 분해, 중복 검사·용어 정규화 | 신규 |
| 산출물 작성 | 수동 | `/myelin:compose` 가 verified 노트만 재료로 설계서·제안서·보고서 초안을 `80_Outputs/drafts/` 에 작성, 근거 링크 필수 | 신규 |
| 환류 | 없음 | 산출물의 `## 환류 후보` 를 `/myelin:distill <산출물>` 이 원자 노트로 되돌림(Rev 2.1 §7.3) | 신규 |
| 외부 AI 에 Vault 노출 | 플러그인 설정에 따라 전체 노출 가능 | MCP 서버(읽기 전용 기본, `write_draft` opt-in). `40_IP/**`·confidential 은 `MYELIN_LLM=local` 세션에서만 접근(ADR-0011) | 대체(통제형) |
| 단계적 권한 | 없음 | `myelin.yaml level` 0~3 에 따라 Skill·허용 경로 누적 개방 | 신규 |

## 4. 품질과 검증

| 기능 영역 | Obsidian | MYELIN (Obsidian + Claude) | 관계 |
|---|---|---|---|
| 상태 관리 | 태그·속성으로 사용자 규약 | `status: draft → unverified → verified → deprecated` 표준. verified 는 **Hub Review Gate 의 사람 클릭**으로만, 본문을 읽은 뒤에만 승격 가능 | 신규 |
| 검사 도구 | 없음(링크 깨짐은 UI 표시 정도) | `myelin doctor` 규칙 8종(스키마·fail-closed·고아·기밀-공유·깨진 링크·중복 id·domain·시간 순서) + `--staged` pre-commit | 신규 |
| 패치 제안 | 없음 | `_patches/*.patch.md`(append·replace·frontmatter), Hub 미리보기(diff)·digest 검사 후 Apply | 신규 |
| 이력 | 코어 File recovery(스냅샷), 커뮤니티 Obsidian Git | 모든 쓰기 = git commit(`[myelin:<skill>]` 접두), Hub Dashboard 에 최근 커밋, 작업 트리 항상 깨끗함을 테스트로 보장 | 대체(Obsidian Git) |
| 품질 지표 | 커뮤니티 Word count 등 | KPI 9종(Inbox 체류·주간 verified·승격률·고아·cross-domain·산출물·재사용 비율·재투입 소요일·재료 수)과 목표 판정, 노트별 **myelin ×1~3** | 신규 |

## 5. 보안과 거버넌스

| 기능 영역 | Obsidian | MYELIN (Obsidian + Claude) | 관계 |
|---|---|---|---|
| 저장 위치 | 로컬 파일(선택적 Sync E2E 암호화) | 로컬 파일 그대로. Hub 는 localhost 전용 | 그대로 |
| 기밀 등급 | 없음 | `classification: public/internal/confidential`, `40_IP/` 폴더. confidential+share 는 doctor 오류·커밋 거부 | 신규 |
| AI 쓰기 통제 | 없음 | PreToolUse Guard(Write/Edit/NotebookEdit·Bash·Read/Grep/Glob), settings.json 2차 방어, Vault pre-commit 훅 | 신규 |
| 사람 승인 | 없음 | Hub 쓰기는 `X-Myelin-Intent: user-click` 헤더 필수, 동작마다 커밋 | 신규 |
| 위협 모델 | 없음 | `docs/security/threat-model.md`(T01~T21), 적대 테스트 500여 건 | 신규 |

## 6. 협업과 공유

| 기능 영역 | Obsidian | MYELIN (Obsidian + Claude) | 관계 |
|---|---|---|---|
| 동기화 | Obsidian Sync(유료), 또는 git·클라우드 드라이브 | 개인 Vault 는 git. Sync 와 병행 가능(`.myelin/` 은 제외 권장) | 그대로 |
| 공개 | Obsidian Publish(유료, 사이트 발행) | **Commons**: `share: true` + 비식별 검사 + 사람 확인 → `publish/<id>` 브랜치 → push/PR(opt-in). 작성자·원 id 실명 보존, 인용 집계·`top_contributors` | 대체(조직 내부용) |
| 팀 지식 구조 | 없음(각자 Vault) | Org Pack(`a3.*`)·Reference Pack·개인 Pack(`me.*`), Pack Registry·제안 | 신규 |
| 지표 공유 | 없음 | opt-in 익명 지표(owner 해시·개수·id 목록만) | 신규 |
| 협업 편집 | 없음(Sync 는 파일 동기화) | 없음(의도적으로 개인 소유 유지) | 동일 |

## 7. 화면·테마·설치

| 기능 영역 | Obsidian | MYELIN (Obsidian + Claude) | 관계 |
|---|---|---|---|
| 테마 | 커뮤니티 테마·CSS snippets | **MYELIN Emboss** 테마(`design/tokens.json` 단일 원천 → emboss.css·Tailwind·Obsidian 테마), frontmatter `cssclasses` 로 verified 링·ai-draft glow 표시 | 확장 |
| 대시보드 | 없음(Dataview 로 구성 가능) | Hub: Dashboard(KPI·강도·커밋) · My Domains · Review Gate · Domain Packs · Settings | 신규 |
| 온보딩 | Vault 만들기 | 온보딩 마법사(3+1 역할 배정, 직접 Domain 정의) 또는 `myelin init`, 설치 스크립트, 첫 verified 까지 15분 측정 | 신규 |
| 모바일 | iOS·Android 앱 | Vault 는 모바일 Obsidian 에서 그대로 열림. Hub·Claude Skill 은 데스크톱 전용 | 그대로(부분) |
| 플러그인 생태계 | 2,000+ 커뮤니티 플러그인 | 모두 그대로 설치 가능. 단 Vault 를 쓰는 AI 플러그인은 Guard 밖이므로 pre-commit 훅이 커밋 시점에 검사 | 그대로 + 통제 |

## 8. 한 줄 요약

Obsidian 이 **쓰고 연결하고 보는 도구**라면, MYELIN 은 그 위에 **AI 가 초안을 만들고 사람이 승격하며, 그 과정이 git 으로 남고, 재사용이 측정되며, 선택한 것만 조직과 나누는 운영체계**를 얹는다. Obsidian 의 편집·그래프·검색·동기화·모바일·플러그인은 그대로 쓰고, 커뮤니티 플러그인에 의존하던 Git·AI·대시보드 기능은 통제된 형태로 대체한다.
