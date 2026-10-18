# 설치 가이드

지원: **macOS · Linux · Windows(WSL2)**. Windows 기본 환경(PowerShell)은 v1.0에서 검증하지 않았습니다 — WSL2를 쓰세요.

## 1. 준비물
| 도구 | 용도 | 확인 |
|---|---|---|
| git | 소스 받기, Vault 기록 | `git --version` |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Python 3.12+ 와 의존성 (자동 설치) | `uv --version` |
| Node.js 18+ (선택) | Hub 웹 화면 빌드 | `node --version` |
| Obsidian + Templater 플러그인 | 노트 편집 | — |
| Claude Code (선택) | `/myelin:*` 스킬 | `claude --version` |

## 2. 설치 (5분 이내)
```bash
git clone https://github.com/wdlab1958/MYELIN.git
bash MYELIN/scripts/install.sh            # 내용을 먼저 읽어 보세요 — sudo·시스템 변경 없음
export PATH="$HOME/.local/bin:$PATH"      # 안내가 나오면 셸 설정에 추가
myelin --version
```
- 설치 위치: `~/.local/share/myelin` (`MYELIN_HOME`), 실행 파일: `~/.local/bin` (`MYELIN_BIN`).
- 특정 버전: `bash MYELIN/scripts/install.sh --ref v1.0.0`
- 갱신: 같은 명령을 다시 실행 (설치 폴더에 수정이 있으면 멈춥니다).
- 의존성은 lockfile 그대로 설치합니다 (`uv sync --frozen`, `npm ci`).

## 3. 첫 Vault — 온보딩 마법사 (10분)
```bash
myelin-hub --vault ~/MyVault --open
```
터미널에 출력된 `http://127.0.0.1:8765/?token=…` 링크로 열립니다 (이번 실행에서만 유효, 공유 금지).
이름 → Pack → **3+1 Domain** → Level → 확인 → "Vault 만들기". "로컬 git으로 기록"은 켜 두세요 (승격에 필요).

CLI로 만들 수도 있습니다: `myelin init ~/MyVault --interactive`

> Vault는 **독립 폴더**에 만드세요. MYELIN 소스 폴더나 다른 git 저장소 안에는 만들어지지 않습니다 (개인 노트 유출 방지).

## 4. Obsidian · Claude Code 연결
1. Obsidian → "폴더를 보관함으로 열기" → `~/MyVault`. Templater 플러그인을 켜고 템플릿 폴더를 `90_System/templates` 로.
2. (선택) Emboss 테마: [theme/README.md](../../theme/README.md)
3. Claude Code (Vault 폴더에서):
   ```
   /plugin marketplace add wdlab1958/MYELIN
   /plugin install myelin@myelin
   ```
4. (선택) MCP: [mcp.md](mcp.md)

## 5. 첫 verified 노트
`/myelin:ingest <자료>` 또는 `/myelin:distill` → Hub **Review Gate** → 원문 확인 → **Promote** → Lime ring.
여기까지가 온보딩입니다 (목표 15분).

## 문제 해결
| 증상 | 해결 |
|---|---|
| `uv 가 필요합니다` | uv 설치 후 새 터미널 |
| Hub가 "웹 화면이 빌드되지 않았습니다" | Node 18+ 설치 후 `install.sh` 재실행 |
| Hub 화면에 "세션이 없습니다" | 터미널에 출력된 `?token=` 링크로 다시 열기 |
| 승격이 "git 저장소가 아닙니다" | Hub Settings → 로컬 git 시작 |
| `--host 0.0.0.0` 이 거부됨 | 정상 — Hub는 localhost 전용 |
