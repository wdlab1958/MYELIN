# Scope: review-gate-promote-toctou
- Project / Module: MYELIN / Hub — `myelin-hub/api` `HubService.promote()`·`note()` + `myelin-hub/web` Review 페이지
- Verification Level Target: **L2 (TLA+/TLC) → L3 (Lean 4, W7 승격)**
- Concern (한 문장): 사람이 Review Gate 에서 초안 본문을 읽은 시점과 Promote 클릭이 Hub 에 도착하는 시점 사이에 초안 파일이 다시 쓰이면, 읽지 않은 글이 verified 가 된다.
- Rank: blast radius **H** (verified = MYELIN 의 신뢰 단위. HITL 승격이 제품의 핵심 약속) × concurrency **M** (Claude Code skill·MCP write_draft·Obsidian 이 같은 폴더에 쓰는 동안 사람이 검토)
- Workflow: W1 (bug hunt) → W7 (Lean 승격)

## In scope
- 초안 파일 `00_Inbox/ai-drafts/<n>.md` 의 내용(버전)
- Review 페이지의 "내용 읽기"(`GET /api/notes/<path>`)와 Promote 클릭(`POST /api/review/promote/<path>`)
- `HubService.promote()` 가 승격 시점에 파일을 다시 읽는 동작
- 초안을 다시 쓰는 임의의 writer (skill, MCP `write_draft`, 편집기)

## Abstracted (버그를 숨길 수 있는 추상화 명시)
- **A1 내용 = 버전 번호.** 파일 바이트 전체를 자연수 하나로 본다. digest 는 내용이 같을 때만 같다고 가정한다(sha256 앞 16 hex 의 충돌은 모델 밖).
- **A2 Promote 처리는 원자적.** 실제 `promote()` 는 `read_bytes()` → 검사 → 대상 쓰기 → 원본 `unlink` 순서다. 읽은 뒤 unlink 전에 writer 가 초안을 또 바꾸면 그 바뀐 글은 사라진다(승격된 글은 사람이 읽은 글 그대로이므로 P3 는 유지되지만, writer 의 마지막 수정은 유실). 이 창은 수 ms 이고 모델에 없다.
- **A3 본문과 digest 는 같은 바이트에서 나온다.** `note()` 가 파일을 한 번 읽어 둘 다 만든다는 코드 사실에 의존한다(`service.py` note()).
- **A4 클릭은 화면에 보인 digest 를 그대로 보낸다.** 브라우저(Review.tsx)가 정직하게 동작한다고 본다. digest 없이 API 를 직접 호출하는 클라이언트는 검사를 받지 않는다(`digest` 는 선택 필드 — 아래 Out of scope).
- **A5 frontmatter 유효성·Domain 검사·git commit·대상 파일 충돌(409)은 생략.** 승격이 "성공한다"는 사실만 모델링.

## Out of scope
- `digest` 없이 들어오는 Promote 요청(스크립트·구버전 UI). 기존 `apply_patch` 와 같은 정책으로 선택 필드로 두었다. 필수화는 공개 API 변경이라 HITL 결정 대상.
- `apply_patch` 의 digest 가 patch 파일만 덮고 대상 노트 내용은 덮지 않는 점(기록만: 후보 표 참조).
- Reject, Commons 제안.

## Tool choice & rationale
- 인터리빙 문제 → **TLA+** 로 반례 탐색·수정 검증.
- 속성이 "모든 초안·모든 재작성 횟수·모든 실행 길이"에 대해 성립해야 하는 제품의 핵심 불변식(의료·금융·보안급은 아니지만 MYELIN 의 HITL 약속 그 자체) → **Lean 4** 로 inductive invariant 증명(W7).

## Bounds
- TLC: `Notes={n1,n2}, MaxVer=2` (PR 게이트) · `Notes={n1,n2,n3}, MaxVer=3` (nightly 급, 105,648 states)
- Lean: 경계 없음 (`Note` 임의 타입, 내용 임의 자연수, 실행 길이 임의)
