# Obsidian 연동 가이드 — MYELIN Emboss 테마 · 상태 표시 · Graph View (v1.3.1)

MYELIN 은 Obsidian 의 Markdown 파일을 정본으로 삼는다. Obsidian 쪽 연동은 **Obsidian 플러그인이 아니라 테마(CSS)와 파일 규약**으로 이루어진다(정본 §4.1 L4 "Obsidian Emboss Theme"). 따라서 설치할 것은 테마 폴더 하나이고, 나머지는 노트의 frontmatter 가 한다.

## 0. 먼저 확인할 것 — "어느 Vault 를 열었나"
- MYELIN Vault 는 **`myelin.yaml` 이 있는 폴더**이다(`myelin init` 또는 Hub 온보딩이 만든 폴더, 예: `~/Vaults/me`).
- Obsidian 을 처음 실행하면 Obsidian 이 스스로 `~/Obsidian Vault` 같은 **기본 Vault 를 만들어 열 수 있다. 이 폴더는 MYELIN 과 무관**하다. 창 왼쪽 아래의 Vault 이름을 눌러(Vault 전환) MYELIN Vault 를 열거나, *Open folder as vault* 로 MYELIN Vault 폴더를 지정한다.
- 명령줄에서 바로 열기: `scripts/install_obsidian.sh --vault <Vault>` 또는 `xdg-open "obsidian://open?path=<Vault 절대경로>"`.

## 1. 테마 파일 넣기
| 방법 | 절차 |
|---|---|
| **자동 (권장)** | `myelin init` 과 Hub 온보딩이 만드는 Vault 에는 `.obsidian/themes/MYELIN Emboss/` 와 `.obsidian/appearance.json`(라이트 + MYELIN Emboss 선선택)이 **이미 들어 있다**. 할 일이 없다 |
| 설치 스크립트 | 기존 Vault 에 넣으려면 `scripts/install.sh --vault <Vault>` (또는 `scripts/install_obsidian.sh --vault <Vault>`). 같은 파일이 있으면 `.bak` 으로 백업한 뒤 갱신한다 |
| 수동 복사 | 저장소의 `theme/obsidian-myelin-emboss/` 안 `manifest.json`·`theme.css` 를 `<Vault>/.obsidian/themes/MYELIN Emboss/` 로 복사한다 |

**폴더 이름 규칙**: 테마 폴더 이름은 `manifest.json` 의 `name` 값(`MYELIN Emboss`)과 **정확히 같아야** Obsidian 이 목록에 올린다. 공백 포함, 대소문자 동일. `.obsidian` 폴더가 아직 없는 Vault 라도 미리 만들어 두면 Obsidian 이 열 때 그대로 유지한다.

## 2. Settings 에서 고르기 (자동 선선택이 안 된 경우)
1. Settings(왼쪽 아래 톱니) › **Appearance**
2. **Base color scheme → Light**. v1.0 의 Emboss 는 라이트 전용이다(정본 §8.3 가드레일 5). Dark 를 골라도 깨지지는 않지만 라이트 값이 그대로 적용된다.
3. **Themes → Manage** → 목록에서 **MYELIN Emboss** 선택. 커뮤니티 테마 다운로드가 아니라 로컬 설치 테마이므로 인터넷 없이 보인다.

## 3. 목록에 없을 때
| 증상 | 확인 | 조치 |
|---|---|---|
| Themes 목록에 MYELIN Emboss 가 없다 | `<Vault>/.obsidian/themes/MYELIN Emboss/manifest.json` 존재 여부, 폴더 이름 | `Ctrl+P` › *Reload app without saving* 또는 Obsidian 재시작 |
| 고른 뒤에도 모양이 그대로다 | `appearance.json` 의 `cssTheme` 값 | `"cssTheme": "MYELIN Emboss"` 로 수정 후 재시작 |
| 다른 Vault 를 보고 있다 | 창 제목의 Vault 이름 | 0절대로 MYELIN Vault 로 전환 |
| 테마가 깨져 보인다 | `theme.css` 첫 줄이 `GENERATED from design/tokens.json` 인지 | `make emboss` 후 다시 복사(손으로 고친 theme.css 는 생성물에 덮인다) |

## 4. 노트에 상태 표시하기 — frontmatter 와 cssclasses
Obsidian 은 frontmatter 의 `cssclasses` 값을 그 노트의 보기 영역에 CSS 클래스로 붙인다. Emboss 는 이 클래스를 읽어 **노트 제목**에 링·glow·외곽선을 그리고, 제목 옆에 글자 칩을 붙인다(색만으로 상태를 전달하지 않는다 — 정본 §8.3 가드레일 4).

```yaml
---
id: 20261018-0900-wcet-budget
type: evergreen
domain: [D2]
status: verified
origin: mixed
confidence: high
classification: internal
share: false
source: []
created: 2026-10-18
reviewed: 2026-10-18
tags: [rtos]
cssclasses: [mx-status-verified]
---
```

