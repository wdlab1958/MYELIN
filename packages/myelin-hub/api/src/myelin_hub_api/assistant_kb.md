# MYELIN 도우미 내장 지식 (한국어)

> `## 제목` 한 절 = 하나의 지식 단위. 첫 줄 `keywords:` 는 질문 매칭용(소문자 부분 일치). 본문은 LLM 시스템 프롬프트와
> 지식 기반(kb) 모드 답변에 그대로 쓰인다. 출처: docs/guides/user-guide.md · README · CLAUDE.md · ADR-0005/0006/0009~0012.
> 수정하면 `packages/myelin-hub/api/tests/test_assistant.py` 가 절 형식(keywords 줄·본문)을 검사한다.

## MYELIN 개요와 설계 철학
keywords: myelin, 미엘린, 철학, 개요, 소개, 무엇, 뭐, 구성, 아키텍처, 원리, 목적, 의도

MYELIN 은 '쓸수록 빨라지는 나의 지식 신경망'을 목표로 하는 Personal Knowledge OS 다. Obsidian Vault(Markdown + YAML 정본) 위에 Claude
Code 플러그인(Skill·Guard), 읽기 전용 MCP 서버, localhost 대시보드 MYELIN Hub, 조직 공유 Commons 가 얹힌다. 설계 의도는 세 가지다. ① 축적의 복리 —
노트는 반복해서 연결·재사용될수록 강해진다(미엘린 강도). ② AI 초안, 사람 승격 — AI 는 `00_Inbox/ai-drafts/` 에 초안만 만들고 verified 승격은 사람이 Hub
Review Gate 에서 클릭으로만 한다(모든 쓰기 = git commit). ③ Vault 는 개인 소유, 공유는 선택 — 조직은 Vault 를 열람하지 않고 `share: true` 로 표시한
노트만 비식별 검사 후 Commons 에 제안한다.

## Vault 폴더 구조
keywords: 폴더, 구조, inbox, 00_, 10_, 20_, 30_, 40_, 50_, 80_, 90_, 99_, _patches, 어디에, 경로, 디렉터리, 저장

`00_Inbox/`(메모 · `ai-drafts/` AI 초안 · `clips/`) · `10_Domains/<ID>/`(verified 노트, `_MOC.md`) · `20_Projects/`
· `30_Resources/` · `40_IP/`(특허 후보 `candidates/`, 로컬 LLM 전용) · `50_Journal/`(/review 보고서) ·
`80_Outputs/drafts/`(/compose 산출물) · `90_System/`(templates · prompts · taxonomy.md · hooks/pre-commit) ·
`99_Archive/`(Reject 된 초안은 `rejected/`) · `_patches/`(링크 패치 제안, applied/rejected 이력) · `.myelin/`(색인 캐시) ·
`myelin.yaml`(설정). AI 가 쓸 수 있는 곳은 Level 에 따라 ai-drafts · 50_Journal · _patches · 80_Outputs/drafts ·
40_IP/candidates 로 제한되고, 그 외(특히 10_Domains · 40_IP · 90_System · myelin.yaml)는 사람 승인 영역이다.

## 노트 Frontmatter v2
keywords: frontmatter, 메타, yaml, id, type, status, origin, classification, share, confidence, 종류, 타입, 필드, 속성, 템플릿, doctor

모든 노트는 YAML frontmatter 를 가진다. 필수: `id` · `type` · `created`. 그 외 `domain`(목록) · `status` · `origin` ·
`confidence` · `classification` · `share` · `source` · `reviewed` · `tags`. 값: type = fleeting · literature ·
evergreen · moc · adr · experiment · lesson · checklist · idea-ip; status = draft · unverified · verified ·
deprecated; origin = human · claude · mixed(사람이 검토한 AI 초안); confidence = low · medium · high; classification =
public · internal · confidential; share = true/false(Commons 후보 표시). 템플릿은 `90_System/templates/`, 검사는 `myelin
doctor`(규칙 schema · fail-closed · orphan · confidential-share · broken-link · duplicate-id · domain ·
temporal).

## Domain(3+1)과 Pack
keywords: domain, 도메인, pack, 팩, sub-moc, moc, 3+1, add-domain, primary, research, growth, 추가, 분야

Domain 은 Primary(업무 근간) · Research(연구) · Growth(성장) + 선택 1개로 구성한다(3+1). Domain 정의는 코드가 아니라 **Pack**(YAML 데이터)이
공급한다: Core(`myelin.core`) · Reference(`brian.physical-ai`, 참고용 읽기 전용) · Org(`a3.*`) · Personal(`me.*`). 각
Domain 은 Sub-MOC 목록 · 허용 note type · taxonomy seed · 템플릿 · 인터뷰 질문 은행 · compose 대상을 갖는다. Domain 추가는 `myelin
add-domain <ID>` 또는 Hub 온보딩/Domain Packs 화면에서 한다. Hub › Domain Packs 에서 Reference Pack 을 '개인 Pack 으로 복사' 하면
`packs/me.*` 로 저장(commit)되어 편집할 수 있다. My Domains 화면의 Sub-MOC 버튼은 주제 검색 패널과 Obsidian 링크(`obsidian://`)를 준다.

