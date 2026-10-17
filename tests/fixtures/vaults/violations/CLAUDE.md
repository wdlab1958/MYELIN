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

## Write Policy (fail-closed)
- 새 노트는 `00_Inbox/ai-drafts/` 에만 만든다 (`origin: claude`, `status: draft`).
- 그 외 경로의 노트는 직접 고치지 않는다. 변경은 `_patches/YYYYMMDD-<topic>.md` 로 제안한다.
- `40_IP/` 와 `classification: confidential` 노트는 읽기만 하고, 외부 도구로 보내지 않는다.
- verified 승격, MOC 편집, 공유는 사람만 한다.

## Note Conventions
- 1 노트 = 1 개념. 제목은 주장형 문장을 권장한다.
- 용어는 `90_System/taxonomy.md` 를 따른다. 새 용어는 그 파일의 "제안" 절에 추가를 요청한다.
- 외부 사실에는 `source` 를 기록한다. 출처가 불분명하면 `confidence: low`.
- 템플릿: `90_System/templates/` · 인터뷰 질문: `90_System/interviews.md`

## Linking
- 링크를 제안할 때는 근거(공통 개념·인과·대조)를 한 줄로 적는다.
- `status: verified` 가 아닌 노트를 MOC에 넣자고 제안하지 않는다.

## 개인 메모
