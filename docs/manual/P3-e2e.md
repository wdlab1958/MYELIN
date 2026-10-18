# P3 수동 e2e — 실제 Claude Code에서 확인하기

자동 테스트는 Guard·권한·Skill 출력 계약을 검사한다. **실제 Claude가 Skill을 따르는지**는
사람이 Claude Code에서 한 번 돌려 봐야 한다. 30분 정도 걸린다.

## 준비
```bash
myelin init ~/MYELIN-test --name Brian --pack brian.physical-ai \
  --primary AI-ML-AX --research ROBOTICS-LEARNING --level 1 --yes
cd ~/MYELIN-test && claude
```
Claude Code 안에서:
```
/plugin marketplace add wdlab1958/MYELIN
/plugin install myelin@myelin
```

## 체크리스트 (결과를 옆에 적는다)
| # | 해볼 것 | 기대 결과 | 결과 |
|---|---|---|---|
| 1 | `/myelin:ingest https://…` (아무 기술 문서) | `00_Inbox/ai-drafts/Lit - ….md` 생성, `origin: claude`, `status: draft` | |
| 2 | `/myelin:distill "00_Inbox/ai-drafts/Lit - ….md"` | 주장형 제목의 evergreen 초안 1~5개, 원본 미수정 | |
| 3 | `/myelin:interview EMBEDDED-SW` | 한 번에 한 질문, 답을 기다림, lesson 초안(`origin: mixed`) | |
| 4 | `/myelin:link 10_Domains/AI-ML-AX/_MOC.md` (Level 1) | Skill이 "Level 2 이상 필요"라고 멈춤 | |
| 5 | Claude에게 "10_Domains/AI-ML-AX/_MOC.md 에 한 줄 추가해 줘" | **Guard 차단** 메시지(`MYELIN guard:`), Claude가 우회하지 않고 알림 | |
| 6 | `40_IP/test.md` 를 직접 만들고 Claude에게 "읽어 줘" | 권한 deny 또는 Guard 차단 — 내용이 대화에 나오지 않음 | |
| 7 | confidential 노트를 `30_Resources/` 에 만들고 "요약해 줘" | Guard 차단 (`confidential 노트는 로컬 LLM 전용`) | |
| 8 | "echo hi > 10_Domains/x.md 실행해 줘" | 권한 deny (Edit 규칙이 리다이렉트 대상 검사) | |
| 9 | `myelin.yaml` 의 level을 2로 바꾸고 `/myelin:link …` | `_patches/…-link-….md` 생성, 노트는 미수정 | |
| 10 | `/myelin:review` | `myelin doctor/stats` 실행(사전 승인), `50_Journal/reviews/…md` 생성 | |
| 11 | 다른 코드 저장소에서 Claude Code 실행 → 평소처럼 파일 수정 | 플러그인 Hook이 **간섭하지 않음** | |
| 12 | 그 코드 저장소 세션에서 `~/MYELIN-test/10_Domains/…` 에 쓰기 요청 | 플러그인 Hook이 차단 | |
| 13 | 끝나고 `myelin doctor ~/MYELIN-test` | 오류 0 (경고는 검토 대기 초안 정도) | |
| 14 | Obsidian에서 Templater로 evergreen 템플릿 새 노트 | id가 `YYYYMMDD-HHmm-ssSSS` 형태로 채워짐 (P2 Backlog) | |

## 문제가 생기면
- Hook이 아예 안 도는 것 같으면: `python3 --version` (3.9+ 필요), `/hooks` 로 등록 상태 확인.
- 결과를 `docs/reports/P3-e2e-result.md` 로 남기고, 실패 항목은 PHASE_STATE Backlog에 올린다.
