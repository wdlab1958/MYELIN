# MYELIN 사용자 가이드 (v1.0)

> 쓸수록 빨라지는 나의 지식 신경망. 경험을 노트로 감싸고(캡처), 반복해서 연결·재사용할수록(Distill·Link·Compose) 지식 경로가 빨라진다.

## 1. 설치 (15분 목표) — 다운로드 → 설치 → 초기화
순서는 **git clone → `scripts/install.sh` → `myelin-hub --vault <빈 폴더>` → 온보딩 마법사**이다. Vault 는 빈 폴더에서 새로 만들며, 다른 사람의 노트나 Domain 을 가져오지 않는다. 마법사에서 Domain 은 조직 Pack 에서 고르거나 직접 정의한다(Reference Pack 은 참고용).
```bash
git clone <repo> myelin && cd myelin
scripts/install.sh --vault ~/Vaults/me --claude   # python/uv 검사 → sync → Hub 빌드 → 런처 → Obsidian 테마 (+ --claude: plugin/MCP 등록)
myelin-hub --vault ~/Vaults/me                 # http://127.0.0.1:8787 → 온보딩 마법사
```
CLI 로 하려면 `myelin init --vault ~/Vaults/me`. 둘 다 같은 로직이다.

## 2. 개념 한 장
| 용어 | 뜻 |
|---|---|
| Vault | 내 Obsidian 폴더. Markdown + YAML 정본. 내 것이며 조직은 열람하지 않는다 |
| Domain (3+1) | Primary(업무 근간) · Research · Growth · 선택 +1. Pack 이 공급 |
| Pack | Domain 선언(YAML). Core / Reference(brian.physical-ai) / Org(a3.*) / Personal(me.*) |
| ai-draft | Claude 가 만든 초안. `00_Inbox/ai-drafts/` 에만 생긴다. Cyan |
| verified | 사람이 Review Gate 에서 승격한 노트. Lime 링(myelinated). git commit 으로 기록 |
| Level | 0 읽기 전용 · 1 초안 · 2 링크 패치 · 3 정기 리뷰. `myelin.yaml level` 은 사람만 바꾼다 |

## 3. 매일
1. 메모는 `00_Inbox/` 에. 7일 안에 `/myelin:distill`.
2. 외부 자료는 `/myelin:ingest <파일|URL>` → literature 초안.
3. Hub › Inbox / Review Gate 에서 **Promote**(verified) 또는 Reject.
4. 주 1회 `/myelin:review` → 지표와 doctor 할 일. `myelin doctor` 는 언제든.
5. 경험은 `/myelin:interview` 로 lesson 노트에.
6. **승격은 읽은 뒤에**: Review Gate 의 Promote 는 "내용 읽기" 로 본문을 연 뒤에만 켜진다. 읽지 않은 승격은 장치가 막는다.
7. **환류**: `/myelin:compose` 로 만든 산출물에는 `## 환류 후보` 절이 생긴다. `/myelin:distill 80_Outputs/drafts/<산출물>.md` 로 그 절을 원자 노트 초안으로 되돌리고 Review Gate 에서 승격한다. 산출물 안에만 남은 지식은 다시 쓰이지 않는다.
8. **모르면 도우미에게**: Hub 우측 하단 말풍선(도우미)을 누르면 MYELIN 도우미(AI)가 열린다. 개념·절차·명령과 이 Vault 의 상태(Level·Domain·KPI·관련 노트)를 답하고 근거 노트를 Obsidian 링크로 준다. 로컬 Ollama(`http://127.0.0.1:11434`)가 켜져 있으면 LLM 이 답하고, 없으면 "지식 기반 모드" 로 내장 지식 절을 그대로 보여 준다. 도우미는 안내만 하며 승격·적용·공개는 여전히 사람이 버튼으로 한다(ADR-0013).
9. **강도(myelin ×N)**: Dashboard 와 My Domains 의 노트 표에 노트별 강도가 텍스트로 보인다. 1 = verified, 2 = 두 곳 이상에서 링크되거나 산출물 재료로 쓰임, 3 = Commons 에서 인용됨. Dashboard 의 "재사용 비율"·"재투입 소요일"·"산출물당 재료 수" 가 목표를 벗어나면 "목표 이탈" 이 뜬다(ADR-0012).

## 4. Claude Code 에서
- Vault 폴더에서 `claude` 실행. plugin 이 설치되어 있으면 `/myelin:ingest` 등이 보인다(없으면 `claude --plugin-dir <repo>/plugin`).
- Guard 가 사람 승인 영역(`10_Domains/`, `40_IP/`, `90_System/`, `myelin.yaml`) 쓰기를 차단한다. 차단 메시지가 뜨면 우회하지 말고 `_patches/` 제안(Level ≥ 2)으로.
- MCP(`search_notes`, `get_note` …)는 읽기 전용. confidential 노트는 본문을 돌려주지 않는다.
- **기밀은 외부 LLM 에 가지 않는다(장치)**: 세션에 `MYELIN_LLM=local` 이 없으면 Claude Code 는 `40_IP/**` 와 `classification: confidential` 노트를 Read/Grep/Glob/Write 할 수 없다(Guard 차단). 로컬 LLM 세션에서만 `MYELIN_LLM=local` 을 켠다. MCP 서버도 로컬 프로세스가 아니면 `expose_confidential` 을 무시한다(ADR-0011).
- **Claude Code 밖에서 바꾼 것도 커밋 시점에 검사된다**: `myelin init` 이 Vault 에 git pre-commit 훅을 설치한다(`myelin doctor --staged`). `origin: claude` 노트가 허용 범위 밖에 있거나 검토 없이 verified 면 커밋이 거부된다. 기존 Vault 는 `myelin doctor --install-hook`.

