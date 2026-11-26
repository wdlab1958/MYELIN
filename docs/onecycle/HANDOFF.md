# One Cycle 인계 절차 — MYELIN (수신 측)

> WBS 3.6 · 3.5 · ADR-0018 · 2026-11-26. 인계는 모두 **파일**이다(USB·공유 폴더). 플랫폼 사이에 네트워크가 없어도 같다.
> MYELIN 은 받기만 한다 — findings 파일이나 재진단 요청을 만들지 않는다.

## 1. 인계 표

| 방향 | 명령 | 입력 파일 | 출력 | 누가 실행 |
|---|---|---|---|---|
| LLMOps · SSC · ARGUS · Proof-Skills → MYELIN (초안 노트) | 보내는 플랫폼의 내보내기 명령(각 플랫폼 HANDOFF 참조). MYELIN 쪽 명령 없음 | 보내는 쪽이 만든 `*.md` (frontmatter `source_platform: llmops\|ssc\|argus\|proof-skills`) | `<Vault>/00_Inbox/ai-drafts/<새 파일>.md` | 보내는 플랫폼을 돌린 컨설턴트(같은 PC 의 Vault 경로를 지정). 다른 PC 면 파일을 옮겨 Vault 소유자가 폴더에 복사 |
| ARGUS → MYELIN (재진단 요청의 Markdown 사본) | 위와 같음 (`source_platform: argus`) | `rediagnosis-request` 의 `.md` 사본 | `<Vault>/00_Inbox/ai-drafts/<새 파일>.md` | ARGUS 운영자 → Vault 소유자 |
| 임의 플랫폼 → MYELIN (findings 가져오기) | `myelin onecycle import-findings <file.json> --vault <Vault> [--domain <ID>] [--dry-run] [--json]` | `onecycle.findings/v1` JSON ([스키마](onecycle.findings.v1.schema.json)) | finding 하나당 `<Vault>/00_Inbox/ai-drafts/<플랫폼> - <제목> (<해시>).md` | Vault 소유자 |
| (점검) 받은 초안 확인 | `myelin doctor --vault <Vault>` · `myelin guard scan --vault <Vault> 00_Inbox/ai-drafts` | — | 표준 출력, 종료 코드 | Vault 소유자 |
| (승격) 초안 → 검증된 노트 | Hub `myelin-hub --vault <Vault>` → Review Gate → "내용 읽기" → Promote | 초안 | `10_Domains/<Domain>/<파일>.md` + commit `[myelin:review] promote …` | Vault 소유자(사람의 클릭만) |

## 2. 한 번만 하는 준비

```bash
# 받을 플랫폼의 Domain 을 Vault 에 더한다 (필요한 것만)
myelin add-domain LLMOPS --vault ~/Vaults/me --pack wdlab.onecycle
myelin add-domain SSC    --vault ~/Vaults/me --pack wdlab.onecycle
myelin add-domain ARGUS  --vault ~/Vaults/me --pack wdlab.onecycle
# PROOF-SKILLS 는 WDLAB-Proof-Skills 가 배포하는 Pack: <Vault>/packs/ 에 복사 후
myelin add-domain PROOF-SKILLS --vault ~/Vaults/me --pack wdlab.proof-skills
# 고객명 목록 (지식 관리 지침 §4) — 프로젝트마다
printf '%s\n' '<고객사 이름>' >> ~/Vaults/me/.myelin/customer-names.txt
```
Domain 을 더하지 않아도 초안은 받는다. 그때는 초안에 `domain` 이 비고, 승격할 때 사람이 Domain 을 고른다.

## 3. 수동 절차 (finding 파일)

1. 보내는 쪽: 자기 플랫폼의 내보내기로 `onecycle.findings/v1` 파일을 만든다. 실제 대상에서 측정하지 않은 결과는 `simulated: true`. 고객명·고객 코드·자격증명은 넣지 않는다.
2. 파일을 Vault 가 있는 PC 로 옮긴다.
3. Vault 소유자:
   ```bash
   myelin onecycle import-findings findings.json --vault ~/Vaults/me --dry-run   # 무엇이 생길지 본다
   myelin onecycle import-findings findings.json --vault ~/Vaults/me
   ```
   | 종료 코드 | 뜻 |
   |---|---|
   | 0 | 모두 생성(또는 이미 있어 건너뜀) |
   | 1 | 고객정보 가드가 일부 finding 을 막았다(나머지는 생성). 보내는 쪽에 돌려보내 고친다 |
   | 2 | 파일 거부(스키마 위반·빈 findings·중복 id·읽기 실패·없는 Domain) — 아무것도 쓰지 않았다 |
4. Hub Review Gate 에서 읽고 승격한다. `[가드 표시]` 가 붙은 초안은 승격 때 확인을 한 번 더 묻는다.
5. 같은 파일을 다시 가져와도 같은 finding 은 다시 생기지 않는다(초안·승격본·기각본 어디에 있든).

## 4. 보장하는 것 / 하지 않는 것

- 가져오기는 `00_Inbox/ai-drafts` 에 **새 파일만** 만든다. 덮어쓰지 않고, `myelin.yaml` 을 고치지 않고, git 을 실행하지 않는다.
- 파일의 값만 옮긴다. 판정을 보태거나 증거를 만들어 내지 않는다. 증거는 참조(`kind`·`ref`·`sha256`)만 옮기고 원본은 보내는 플랫폼에 남는다.
- verified 승격은 사람만 한다.
- 다섯 플랫폼의 실제 내보내기를 끝에서 끝까지 이어 돌린 검증은 이 저장소에서 하지 않았다. 표본(`samples/`)과 스키마로 검증했다.

## 5. 표본 (`samples/`, 가상 데이터)

| 파일 | 내용 |
|---|---|
| `findings.{llmops,ssc,argus,proof-skills}.sample.json` | `onecycle.findings/v1`, 모두 `simulated: true`. `links.upstream` 으로 llmops → ssc → argus 가 이어진다 |
| `draft.{llmops,ssc}.sample.md` | `source_platform` 초안 |
| `draft.argus-rediagnosis.sample.md` | 재진단 요청의 Markdown 사본 |

검증: `.venv/bin/python -m pytest packages/myelin-core/tests/test_onecycle.py packages/myelin-hub/api/tests/test_guard_onecycle_hub.py -q`
