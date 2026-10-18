# MYELIN MCP 서버 연결 가이드

Claude Desktop이나 Claude Code가 **내 Vault를 검색**할 수 있게 해 줍니다. 기본은 **읽기 전용**입니다.

## 무엇을 할 수 있나
| 도구 | 하는 일 |
|---|---|
| `search_notes` | 전문 검색 (한국어 부분 문자열 가능), domain·type·status로 거르기 |
| `get_note` | 노트 하나 (frontmatter + 본문) — 경로 또는 id |
| `query_frontmatter` | 조건으로 목록 (예: 이번 달 verified, 검토 대기 AI 초안) |
| `list_domains` | 내 Domain과 노트 수 |
| `vault_stats` | 지표·doctor 요약 (숫자만) |
| `write_draft` | **opt-in**: `myelin.yaml` 에 `mcp.write_drafts: true` 일 때만 나타남. `00_Inbox/ai-drafts/` 에 초안만 |

## 개인정보
- 이 서버가 돌려준 내용은 Claude의 대화에 들어가고, **Anthropic으로 전송됩니다.**
- 그래서 `40_IP/`(candidates 제외)와 `classification: confidential` 노트는 **색인 자체에 넣지 않습니다** — 검색·조회 어디로도 나가지 않습니다.
  (`myelin.yaml` 의 `llm.route` 를 `claude` 로 바꾸면 열립니다. 바꾸면 색인이 자동으로 다시 만들어집니다.)
- 색인 파일은 Vault의 `.myelin/index.db` — `.gitignore` 대상이며 내 PC에만 있습니다.
- 네트워크 포트를 열지 않습니다 (stdio 전용).

## 설치
```bash
git clone https://github.com/wdlab1958/MYELIN.git ~/src/MYELIN
cd ~/src/MYELIN && uv sync
```

## Claude Code
```bash
claude mcp add myelin -- uv run --directory ~/src/MYELIN myelin-mcp --vault ~/MyVault
```
확인: Claude Code에서 `/mcp`.

## Claude Desktop
`claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`):
```json
{
  "mcpServers": {
    "myelin": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/me/src/MYELIN", "myelin-mcp", "--vault", "/Users/me/MyVault"]
    }
  }
}
```
Claude Desktop을 다시 시작하면 도구 목록에 `myelin` 이 보입니다.

## 써 보기
- "내 Vault에서 WCET 관련 verified 노트를 찾아서 요약해 줘"
- "검토 대기 중인 AI 초안 목록 보여 줘" → `query_frontmatter(origin=claude, status=draft)`
- "이번 주 지표는?" → `vault_stats`

## 성능
5,000 노트 기준 검색 p95 약 20ms (Gate 측정 기준 300ms). 첫 실행 때 색인을 만드는 데 몇 초 걸립니다.
