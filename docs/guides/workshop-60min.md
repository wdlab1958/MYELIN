# MYELIN 60분 워크숍 (정본 §9.3)

| 시간 | 내용 | 자료·실습 |
|---|---|---|
| 0–10분 | **왜 MYELIN 인가** — 축적이 복리로 작동하는 구조. Brian Reference Pack(D1~D4) 사례: 45년차 엔지니어의 지식 지형도가 후배의 출발점이 된다 | `docs/spec/MYELIN_Rev2.0.md` §1–2, `packs/brian.physical-ai` |
| 10–25분 | **3+1 Domain 설정** — Primary(업무 근간)·Research·Growth. `myelin init` 또는 Hub 온보딩. "시작부터 많이 만들면 MOC 가 빈다" | `docs/guides/pilot-guide.md` §2 |
| 25–40분 | **실습: 오늘 업무 하나를 `/ingest` → `/distill` → Review Gate 승격** — ai-draft(Cyan) 가 verified(Lime 링) 가 되는 순간을 본다. 승격은 사람의 클릭, git commit 으로 기록 | Hub Review Gate |
| 40–50분 | **`/interview` 체험** — Pack 질문 은행에서 한 질문. 1인칭 답을 lesson 초안으로 | `myelin interview-bank -d <Domain>` |
| 50–60분 | **공유 원칙·보안 정책·Q&A** — 개인 Vault 불가침, share:true + verified + ≤ internal 만 Commons, 비식별 스캔, 지표는 opt-in 익명 | ADR-0010, `docs/spec/commons.md` |

준비물: 노트북(Python 3.12, Node 22, git, Claude Code), 사내 Registry 경로, 오늘 업무 메모 1개.
