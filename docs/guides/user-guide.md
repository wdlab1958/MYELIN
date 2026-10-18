# MYELIN 사용자 가이드 (v1.0)

> 쓸수록 빨라지는 나의 지식 신경망. 경험을 노트로 감싸고(캡처), 반복해서 연결·재사용할수록(Distill·Link·Compose) 지식 경로가 빨라진다.

## 1. 설치 (15분 목표)
```bash
git clone <repo> myelin && cd myelin
scripts/install.sh --vault ~/Vaults/me        # python/uv 검사 → sync → Hub 빌드 → 런처 → plugin → MCP → Obsidian 테마
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

## 4. Claude Code 에서
- Vault 폴더에서 `claude` 실행. plugin 이 설치되어 있으면 `/myelin:ingest` 등이 보인다(없으면 `claude --plugin-dir <repo>/plugin`).
- Guard 가 사람 승인 영역(`10_Domains/`, `40_IP/`, `90_System/`, `myelin.yaml`) 쓰기를 차단한다. 차단 메시지가 뜨면 우회하지 말고 `_patches/` 제안(Level ≥ 2)으로.
- MCP(`search_notes`, `get_note` …)는 읽기 전용. confidential 노트는 본문을 돌려주지 않는다.

## 5. Obsidian
MYELIN 과 Obsidian 의 연동은 플러그인이 아니라 **테마 + 파일 규약**이다. 상세는 [`docs/guides/obsidian-setup.md`](obsidian-setup.md).
- **어느 Vault 인가**: MYELIN Vault 는 `myelin.yaml` 이 있는 폴더다. Obsidian 이 처음 만드는 `~/Obsidian Vault` 는 MYELIN 과 무관하므로 왼쪽 아래 Vault 전환으로 MYELIN Vault 를 연다.
- **테마 파일**: `myelin init`/Hub 온보딩이 만든 Vault 에는 `.obsidian/themes/MYELIN Emboss/` 와 `appearance.json`(라이트·테마 선선택)이 이미 있다. 기존 Vault 는 `scripts/install.sh --vault <Vault>` 또는 `theme/obsidian-myelin-emboss/` 를 `<Vault>/.obsidian/themes/MYELIN Emboss/` 로 복사(폴더 이름 = manifest.json 의 name).
- **Settings**: Appearance › Base color scheme **Light** › Themes **Manage** › **MYELIN Emboss**. 목록에 없으면 `Ctrl+P` › *Reload app without saving*.
- **상태 표시**: frontmatter `cssclasses: [mx-status-verified]`(라임 링 + verified 칩) / `[mx-status-ai-draft]`(시안 glow) / `[mx-status-blocked]`(마젠타 외곽선). 미지 필드이지만 허용·보존된다(ADR-0003).
- **색 변경**: `theme.css` 가 아니라 `design/tokens.json` → `make emboss` → 복사.
- Obsidian 자체가 없으면 `scripts/install_obsidian.sh --vault <Vault>` (Debian/Ubuntu).

## 6. 공유 (Commons)
- 공개하고 싶은 verified 노트에 `share: true`. Hub › Review Gate › **Commons 후보** 에서 비식별 검사 → 확인 체크 → "Commons 제안" → 브랜치/PR → 챔피언 merge.
- 고객명·IP·시스템명을 쓰지 않는다. 쓰면 제안이 차단된다.
- `myelin.yaml commons.metrics_opt_in: true` 로 익명 지표(숫자만)를 보낼 수 있다. 기본은 꺼짐.

## 7. 명령 요약
`myelin init | add-domain | doctor | stats | skills | interview-bank | publish | pack-propose | metrics | commons` · `myelin-mcp --vault` · `myelin-hub --vault`

## 8. 문제 해결
- `myelin doctor` 오류 → 메시지의 규칙 이름(schema / fail-closed / orphan / confidential-share / broken-link / duplicate-id / domain / temporal)으로 `docs/reports/P2.md` 표 참조.
- Guard 가 전부 막는다 → Vault 에 `myelin.yaml` 이 있는지, `level` 이 0 이 아닌지 확인.
- Hub 가 403 → localhost 로 접속하는지(`127.0.0.1`), 다른 사이트 탭에서 호출하지 않았는지.