## Level 과 Skill
keywords: level, 레벨, skill, 스킬, ingest, distill, interview, review, link, compose, ip-scan, 권한, 쓰기 범위, 자율, 단계

Level 은 AI 자율성 단계다. 0 read-only · 1 drafts(/ingest /distill /interview /review) · 2 link-patch(+ /link
/compose) · 3 scheduled review(+ /ip-scan). 쓰기 범위: /ingest·/distill·/interview → `00_Inbox/ai-drafts/`,
/review → `50_Journal/`, /link → `_patches/`, /compose → `80_Outputs/drafts/`, /ip-scan → `40_IP/candidates/`.
Level 은 사람만 바꾼다 — Hub › Settings 또는 `myelin.yaml level`. Skill 요약: /ingest 파일·URL·PDF → literature 초안,
/distill Inbox → 원자 노트 분해·용어 정규화, /interview 질문 은행으로 암묵지 → lesson 초안, /review 주간 품질 보고서(doctor + 지표 + 환류 대기),
/link 링크 후보·MOC 갱신 패치 제안, /compose 목적·독자 기반 산출물 초안, /ip-scan 교차 Domain 특허 후보(로컬 LLM).

## Hub 화면 안내
keywords: hub, 허브, 화면, 메뉴, dashboard, 대시보드, review gate, settings, 설정, 온보딩, 페이지, 어디서, 버튼, domain packs, my domains

Dashboard — KPI(주간 verified · 고아 비율 · 재사용 비율 · 재투입 소요일 · 산출물당 재료 수)와 '목표 이탈' 배지, Myelination(강도 분포), 최근 git
커밋. My Domains — Domain orb · Sub-MOC 검색 패널 · 노트 표(강도 `myelin ×N`) · Obsidian 열기. Inbox / Review Gate — AI 초안
'내용 읽기' → Promote/Reject, 패치 제안 미리보기(diff) → Apply, Commons 후보 비식별 검사 → 'Commons 제안'. Domain Packs — Pack 열기 ·
개인 Pack 으로 복사 · 저장(commit). Settings — Level, MCP(`write_draft`·`expose_confidential`), Commons(로컬 clone ·
remote · 연동 · 익명 지표 opt-in). 온보딩 마법사 — 빈 폴더에 이름·3+1 Domain(Pack 또는 직접 정의)·Level 로 Vault 생성. 모든 쓰기 버튼은 사람의 클릭
헤더(`X-Myelin-Intent: user-click`)가 있어야 하고 git commit 하나로 기록된다(ADR-0009). Hub 는 localhost 전용이다.

## Review Gate — Promote · Reject
keywords: promote, 승격, reject, 거절, verified, 초안, draft, ai-draft, 검토, 승인, 읽기, inbox

AI 초안(`origin: claude`, `status: draft`)은 Hub › Inbox / Review Gate 에서 사람이 처리한다. 먼저 '내용 읽기' 로 본문을 열어야 Promote
버튼이 켜진다(읽음 확인 장치). Promote 를 누르면 Hub 가 **자동으로** `origin: mixed`, `status: verified`, `reviewed: 오늘` 로 바꾸고
`10_Domains/<Domain>/` 으로 옮기며 `[myelin:review] promote …` 커밋 하나를 만든다(사람은 읽고 누르기만 한다). 같은 이름이 이미 있으면 409 로 막는다.
Reject → `99_Archive/rejected/` 로 옮기고 `status: deprecated`. doctor 를 통과하지 못한 초안(invalid)은 승격할 수 없다. 승격은 Hub
에서만 가능하며 Claude Code 가 직접 verified 를 만들 수 없다(Guard · pre-commit 훅).

## 패치 제안(_patches)
keywords: patch, 패치, _patches, apply, 적용, 미리보기, diff, digest, link, 제안

/link(Level ≥ 2)는 verified 노트를 직접 고치지 않고 `_patches/*.patch.md` 제안 파일을 만든다(ADR-0006). 종류: append(선택적으로 `under`
제목 구획 아래) · replace · frontmatter `## set`(허용 키 tags·source·projects·aliases·confidence). Hub › Review Gate 의
'미리보기' 가 diff 와 검사 결과(40_IP·confidential·verified→미검증 AI 링크 등 fail-closed 규칙)와 digest 를 보여 주고, Apply 는 그
digest 가 일치할 때만 적용된다(불일치 409). 처리된 패치는 `_patches/applied/` 또는 `_patches/rejected/` 로 이동한다.

