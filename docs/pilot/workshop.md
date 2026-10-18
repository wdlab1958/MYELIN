# 60분 워크숍 — "나의 지식 신경망 시작하기" (명세 §9.3)

준비물: 노트북(설치 완료 또는 설치 스크립트), 오늘 업무 자료 1건, Claude 계정(회사 승인 플랜).
진행자: 챔피언 1명 + 보조 1명 (10명 기준).

| 시간 | 내용 | 진행 포인트 |
|---|---|---|
| 0–10분 | **왜 MYELIN인가** | 축적이 복리로 작동하는 구조. 경험 → verified 노트 → 다음 산출물에 재투입. 사례: Reference Pack(4 Domain) |
| 10–25분 | **설치 + 온보딩 마법사** | `myelin-hub --vault ~/MyVault --open` → 이름 → Pack → **3+1 Domain** → Level 1 → 만들기. 시작 시각을 적어 두기 |
| 25–40분 | **실습: 업무 하나를 지식으로** | Vault 폴더에서 Claude Code: `/myelin:ingest <자료>` → `/myelin:distill` → Hub **Review Gate**에서 원문 확인 후 Promote → Lime ring(myelinated) 확인 |
| 40–50분 | **/interview 체험** | `/myelin:interview` — Pack 질문 은행으로 내 업무 교훈 1개를 lesson 초안으로 → 승격 |
| 50–60분 | **공유 원칙 · 보안 · Q&A** | 개인 Vault 불가침 · confidential/40_IP는 로컬만 · Commons 공개 4단계 · 지표는 opt-in 파일 |

## 진행자 체크리스트
- [ ] 정책 3종 합의 상태를 시작 전에 공지했다 (미합의면 "Commons는 아직 꺼져 있음")
- [ ] 참가자 Vault가 MYELIN 소스·공개 저장소 밖에 있는지 확인했다
- [ ] 각자 `pilot_time.py` 로 온보딩 분을 계산해 운영자에게 알렸다 (노트 내용 X)
- [ ] 15분을 넘긴 참가자는 어디서 막혔는지 한 줄 메모를 받았다 → `feedback.md`

## 자주 막히는 곳 (사전 안내)
| 증상 | 해결 |
|---|---|
| `myelin init` 이 "git 저장소 안" 이라며 거부 | Vault는 독립 폴더에 (예: `~/MyVault`) |
| Promote가 "git 없음"으로 거부 | Settings → 로컬 git 시작 |
| Claude가 40_IP 노트를 못 읽음 | 정상 — 로컬 LLM 전용 영역 |
| Commons 제안 버튼이 꺼져 있음 | 5개 확인 항목을 모두 체크 / 자동 검사 차단 사유 확인 |
