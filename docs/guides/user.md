# 사용자 가이드 — MYELIN v1.0

> 쓸수록 빨라지는 나의 지식 신경망. 경험을 **검증된(verified) 노트**로 바꾸고, 다음 일에 다시 씁니다.

## 1. 하루의 흐름
```
자료·메모 ──▶ 00_Inbox ──(Claude: /ingest, /distill)──▶ 00_Inbox/ai-drafts
                                                         │
                                  Hub Review Gate (사람) ▼ Promote → verified + git commit
                                                10_Domains/<Domain>/  ──▶  /compose 산출물
```
- **사람만 verified 를 만든다.** Claude는 초안만 씁니다. 승격은 Hub의 Review Gate에서 원문을 보고 누릅니다.
- 승격된 노트도 `origin: claude` 는 남습니다 — 누가 썼는지 지워지지 않습니다.
- 반려는 삭제가 아니라 `99_Archive/rejected/` 로 이동(`deprecated`).

## 2. Vault 구조
| 폴더 | 내용 | Claude 쓰기 |
|---|---|---|
| `00_Inbox/` | 원료 메모(frontmatter 없어도 됨), `ai-drafts/`(Claude 초안), `clips/` | ai-drafts만 (Level ≥ 1) |
| `10_Domains/<ID>/` | Domain별 verified 지식과 `_MOC.md` | ✗ |
| `20_Projects/` · `30_Resources/` | 프로젝트 · 참고 | ✗ |
| `40_IP/` | 특허·직무발명 — **Claude로 보내지 않음** | `candidates/` 만 (Level 3, 로컬 LLM) |
| `50_Journal/` | 일일·주간 리뷰 | `reviews/` (Level ≥ 1) |
| `80_Outputs/` | 산출물 | `drafts/` (Level ≥ 2) |
| `90_System/` | 템플릿·용어 사전·질문 은행·lock | ✗ |

## 3. 노트 frontmatter (필수)
```yaml
id: 20261018-0712-45123        # 템플릿이 자동 생성, 바꾸지 않음
type: evergreen                # fleeting|literature|evergreen|moc|adr|experiment|lesson|checklist|idea-ip
domain: [AI-ML-AX]
status: draft                  # draft|unverified|verified|deprecated
origin: human                  # human|claude|mixed
classification: internal       # public|internal|confidential
share: false                   # true 일 때만 Commons 공개 후보
created: 2026-10-18
```
`myelin doctor ~/MyVault` 가 스키마 위반, 고아 노트, "verified 가 미검증 AI 노트를 링크" 같은 fail-closed 위반을 찾습니다.

## 4. Claude 권한 Level (Hub Settings)
| Level | Claude가 할 수 있는 것 |
|---|---|
| 0 | 읽기만 |
| 1 | ai-drafts 초안, 주간 리뷰 (기본) |
| 2 | + 링크·MOC 변경 제안(`_patches`), 산출물 초안 |
| 3 | + 특허 후보 추출 (로컬 LLM 라우팅) |
Vault 안의 Guard Hook이 실제로 막습니다. Claude가 이 설정 자체를 바꾸는 것도 막힙니다.

## 5. Claude Code 스킬
| 스킬 | 하는 일 | Level |
|---|---|---|
| `/myelin:ingest` | 파일·URL·PDF → literature 초안 | 1 |
| `/myelin:distill` | Inbox 메모 → 원자 노트 초안 | 1 |
| `/myelin:interview` | Pack 질문 은행으로 암묵지 인터뷰 → lesson 초안 | 1 |
| `/myelin:review` | 주간 품질 보고서 | 1 |
| `/myelin:link` | 링크·MOC 변경 제안 | 2 |
| `/myelin:compose` | 목적·독자 기반 산출물 초안 | 2 |
| `/myelin:ip-scan` | Cross-domain 특허 후보 | 3 |

## 6. Hub 화면
| 화면 | 용도 |
|---|---|
| Dashboard | Verified·AI 초안·승격률(40~70% 목표)·Cross-domain, doctor 결과, 최근 git 기록 |
| My Domains | Domain Map, Domain 추가 (3+1 규칙) |
| Review Gate | 검토 대기 노트 → 원문 확인 → Promote / Reject |
| Domain Packs | 설치 가능한 Pack, pack.yaml 검증 |
| Team Commons | (조직이 켠 경우) 공개 제안 |
| Settings | Level, MCP 초안 쓰기, 익명 지표 동의, 기밀 경계 확인, 로컬 git |

## 7. 기밀과 공유
- `classification: confidential` 과 `40_IP/` 는 Claude·MCP로 나가지 않습니다. 경계(`llm.route`)는 Hub에서 바꿀 수 없습니다.
- 공유는 **share: true + verified + internal 이하** 노트만, Team Commons 화면에서: 자동 비식별 검사 → 본인 확인 5항목 →
  제안 → "조직으로 보내기" 확인 → 챔피언 리뷰. 고객명·IP·연락처·키가 있으면 자동 차단됩니다.
- 지표는 동의한 경우에만, 파일로만 (`myelin metrics ~/MyVault --out m.json`) — 내용을 보고 직접 제출합니다.

## 8. 명령 요약
```bash
myelin init <Vault> [--interactive]          myelin doctor <Vault> [--strict]
myelin add-domain <Vault> --domain X --role research|growth|extra
myelin stats <Vault> [--json]                myelin packs
myelin commons link <Vault> <clone>          myelin commons check <Vault> <노트>
myelin metrics <Vault> [--out file]          myelin-hub --vault <Vault> [--open]
myelin-mcp --vault <Vault>
```