| `cssclasses` 값 | 제목에 그려지는 것 | 쓰는 때 |
|---|---|---|
| `mx-status-verified` | 라임 링 + **verified** 칩 (myelinated) | Review Gate 에서 승격한 노트. 승격 시 자동으로 붙지는 않으므로 필요할 때 적는다 |
| `mx-status-ai-draft` | 시안 glow + **ai-draft** 칩 | `00_Inbox/ai-drafts` 의 초안을 구분해 보고 싶을 때 |
| `mx-status-blocked` | 마젠타 외곽선 + **blocked** 칩 | doctor 가 지적했거나 Guard 에 막힌 노트를 표시해 둘 때 |

- `cssclasses` 는 Frontmatter v2 의 12개 정본 필드가 아니지만, MYELIN 은 미지 필드를 허용·보존하므로(ADR-0003) `myelin doctor` 는 오류가 아니라 info(extra-field)로만 알린다.
- Dataview 플러그인을 쓰면 `status` 필드로 같은 클래스를 자동으로 붙이는 방법도 있다(선택).

## 5. 색을 바꾸고 싶을 때
`theme.css` 는 **생성물**이다. 색·그림자·반경은 `design/tokens.json` 에서 바꾸고 `make emboss` 로 `design/dist/emboss.css`, Tailwind preset, `theme/obsidian-myelin-emboss/theme.css` 를 함께 다시 만든 뒤, `make a11y`(대비 4.5:1)와 `make emboss-lint`(하드코딩 0)를 통과시키고 설치 스크립트로 Vault 에 복사한다. Hub 와 Obsidian 이 항상 같은 색을 쓰게 하는 장치이다.

## 6. Graph View — Domain 이 색으로 묶인 링크 그래프 (v1.3.1)
`myelin init` 과 Hub 온보딩이 만드는 Vault 에는 `.obsidian/` 설정 세 개가 **함께 들어 있다**. 기존 Vault 는 `myelin obsidian setup --vault <Vault>` 또는 Hub Dashboard 의 **Obsidian Graph View › "Graph View 설정 쓰기"** 버튼 한 번으로 같은 상태가 된다(있는 파일은 덮어쓰지 않고 빠진 항목만 보탠다).

| 파일 | 내용 |
|---|---|
| `core-plugins.json` | **Graph**·Backlinks·Outgoing links·Tags·Properties·Templates 켜짐. Daily notes(50_Journal 은 MYELIN 것)·Sync·Publish 꺼짐 |
| `graph.json` | **Domain 폴더마다 색 그룹 하나** — `path:10_Domains/D1/` = 그 Domain 의 Emboss accent(violet·cyan·lime·magenta, `design/tokens.json` 값 그대로) + `00_Inbox/`(muted)·`40_IP/`(magenta-ink)·`99_Archive/`(border). 태그 표시, 미해결 링크 숨김(Sub-MOC 자리표시) |
| `app.json` | 새 노트 → `00_Inbox`, `[[stem]]` 위키링크(색인·doctor 가 푸는 형식), 이름 변경 시 링크 자동 갱신 |

- **열기**: Obsidian 에서 `Ctrl/Cmd+G`(Graph View) 또는 왼쪽 리본의 그래프 아이콘. Hub Dashboard 의 "Obsidian 에서 Vault 열기" 는 `obsidian://open?path=<Vault>` 다. **Advanced URI** 커뮤니티 플러그인이 설치돼 있으면 같은 버튼이 `obsidian://advanced-uri?vault=<이름>&commandid=graph:open` 으로 Graph View 를 바로 연다.
- **Vault 등록**: Obsidian 은 자기 목록(`~/.config/obsidian/obsidian.json`)에 있는 Vault 만 URI 로 연다. 처음 한 번은 `myelin obsidian setup --vault <Vault> --open` 이나 Obsidian 의 *Open folder as vault* 로 연다. Hub 의 Obsidian 카드가 "등록됨/미등록" 을 보여 준다(`myelin obsidian status`).
- **노트 단위 그래프**: 노트를 연 뒤 오른쪽 패널의 *Backlinks*·*Outgoing links*, 또는 명령 "Open local graph".
- Hub 의 Domain Orb 와 Graph View 의 색은 **같은 토큰**에서 나온다. 색을 바꾸려면 5절(`design/tokens.json` → `make emboss`) 뒤 `myelin obsidian setup` 을 다시 실행하되, 이미 있는 그룹의 색은 사용자의 것이므로 바꾸지 않는다 — 새 색을 쓰려면 `graph.json` 의 해당 그룹을 지우고 다시 실행한다.

## 7. 무엇이 달라 보이나
- 배경과 카드가 같은 색(surface)이고 경계는 그림자로만 구분된다. 입력창은 함몰(inset), 콜아웃은 돌출(raised).
- 링크·강조·태그는 Violet, 승격된 노트의 제목은 Lime 링, AI 초안은 Cyan glow 로만 색이 켜진다.
- 다크 모드는 v1.0 범위 밖이다.