## Claude Code 에서 쓰기 (plugin · Guard · MCP)
keywords: claude, 클로드, plugin, 플러그인, guard, 가드, 차단, mcp, hook, 훅, slash, /myelin, settings.json, write_draft

Vault 폴더에서 `claude` 를 실행하면 플러그인 Skill `/myelin:ingest` `/myelin:distill` `/myelin:interview` `/myelin:review`
`/myelin:link` `/myelin:compose` 가 보인다(없으면 `claude --plugin-dir <repo>/plugin`). Guard(PreToolUse hook, 표준
라이브러리만)가 Level 쓰기 범위 밖의 Write/Edit/Bash 쓰기를 차단하고, `.claude/settings.json` deny 가 2차 방어다. 차단되면 우회하지 말고
`_patches/` 제안으로 간다. MCP 서버(`myelin-mcp --vault`)의 도구 `search_notes` · `get_note` 등은 읽기 전용이며 `write_draft` 는
`mcp.write_draft: true` 와 Level ≥ 1 일 때만 등록된다. AI 가 만든 Vault 커밋은 `[myelin:<skill>]` 접두사를 쓴다.

## 기밀 라우팅 (confidential · 40_IP)
keywords: 기밀, confidential, 40_ip, ip, 라우팅, 로컬, local, 외부, 유출, 보안, 특허, myelin_llm, pre-commit, 훅

`classification: confidential` 노트와 `40_IP/**` 는 외부 LLM 에 보내지 않는다(ADR-0011 장치). 세션에 `MYELIN_LLM=local` 이 없으면
Claude Code 는 그 노트를 Read/Grep/Glob/Write 할 수 없고(guard_read · guard_bash), MCP 도 로컬 프로세스가 아니면
`expose_confidential` 을 무시한다. Vault git pre-commit 훅(`90_System/hooks/pre-commit` → `myelin doctor --staged`)은
Claude Code 밖에서 AI 초안을 승인 영역에 커밋하거나 confidential+share 를 커밋하는 것을 거부한다(기존 Vault: `myelin doctor
--install-hook`). 이 도우미도 같은 규칙을 따른다: 로컬(loopback) Ollama 에만 연결하며, 엔드포인트가 로컬이 아니면 confidential·40_IP 노트는 컨텍스트에서
제외한다.

## Commons 공유
keywords: commons, 공유, 공개, share, pr, push, 비식별, 익명, 지표, metrics, 평판, remote, clone, 조직

공개하고 싶은 verified 노트에 `share: true` 를 표시하면 Hub › Review Gate › Commons 후보에 나타난다. 비식별 검사(고객명·IP·시스템명 등 내장 7 +
`deid.yaml`)를 통과하고 사용자가 확인 체크한 것만 'Commons 제안' 으로 로컬 Commons clone 의 `publish/*` 브랜치에 커밋된다(ADR-0010). 'push 하고
PR 을 만든다' 를 체크하면 push 와 PR(`gh`)까지 진행하고, 실패해도 커밋은 보존되고 다음 명령을 안내한다. Settings › Commons 에서 로컬 clone
경로·원격(`commons.remote`, 연동을 켤 때 필수)·익명 지표 opt-in 을 설정한다(`myelin commons init`). 두 정체성: Commons 노트에는 작성자 실명과 원
노트 id 가 남아 기여가 평판이 되고(`top_contributors`, 인용 수), 익명 지표는 owner 해시와 숫자만 보낸다(기본 꺼짐).

## 미엘린 강도와 재사용 KPI (ADR-0012)
keywords: 강도, strength, kpi, 지표, 재사용, reuse, 목표 이탈, myelination, 복리, ×, 통계, stats

노트별 강도 0~3: 0 = verified 아님, 1 = verified, 2 = 두 곳 이상에서 링크되거나 /compose 산출물의 재료로 쓰임, 3 = Commons 에서 인용됨.
Dashboard 와 My Domains 표에 `myelin ×N` 텍스트로 보인다. 재사용 KPI: `reuse_ratio`(verified 중 재사용된 비율, 목표 ≥ 0.30) ·
`reuse_lag_days`(verified 후 첫 재사용까지, 목표 ≤ 30일) · `compose_sources_avg`(산출물당 재료 노트 수, 목표 ≥ 3). 목표를 벗어나면
Dashboard 에 '목표 이탈' 배지가 뜬다. `myelin stats` 로도 같은 수치를 본다.

## 환류(refeed)
keywords: 환류, refeed, compose, 산출물, outputs, 80_outputs, 되돌, 재투입

