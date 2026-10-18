# ADR-0009: Hub 쓰기 정책 — 사람의 클릭만 Vault 를 바꾼다

- 상태: Accepted · 일자: 2026-10-18 · Phase: P6
- 근거: 정본 §1.2 "HITL 승격 — verified 승격은 Hub 의 Review Gate 에서 사람의 클릭으로만, Git commit 으로 기록", §3 HITL Oversight, §4.2 데이터 흐름, P6 Gate "사용자 클릭 없이 Vault 쓰기 발생 0"

## 결정

1. **읽기는 GET, 쓰기는 POST/PUT 로 분리**하고, 쓰기 엔드포인트는 전부 `X-Myelin-Intent: user-click` 헤더를 요구한다(없으면 403). 헤더는 Hub UI 의 **onClick 핸들러에서만** 붙인다(`lib/api.ts userPost/userPut`). 페이지 로드·폴링·useEffect 는 GET 만 호출한다.
2. **쓰기 동작 6종**: `promote`(ai-draft → `10_Domains/<D>/`, status verified, reviewed 오늘, origin claude→mixed), `reject`(→ `99_Archive/rejected/`, status deprecated), `apply_patch`/`reject_patch`(ADR-0006), `save_settings`(myelin.yaml + CLAUDE.md 재렌더, personal 블록 보존), `save_pack`(개인 Pack `me.*` 만, `<Vault>/packs/`), `onboarding`(init_vault + welcome 초안 + git init). 각 동작은 **정확히 하나의 git commit** 으로 끝난다(`[myelin:<action>] …`).
3. **승격 전제**: 초안이 `00_Inbox/ai-drafts/` 에 있고 frontmatter 가 유효하며 Domain 이 설정된 것이어야 한다. 모순(confidential+share 등)은 승격 거부(422). 대상 파일이 이미 있으면 409(덮어쓰기 금지).
4. **git**: Vault 가 저장소가 아니면 첫 쓰기에서 `git init` + `[myelin:init]` 커밋. `.myelin/` 은 `.gitignore` 로 제외. 스테이징은 변경된 경로만(`git add -- path`, 삭제는 `git rm --cached`), 무관한 사용자 변경은 커밋에 섞이지 않는다.
5. **Welcome 초안**: 온보딩이 `00_Inbox/ai-drafts/MYELIN 시작하기.md`(origin claude, status draft) 를 만들어 Day 1 에 첫 승격을 경험하게 한다(부록 D). CLI `myelin init` 은 만들지 않는다(golden 안정, CLI 는 스크립트 용도).
6. **감사 테스트**: (a) API 테스트가 모든 GET 과 `POST /api/packs/validate` 를 호출한 뒤 Vault 트리 해시가 동일함을 확인, (b) Playwright 가 5개 화면을 모두 방문한 뒤 `git status` 가 clean 이고 커밋 수가 그대로임을 확인, (c) 헤더 없는 쓰기 요청은 모두 403.
7. **Hub 는 localhost 전용**(Personal 모드). `--host` 가 loopback 이 아니면 기동 거부. Team 모드 인증은 P7.
8. Hub 는 기밀 노트를 가리지 않는다 — 소유자의 로컬 UI 이며 외부 모델로 보내지 않는다(MCP 정책 ADR-0007 과 구별).

## 결과
- Guard(ADR-0005)·MCP(ADR-0007)·Hub(이 ADR) 세 경로 모두 "AI 는 초안만, 승격은 사람만" 을 장치로 강제한다.
- Guard 차단 이벤트는 `<Vault>/.myelin/guard.log`(JSONL) 로 남고 Hub Dashboard 의 "Guard 차단 (7일)" 타일에 표시된다.
