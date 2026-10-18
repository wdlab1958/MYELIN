# MYELIN A3 파일럿 가이드 (P7)

대상: 자원자 5~10명 + 팀별 챔피언 · 기간: 3주 · 목표: **온보딩 15분**, Org Pack 2종 확정, Commons 첫 공개.

## 0. 준비 (운영자 — Brian)
1. Commons 저장소 생성: `uv run myelin commons init /srv/myelin-commons` → 사내 git 에 push, URL 을 아래 2단계에 기입.
2. Org Pack 등록: `uv run myelin commons add-pack packs/a3.security-consulting --commons /srv/myelin-commons --champion <이름>` (incident-response 도 동일).
3. 파일럿 참가자에게 이 문서 + `day1-checklist.md` 전달. 워크숍 일정(60분) 잡기.

## 1. 설치 (참가자, 5분)
```bash
git clone <myelin repo> && cd myelin
make sync && make web                       # Python + Hub 웹 빌드
export MYELIN_PACKS=/srv/myelin-commons/registry/packs   # 사내 Registry 를 Pack 검색 루트에
```

## 2. Vault 만들기 (5분) — 둘 중 하나
- Hub: `uv run myelin-hub --vault ~/Vaults/me` → 브라우저에서 이름·3+1 Domain·Level 입력 → Vault 생성 (welcome 초안이 생긴다)
- CLI: `uv run myelin init --vault ~/Vaults/me` (대화형)

온보딩 시작 시각이 `.myelin/metrics.jsonl` 에 기록된다.

## 3. 첫 verified 노트 (5분)
1. Obsidian 에서 Vault 열기 → Settings › Appearance › Themes › `theme/obsidian-myelin-emboss` 복사(`.obsidian/themes/`) → Emboss 적용
2. Vault 폴더에서 `claude --plugin-dir <myelin repo>/plugin` → "이 Vault 의 규칙을 요약하라" 로 연결 확인
3. 오늘 업무 메모 하나를 `00_Inbox/` 에 쓰고 `/myelin:distill`
4. Hub › Inbox / Review Gate › **Promote** → Lime 링 확인. 이 순간 `first_promote` 가 기록되고 `uv run myelin metrics` 가 **onboarding_minutes** 를 보여 준다.

## 4. 결과 기록 (운영자)
```bash
python3 scripts/pilot.py record --vault ~/Vaults/<참가자> --note "컨설팅 2팀"   # onboarding_minutes 를 읽어 기록
python3 scripts/pilot.py report                                              # docs/reports/P7/pilot-results.md 갱신
```
참가자 이름은 저장하지 않는다(익명 해시 + 메모만).

## 5. 3주 운영
- 주 1회 `/myelin:review` · 주간 verified ≥ 5 목표
- `share: true` 로 표시한 verified 노트는 Hub › Review Gate › **Commons 후보** 에서 비식별 검사 후 "Commons 제안" → PR → 챔피언 merge
- 피드백은 `docs/reports/P7/pilot-feedback.md` 양식으로

## 6. 보안 정책 요약 (§9.1)
- 개인 Vault 불가침. 조직은 Vault 를 열람하지 않는다. 지표는 opt-in 익명 집계뿐(`myelin.yaml commons.metrics_opt_in`).
- confidential 노트·`40_IP/` 는 외부 LLM 에 보내지 않고(`llm.route`) 공개할 수 없다.
- 고객명·IP·시스템명은 노트에 쓰지 않는다. 쓰면 Commons 제안이 차단된다.
