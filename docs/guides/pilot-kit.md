# MYELIN 사내 파일럿 키트 (5명, 3주)

- 작성: 2026-11-26 · 대상: 파일럿 운영자와 팀 챔피언 · 관련 작업: WBS 2.5.4(파일럿), WBS 1.6(명칭·상표)
- **상태: 파일럿은 아직 수행되지 않았다.** `docs/reports/P7/pilot-results.jsonl` 은 존재하지 않고, `docs/reports/P7/pilot-feedback.md` 는 `(TBD)` 양식 그대로다. 이 문서는 사람이 파일럿을 돌릴 때 쓰는 준비물이며, 결과가 아니다.
- 참가자 실행 절차의 상세는 [`pilot-guide.md`](pilot-guide.md), 첫날 점검은 [`day1-checklist.md`](day1-checklist.md), 워크숍은 [`workshop-60min.md`](workshop-60min.md) 를 따른다. 이 키트는 그 문서들을 묶는 운영 계획서다.

## 0. 위치 정리

MYELIN 은 고객에게 판매하는 상품이 아니다. One Cycle Dev. Framework 수행 과정에서 생기는 정보 자산(진단 교훈, 검증 결과, 운영 기록)을 개발자와 운영자가 직접 관리하는 **개인 지식 관리 서비스**다. 파일럿의 목적은 "팔 수 있는가"가 아니라 "사내 5명이 15분 안에 쓰기 시작하고 3주 동안 계속 쓰는가"를 확인하는 것이다.

## 1. 역할 (사람이 지정 — 현재 미지정)

| 역할 | 담당자 | 하는 일 | 지정일 |
|---|---|---|---|
| 파일럿 운영자 (lead) | | 일정, 설치 지원, `scripts/pilot.py` 기록, 피드백 리포트 작성 | |
| 챔피언 — a3.security-consulting | | Pack 의 Sub-MOC·용어 확정, Commons PR 검토·merge | |
| 챔피언 — a3.incident-response | | 위와 같음 | |
| 참가자 1 | | 온보딩, 3주 사용, 피드백 양식 제출 | |
| 참가자 2 | | | |
| 참가자 3 | | | |
| 참가자 4 | | | |
| 참가자 5 | | | |

참가자 실명은 이 표(사내 보관)에만 쓴다. `scripts/pilot.py` 는 이름을 저장하지 않고 owner 해시와 메모만 남긴다.

## 2. 사전 준비 (운영자)

| # | 항목 | 확인 |
|---|---|---|
| 1 | 참가자 PC: Python 3.12, `uv`, `git`, Node(Hub 웹 빌드용). `scripts/install.sh` 가 첫 단계에서 검사한다 | ☐ |
| 2 | Obsidian 설치 (Linux 는 `scripts/install_obsidian.sh`) | ☐ |
| 3 | Claude Code 를 쓰는 참가자만 `--claude` 연동. 쓰지 않아도 Vault·Hub 는 동작한다 | ☐ |
| 4 | Commons 저장소: `uv run myelin commons init <경로>` 후 사내 git 에 push | ☐ |
| 5 | Org Pack 등록: `uv run myelin commons add-pack packs/a3.security-consulting --commons <경로> --champion <이름>` (`a3.incident-response` 도 동일) | ☐ |
| 6 | 참가자 전원이 [지식 관리 지침](knowledge-management-policy.md) 을 읽었다 (5절) | ☐ |
| 7 | 60분 워크숍 일정 확정 | ☐ |

## 3. 참가자별 온보딩 (목표 15분)

```bash
# 1) 설치 — 런처 myelin / myelin-mcp / myelin-hub 를 ~/.local/bin 에 만든다
git clone <myelin repo> && cd myelin
scripts/install.sh --vault ~/Vaults/me            # Claude Code 연동까지 하려면 --claude 추가
#   옵션: --bin <dir> --no-web --no-plugin --no-mcp --dry-run

# 2) Vault 만들기 — 둘 중 하나
myelin-hub --vault ~/Vaults/me                    # http://127.0.0.1:8787 의 온보딩 마법사
myelin init --vault ~/Vaults/me                   # 또는 CLI 대화형

# 3) 첫 verified 노트
#    00_Inbox/ 에 메모 작성 → (Claude Code 사용자는 /myelin:distill) → Hub › Inbox / Review Gate › Promote
myelin metrics show --vault ~/Vaults/me           # onboarding_minutes 확인
```

