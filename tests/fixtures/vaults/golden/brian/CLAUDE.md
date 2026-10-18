# MYELIN Vault — Operating Rules for Claude

<!-- myelin init 이 만든 파일입니다. 표시된 자동 생성 구간 밖은 자유롭게 고쳐도 됩니다. -->

## Owner
- Brian. 노트와 응답은 `ko` 로, 기술 용어는 영어를 병기한다.

<!-- myelin:generated:start -->
## Domains

| Role | ID | Label | Name |
|---|---|---|---|
| primary | AI-ML-AX | D1 | AI / ML / AX Platform |
| research | ROBOTICS-LEARNING | D3 | 자율학습 Robotics (Physical AI) |
| growth | AUTO-DESIGN | D4 | Auto Design — SolidWorks 설계 자동화 |
| extra | EMBEDDED-SW | D2 | Embedded SW Engineering |

## Level: 1
- 초안 — ai-drafts에 초안을 쓸 수 있다
<!-- myelin:generated:end -->

## Write Policy (fail-closed — `.claude/hooks/myelin_guard.py` 가 실제로 차단한다)
- 쓸 수 있는 곳은 Level에 따라 정해진다 (`.md` 만):
  - L1 `00_Inbox/ai-drafts/`, `50_Journal/reviews/`
  - L2 + `_patches/`, `80_Outputs/drafts/`
  - L3 + `40_IP/candidates/`
- 새 노트의 frontmatter에는 `origin: claude`, `status: draft` 를 넣는다.
- 기존 노트는 직접 고치지 않는다. 변경은 `_patches/YYYYMMDD-<topic>.md` 로 제안한다.
- `40_IP/` 와 `classification: confidential` 노트는 **읽지 않는다**.
  로컬 LLM 전용이다 — Claude가 읽는 순간 내용이 외부로 전송되기 때문.
- verified 승격, MOC 편집, 공유는 사람만 한다. 차단 메시지가 나오면 우회하지 말고 사람에게 알린다.

## Note Conventions
- 1 노트 = 1 개념. 제목은 주장형 문장을 권장한다.
- 용어는 `90_System/taxonomy.md` 를 따른다. 새 용어는 그 파일의 "제안" 절에 추가를 요청한다.
- 외부 사실에는 `source` 를 기록한다. 출처가 불분명하면 `confidence: low`.
- 템플릿: `90_System/templates/` · 인터뷰 질문: `90_System/interviews.md`

## Linking
- 링크를 제안할 때는 근거(공통 개념·인과·대조)를 한 줄로 적는다.
- `status: verified` 가 아닌 노트를 MOC에 넣자고 제안하지 않는다.

## 개인 메모