## 5. Obsidian
MYELIN 과 Obsidian 의 연동은 플러그인이 아니라 **테마 + 파일 규약**이다. 상세는 [`docs/guides/obsidian-setup.md`](obsidian-setup.md).
- **어느 Vault 인가**: MYELIN Vault 는 `myelin.yaml` 이 있는 폴더다. Obsidian 이 처음 만드는 `~/Obsidian Vault` 는 MYELIN 과 무관하므로 왼쪽 아래 Vault 전환으로 MYELIN Vault 를 연다.
- **테마 파일**: `myelin init`/Hub 온보딩이 만든 Vault 에는 `.obsidian/themes/MYELIN Emboss/` 와 `appearance.json`(라이트·테마 선선택)이 이미 있다. 기존 Vault 는 `scripts/install.sh --vault <Vault>` 또는 `theme/obsidian-myelin-emboss/` 를 `<Vault>/.obsidian/themes/MYELIN Emboss/` 로 복사(폴더 이름 = manifest.json 의 name).
- **Settings**: Appearance › Base color scheme **Light** › Themes **Manage** › **MYELIN Emboss**. 목록에 없으면 `Ctrl+P` › *Reload app without saving*.
- **상태 표시**: frontmatter `cssclasses: [mx-status-verified]`(라임 링 + verified 칩) / `[mx-status-ai-draft]`(시안 glow) / `[mx-status-blocked]`(마젠타 외곽선). 미지 필드이지만 허용·보존된다(ADR-0003).
- **색 변경**: `theme.css` 가 아니라 `design/tokens.json` → `make emboss` → 복사.
- Obsidian 자체가 없으면 `scripts/install_obsidian.sh --vault <Vault>` (Debian/Ubuntu).
- **Graph View**: Vault 에 `.obsidian/graph.json` 이 함께 생성돼 Domain 폴더가 Emboss 색으로 묶인 링크 그래프가 바로 보인다(`Ctrl/Cmd+G`). 기존 Vault 는 Hub Dashboard 의 *Obsidian Graph View › 설정 쓰기* 또는 `myelin obsidian setup --vault <Vault> --open` (가이드 6절).

## 6. 공유 (Commons)
- 공개하고 싶은 verified 노트에 `share: true`. Hub › Review Gate › **Commons 후보** 에서 비식별 검사 → 확인 체크 → "Commons 제안" → 브랜치/PR → 챔피언 merge.
- 고객명·IP·시스템명을 쓰지 않는다. 쓰면 제안이 차단된다.
- Hub 에서 "push 하고 PR 을 만든다" 를 체크하면 브랜치 push 와 PR(`gh`) 까지 한 번에 간다. 체크하지 않으면 로컬 브랜치까지만 만들고 다음 명령을 안내한다. 원격은 Settings › Commons 의 `commons.remote` 를 쓴다.
- **두 정체성**: Commons 노트에는 작성자 이름과 원 노트 id 가 **실명**으로 남아 기여가 평판이 된다(Commons 집계의 `top_contributors`, 노트별 인용 수). 반면 `myelin.yaml commons.metrics_opt_in: true` 로 보내는 지표는 owner 해시와 숫자·id 목록만이며 기본은 꺼짐.

## 7. 명령 요약
`myelin init | add-domain | doctor | stats | skills | interview-bank | publish | pack-propose | metrics | commons` · `myelin-mcp --vault` · `myelin-hub --vault`

## 8. 문제 해결
- `myelin doctor` 오류 → 메시지의 규칙 이름(schema / fail-closed / orphan / confidential-share / broken-link / duplicate-id / domain / temporal)으로 `docs/reports/P2.md` 표 참조.
- Guard 가 전부 막는다 → Vault 에 `myelin.yaml` 이 있는지, `level` 이 0 이 아닌지 확인.
- Hub 가 403 → localhost 로 접속하는지(`127.0.0.1`), 다른 사이트 탭에서 호출하지 않았는지.
- 도우미가 "지식 기반 모드" → Ollama 가 꺼져 있거나 모델이 없다. `ollama serve` 후 다시 열면 LLM 모드가 된다. 다른 주소·모델은 `MYELIN_ASSISTANT_URL` · `MYELIN_ASSISTANT_MODEL` 환경변수로 지정한다(loopback 이 아닌 주소면 기밀 노트는 컨텍스트에서 빠진다).