`/myelin:compose` 로 만든 산출물(`80_Outputs/drafts/`)에는 `## 환류 후보` 절이 생긴다. `/myelin:distill
80_Outputs/drafts/<산출물>.md` 로 그 절을 lesson · evergreen · adr 초안(`tags: [refeed]`)으로 되돌리고 Review Gate 에서 승격한다.
`/myelin:review` 는 환류 대기 산출물과 재사용 지표 이탈을 보고한다. 산출물 안에만 남은 지식은 다시 쓰이지 않으므로 반드시 원자 노트로 되돌린다.

## Obsidian 연동
keywords: obsidian, 옵시디언, 테마, theme, cssclasses, emboss, 열기, 링크

MYELIN 과 Obsidian 의 연동은 플러그인이 아니라 테마 + 파일 규약이다. MYELIN Vault 는 `myelin.yaml` 이 있는 폴더이며
`.obsidian/themes/MYELIN Emboss/` 테마가 미리 들어 있다(Appearance › Light › MYELIN Emboss). 상태 표시는 frontmatter
`cssclasses: [mx-status-verified]`(라임 링) · `[mx-status-ai-draft]`(시안 glow) · `[mx-status-blocked]`. Hub 의 노트
링크는 `obsidian://open?path=` 로 Obsidian 에서 바로 열린다. 색은 `design/tokens.json` → `make emboss` 로만 바꾼다.

## CLI 명령
keywords: cli, 명령, 커맨드, init, 터미널, 설치, install, 실행, 시작, 포트, port, uv

`myelin init --vault <폴더>`(Vault 생성, git + pre-commit 훅, `--no-git`) · `myelin add-domain <ID>` · `myelin
doctor [--staged | --install-hook]` · `myelin stats` · `myelin skills` · `myelin interview-bank` · `myelin
publish` · `myelin pack-propose` · `myelin metrics [aggregate]` · `myelin commons init`. 서버: `myelin-mcp
--vault <v>` · `myelin-hub --vault <v> [--port 8787]`(localhost 전용). 설치: `git clone … && scripts/install.sh
--vault ~/Vaults/me --claude`(uv sync → Hub 빌드 → 런처 → Obsidian 테마, `--claude` 는 plugin/MCP 등록 opt-in). 요구:
Python 3.12 · uv · git · Node 22(Hub 웹) · Claude Code.

## 문제 해결
keywords: 오류, 에러, 문제, 안됨, 안 됨, 403, 409, 실패, 해결, 고장, ollama, 모드, 느려, 안 보

`myelin doctor` 오류 → 메시지의 규칙 이름(schema · fail-closed · orphan · confidential-share · broken-link ·
duplicate-id · domain · temporal)으로 해당 노트를 고친다. Guard 가 전부 막는다 → Vault 에 `myelin.yaml` 이 있는지, `level` 이 0 이
아닌지 확인. Hub 가 403 → `127.0.0.1` 로 접속하는지, 다른 사이트 탭에서 호출하지 않았는지(Host/Origin 검사). Commons 연동을 켤 때 '원격 저장소가 필요하다'
→ Settings › Commons 에 `commons.remote` 를 먼저 적는다. Promote 가 409 → 같은 이름의 노트가 Domain 폴더에 이미 있다. 이 도우미가 '지식 기반
모드' 라고 표시되면 로컬 Ollama(`http://127.0.0.1:11434`)가 꺼져 있다 — 켜면 자동으로 LLM 모드가 된다(`MYELIN_ASSISTANT_URL` ·
`MYELIN_ASSISTANT_MODEL` 로 변경).

## 이 도우미에 대해
keywords: 너는, 누구, 챗봇, 도우미, 어시스턴트, ai, 사람, 할 수 있, 무엇을, 기능, 도움, help

저는 사람이 아닌 MYELIN 도우미(AI) 입니다. Hub 우측 하단 말풍선에서 열리는 도움말 챗봇으로, MYELIN 의 개념·사용법·절차와 이 Vault 의 상태(Domain · Level ·
KPI · 관련 노트)를 안내한다. 답변은 내장 지식(사용자 가이드·ADR 요약)과 Vault 검색 발췌를 근거로 하며, 로컬 Ollama 가 있으면 LLM 이 문장을 만들고 없으면 지식 절을
그대로 보여 준다(지식 기반 모드). 이 도우미는 MYELIN 의 개념·사용법·절차와 이 Vault 의 상태만 안내하며, 노트를 쓰거나 승격·커밋·삭제 같은 어떤 행위도 대신 하지 않습니다 — 그
일은 Hub 의 버튼과 Claude Code Skill 로, 사람이 합니다. 대화 내용은 서버에 저장하지 않는다.
