# MYELIN MCP — Claude Desktop / Claude Code 설정 가이드

MYELIN MCP 는 **당신의 Vault 하나**를 읽기 전용으로 Claude 에 연결한다(정본 §7.3, ADR-0007). 서버는 로컬 stdio 프로세스이며, 기밀 노트는 기본적으로 본문을 돌려주지 않는다.

## 1. 설치 확인
```bash
cd <myelin repo>
uv sync --all-packages
uv run myelin-mcp --version          # myelin-mcp 0.1.0a0
uv run myelin-mcp --vault ~/Vaults/brian   # 대기 상태로 뜨면 Ctrl-C (stdio 서버 정상)
```
Vault 에 `myelin.yaml` 이 없으면 종료 코드 2 로 거부한다.

## 2. Claude Code
```bash
claude mcp add myelin --scope user -- uv --directory /path/to/myelin run myelin-mcp --vault /path/to/Vault
claude mcp list        # myelin: connected
```
Vault 폴더 안에서 Claude Code 를 쓰면 `--vault` 대신 환경변수 `MYELIN_VAULT` 를 써도 된다.

## 3. Claude Desktop
`claude_desktop_config.json` (macOS `~/Library/Application Support/Claude/`, Windows `%APPDATA%\Claude\`):
```json
{
  "mcpServers": {
    "myelin": {
      "command": "uv",
      "args": ["--directory", "/path/to/myelin", "run", "myelin-mcp", "--vault", "/path/to/Vault"]
    }
  }
}
```
재시작 후 도구 목록에 `search_notes · get_note · query_frontmatter · list_domains · vault_stats` 가 보이면 된다.

## 4. 도구
| 도구 | 설명 | 권한 |
|---|---|---|
| `search_notes(query, domain?, status?, type?, limit=20)` | FTS5(+LIKE) 검색, 스니펫·순위 | read |
| `get_note(ref)` | 경로 또는 id → frontmatter + 본문 + backlinks | read (confidential 은 본문 비공개) |
| `query_frontmatter(type?, status?, origin?, classification?, domain?, tag?, share?, created_from/to?, reviewed_from/to?, order, limit)` | Dataview 류 질의 | read |
| `list_domains()` | 3+1 Domain·역할·노트 수·Pack 메타 | read |
| `vault_stats(today?)` | 정본 §11.1 지표 | read |
| `write_draft(title, body, type, domain, tags, source)` | `00_Inbox/ai-drafts/` 에 새 초안 | **opt-in**: `mcp.write_draft: true` + `level ≥ 1` |

## 5. 정책 스위치 (`<Vault>/myelin.yaml`)
```yaml
mcp:
  write_draft: false          # true 이면 write_draft 도구가 등록된다 (level ≥ 1 필요)
  expose_confidential: false  # true 는 로컬 LLM 세션에서만. 외부 Claude 에 기밀을 보내지 않는다.
```
- `expose_confidential: false` 일 때 `classification: confidential` 노트와 `40_IP/**` 는 검색에서 제외되고 `get_note` 본문은 `[confidential — body withheld …]` 로 대체된다.
- 색인은 `<Vault>/.myelin/index.db` 에 있고 자동으로 증분 갱신된다. 이상하면 지우면 된다(다음 호출에서 재구축).

## 6. 문제 해결
- 도구가 안 보임 → `claude mcp list` 로 연결 확인, `uv run myelin-mcp --vault …` 를 터미널에서 직접 실행해 오류 메시지 확인.
- `write_draft` 가 없음 → 설계상 기본값. 위 스위치와 Level 을 확인.
- 검색이 비어 있음 → 2자 이하 토큰은 부분 일치, 3자 이상은 FTS. 공백으로 단어를 나누면 AND 로 묶인다.
