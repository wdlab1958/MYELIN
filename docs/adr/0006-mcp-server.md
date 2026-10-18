# ADR-0006: MYELIN MCP 서버 — SDK, 색인, 보안 경계

- 상태: Accepted
- 일자: 2026-10-18
- Phase: P4

## 맥락
Claude Desktop·Claude Code가 Vault를 "검색"할 수 있어야 한다 (명세 §7.3).
MCP 결과는 곧 Claude의 컨텍스트 = Anthropic으로 전송되는 데이터이므로, P3 Guard의 **읽기 정책을 MCP에도 똑같이** 적용해야 한다.

## 결정
### SDK
- **MCP Python SDK 2.x** (`mcp>=2.3`). v2에서 `FastMCP` 는 `MCPServer` (`mcp.server.mcpserver`) 로 이름이 바뀌었다 (설치 패키지 소스로 확인).
- 전송은 **stdio만** (로컬 하위 프로세스). 네트워크 포트를 열지 않는다.
- 진입점: `myelin-mcp --vault <경로>`. Vault 표식(`myelin.yaml` + lock)이 없으면 시작하지 않는다 (exit 2).

### 색인
- `<vault>/.myelin/index.db` — SQLite FTS5 **trigram** 토크나이저. 한국어는 조사가 붙어 단어 경계 검색이 안 되므로(“예산은”) 부분 문자열 검색이 맞다.
  trigram은 3글자 미만을 찾지 못하므로 2글자 이하 검색어는 `LIKE` 로 보완한다.
- 색인 범위 = doctor 스캔 범위 (ADR-0005 보정과 동일한 함수 사용).
- 증분 갱신: 파일의 `(mtime_ns, size)` 가 바뀐 것만 다시 읽는다. 매 도구 호출 전에 갱신하되 2초 이내 재호출은 생략.
- `.myelin/` 은 Vault `.gitignore` 에 이미 있다 — 색인은 공유되지 않는다.

### 보안 경계 (P3 Guard와 동일한 정책)
1. **보호 노트는 색인하지 않는다**: `40_IP/`(candidates 제외), `classification: confidential` — `llm.route` 가 local일 때(기본).
   결과에서 거르는 것이 아니라 아예 넣지 않는다 (fail-closed — 필터 버그가 있어도 나갈 내용이 없다).
2. `get_note` 는 색인에 있는 노트만 돌려준다. 경로 인자는 정규화·realpath 후 Vault 안·내용 폴더 안이어야 한다. 심볼릭 링크 탈출 차단.
3. **기본 읽기 전용.** `write_draft` 도구는 `myelin.yaml` 의 `mcp.write_drafts: true` 일 때만 **등록**된다 (목록에도 없음).
   등록되어도 경로·Level 판정은 Guard 모듈의 `check()` 를 그대로 호출한다 — 규칙을 두 곳에 구현하지 않는다.
   쓰는 노트는 항상 `origin: claude`, `status: draft`, `00_Inbox/ai-drafts/`, 덮어쓰기 금지.
4. 모든 도구에 MCP `readOnlyHint` 등 annotation을 단다.

### 스키마 변경
- `myelin.yaml` 에 `mcp: {write_drafts: false}` 추가 (기본 false). `render_config` 가 이 블록을 쓴다.

## 결과
- Claude Desktop 설정과 `claude mcp add` 방법은 `docs/guides/mcp.md`.
- 성능 기준: 5,000 노트에서 `search_notes` p95 < 300ms (Gate가 생성 fixture로 측정).