온보딩 시작과 첫 승격 시각은 Vault 의 `.myelin/metrics.jsonl` 에 기록되고, 그 차이가 `onboarding_minutes` 다.

운영자는 참가자마다 한 번 기록한다.

```bash
python3 scripts/pilot.py record --vault ~/Vaults/<참가자> --note "팀/메모"   # onboarding_minutes 를 읽어 기록
python3 scripts/pilot.py record --vault <path> --minutes 12.5 --note "수동 측정" # 측정 이벤트가 없을 때
python3 scripts/pilot.py report      # docs/reports/P7/pilot-results.md 갱신
python3 scripts/pilot.py check       # 5명 이상이고 전원 15분 이내면 exit 0
```

측정 이벤트(`onboard_start`, `first_promote`)가 없으면 `record` 는 exit 2 로 끝나고 `--minutes` 를 요구한다.

## 4. 3주 일정

| 주 | 운영자 | 참가자 | 산출물 |
|---|---|---|---|
| 0 (준비) | 2절 점검표, 역할 지정 | 지식 관리 지침 읽기 | 역할 표(1절) |
| 1 | 워크숍 60분, 온보딩 측정, `pilot.py record` 5건 | 설치 → Vault → 첫 verified 노트, Day 1 체크리스트 | `pilot-results.jsonl` 5행 이상 |
| 2 | 막힌 지점 수집(설치, Guard 차단, doctor 오류, 용어) | 주 1회 `/myelin:review`, 주간 verified 5건 목표 | 중간 메모 |
| 3 | 챔피언과 Pack 확정, Commons 첫 PR 검토 | `share: true` 노트를 Commons 후보로 제안, 피드백 양식 제출 | 피드백 양식 5부, Pack 변경안 |
| 종료 | `pilot-feedback.md` 작성(TBD 제거) → `make gate P=7` | | P7 Gate 결과 |

## 5. 기록 금지 규칙 (요약)

Skill 작업은 Claude Code(클라우드)를 거친다. 그래서 다음은 Vault 어디에도 쓰지 않는다. 전문은 [`knowledge-management-policy.md`](knowledge-management-policy.md).

- 고객 식별 정보: 고객명, 시스템명, IP, 호스트명, 계정
- 고객 코드: 고객 저장소의 소스, 설정 파일, 로그 원문
- 자격증명: 비밀번호, 토큰, API 키, 개인키

고객은 유형(금융, 공공, 제조, 플랫폼)으로만 분류하고 `<고객A>`, `<호스트1>` 같은 자리표시자를 쓴다.

## 6. 성공 기준

### 6.1 P7 Gate 가 기계적으로 검사하는 것 (`scripts/gate.py`, `make gate P=7`)

| 기준 | 판정 방법 | 현재 |
|---|---|---|
| 참가자 5명 이상 기록, **전원** 온보딩 15분 이내 | `python3 scripts/pilot.py check` 가 exit 0 (`TARGET_N = 5`, `TARGET_MIN = 15.0`) | 미충족 (기록 0건) |
| 피드백 리포트가 채워짐 | `docs/reports/P7/pilot-feedback.md` 에 문자열 `TBD` 가 없음 | 미충족 |

한 명이라도 15분을 넘으면 `check` 는 실패한다. 평균이 아니라 전원 기준이다.

### 6.2 운영 목표 (Gate 가 검사하지 않음 — 운영자가 피드백 리포트에 기록)

| 목표 | 출처 |
|---|---|
| 참가자별 주간 verified 노트 5건 이상 | `pilot-guide.md` 5절 |
| Org Pack 2종의 Sub-MOC·용어를 챔피언이 확정 | `pilot-feedback.md` 3절 |
| Commons 첫 공개: 공개 노트 수, PR 수, 비식별 차단 건수 기록 | `pilot-feedback.md` 4절 |
| 기록 금지 규칙 위반 0건 | 5절 |

