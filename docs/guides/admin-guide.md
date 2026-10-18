# MYELIN 관리자 가이드 (v1.0, 조직 운영자·챔피언)

## 1. 구성 요소와 포트
| 구성 | 실행 | 비고 |
|---|---|---|
| Hub | `myelin-hub --vault <v> --port 8787` | localhost 전용. 비-loopback 바인딩 거부. Host/Origin 검증 |
| MCP | `claude mcp add myelin -- uv --directory <repo> run myelin-mcp --vault <v>` | stdio, 읽기 전용 기본 |
| Plugin | `claude plugin marketplace add <repo>` → `claude plugin install myelin@myelin-local` | `claude plugin validate <repo>/plugin --strict` |
| Commons | 사내 git (`myelin commons init <dir>` 후 push) | 구성원은 `MYELIN_PACKS=<clone>/registry/packs` |

## 2. Commons 운영
1. `myelin commons init /srv/myelin-commons` → 원격 생성·push.
2. Org Pack 등록: `myelin commons add-pack packs/org.security-consulting --commons <clone> --champion <이름>`.
3. `deid.yaml` 에 고객명·프로젝트 코드 등 금칙어 유지(Commons 공통). 각 Vault 의 `90_System/deid.yaml` 로 보강 가능.
4. PR 리뷰(챔피언): 비식별 확인 → merge. main 직접 커밋 금지.
5. 지표: `myelin metrics aggregate <clone>` (opt-in 한 사람의 숫자만 모인다).

## 3. 보안 정책 (정본 §9.1, 위협 모델 docs/security/threat-model.md)
- 개인 Vault 불가침 — 관리자는 Vault 에 접근하지 않는다. 지표는 opt-in 익명 집계만.
- 외부 AI 사용 범위: `classification: confidential` 과 `40_IP/` 는 외부 LLM 금지(`llm.route`, MCP 기본 비노출). HR·법무·보안과 지식 소유권·직무발명 절차를 **사전 합의**(정본 §9.1).
- Hub 는 공유 호스트에서 띄우지 않는다(같은 호스트의 다른 사용자가 접근 가능). Team 모드 인증은 v1.1.

## 4. 배포 (Rollout, 정본 §9.2)
Alpha(Brian, 2주) → Pilot(5~10명, 3주, `docs/guides/pilot-guide.md`) → Wave 1(희망 팀) → Wave 2(전사). 각 단계 종료 시 `scripts/pilot.py report`, `myelin metrics aggregate`.

## 5. 업그레이드
```bash
git pull && scripts/install.sh --vault <v>     # 멱등. 테마는 .bak 백업 후 갱신
make gate P=8                                   # 전체 검사
```
Vault 포맷(Frontmatter v2, myelin.yaml) 변경은 ADR 선행. `myelin doctor` 로 마이그레이션 검증.

## 6. CI
`.github/workflows/ci.yml` — lint/typecheck/test + `make gate P=<current>`. e2e(Playwright) 는 Node 22 + Chrome 채널이 필요하다(`make web`, `make e2e`).