## 7. 참가자 피드백 양식 (복사해서 사용)

```markdown
# MYELIN 파일럿 피드백

- 참가자 번호(이름 대신): P_
- 소속 유형: 컨설팅 / 관제 / 개발 / 기타
- 사용 기간: 2026-__-__ ~ 2026-__-__
- Claude Code 연동 사용: 예 / 아니오

## 1. 온보딩
- 설치부터 첫 verified 노트까지 걸린 시간(체감): __ 분
- 막힌 단계: 설치 / Vault 생성 / Obsidian 테마 / Claude Code 연결 / Promote / 없음
- 막힌 내용(오류 메시지 그대로):

## 2. 3주 사용
- 주간 verified 노트 수: 1주 __ · 2주 __ · 3주 __
- 가장 자주 쓴 기능: /ingest · /distill · /interview · /review · Hub Review Gate · 검색 · 기타
- 한 번도 쓰지 않은 기능과 이유:
- Guard 차단이나 doctor 오류로 작업이 멈춘 횟수: __ 회 (대표 사례:)

## 3. Domain Pack (해당 Pack 사용자만)
- 사용한 Pack: a3.security-consulting / a3.incident-response
- 빠진 Sub-MOC 또는 템플릿:
- 실무와 다른 용어(현재 용어 → 제안 용어):

## 4. 기록 금지 규칙
- 고객 식별 정보·고객 코드·자격증명을 쓰려다 멈춘 적이 있는가: 예 / 아니오
- 규칙 때문에 기록을 포기한 지식이 있는가(내용은 쓰지 말고 종류만):

## 5. 평가 (1 전혀 아니다 ~ 5 매우 그렇다)
- 다음 프로젝트에서 이전 노트를 실제로 다시 찾아 썼다: _
- 파일럿이 끝나도 계속 쓰겠다: _
- 동료에게 권하겠다: _

## 6. 한 가지만 고친다면
```

운영자는 5부를 모아 `docs/reports/P7/pilot-feedback.md` 의 2~5절을 채운다. 참가자 번호와 실명의 대응표는 저장소에 넣지 않는다.

## 8. 명칭·상표 점검표 (WBS 1.6) — 미완료

현재 기록은 [`docs/reports/P8/naming-check.md`](../reports/P8/naming-check.md) (2026-10-18, 자동 조회, 법률 자문 아님)이다. **KIPRIS 직접 조회는 수행되지 않았다.**

| # | 항목 | 담당 | 상태 |
|---|---|---|---|
| 1 | kipris.or.kr 에서 "MYELIN", "미엘린" 을 제9류(소프트웨어)로 검색 → 출원인, 출원일, 상태를 `naming-check.md` 1절 표에 기입 | | ☐ 미수행 |
| 2 | 같은 검색을 제42류(SaaS·소프트웨어 서비스)로 수행 | | ☐ 미수행 |
| 3 | 미국 선출원(naming-check.md 기록: "MYELIN", 심사 중)의 현재 상태 재확인 | | ☐ 미수행 |
| 4 | 대외 명칭 결정: MYELIN 유지 / 결합형(MYELIN KOS, WDLAB MYELIN) / 대안(MindForge) | | ☐ 미결정 |
| 5 | 변리사 검토(선택) | | ☐ 미수행 |
| 6 | 결정된 명칭을 README, 릴리스 노트의 "알려진 제약"에 반영 | | ☐ |

파일럿은 사내 사용이므로 현재 명칭으로 진행할 수 있다. 다만 이 저장소는 공개 저장소이므로, 4번 결정 전에는 대외 자료에 "가칭"임을 표기한다.

## 9. 종료 절차

1. `python3 scripts/pilot.py report` → `python3 scripts/pilot.py check` 가 exit 0 인지 확인
2. `docs/reports/P7/pilot-feedback.md` 의 `(TBD)` 를 모두 실제 값으로 교체
3. `make gate P=7` → 통과하면 `PHASE_STATE.md` 갱신 후 승인 요청 (태그는 승인 뒤에만)
4. 챔피언이 확정한 Pack 변경은 `myelin pack-propose` 로 Commons 에 제안
