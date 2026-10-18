# ADR-0007: MYELIN MCP 정책 — 읽기 전용 기본, 기밀 노출, write_draft, 색인

- 상태: Accepted · 일자: 2026-10-18 · Phase: P4
- 근거: 정본 §4.4 색인(SQLite FTS5, `.myelin/index.db`), §7.3 MCP tools 표, ADR-0002 D7, P4 착수 프롬프트("write_draft는 myelin.yaml에서 명시 허용된 경우에만 등록")

## 결정

1. **전송은 stdio, 서버는 Vault 1개.** `myelin-mcp --vault <path>`(또는 `$MYELIN_VAULT`). Vault 밖 접근은 경로 해석 단계에서 차단(`..`·절대경로·`~`·symlink 이탈 → 오류). 존재 여부도 노출하지 않는다.
2. **기본 읽기 전용.** 등록 도구 = `search_notes · get_note · query_frontmatter · list_domains · vault_stats`. `write_draft` 는 `myelin.yaml` 에 `mcp.write_draft: true` **그리고** `level >= 1` 일 때만 **등록**된다(호출 시 거부가 아니라 도구 자체가 없다). write_draft 는 `00_Inbox/ai-drafts/` 에 새 파일만 만들고(`x` 모드), `origin: claude`·`status: draft`, 템플릿은 Vault 의 `90_System/templates/<type>.md`. 생성 후 색인 갱신 → frontmatter 오류면 파일을 지우고 오류 반환.
3. **기밀 정책 — "local 클라이언트만"의 해석.** stdio 서버는 항상 로컬 프로세스지만, 그 클라이언트(Claude Desktop/Code)가 내용을 외부 모델로 보낸다. 따라서 "local" 은 전송이 아니라 **Vault 소유자의 명시 opt-in** 으로 해석한다: `mcp.expose_confidential: false`(기본) 이면 `classification: confidential` 노트와 `40_IP/**` 는 검색 결과에서 제외되고 `get_note` 는 frontmatter 만 돌려주며 본문은 `[confidential — body withheld …]`. `true` 는 로컬 LLM 세션(정본 §4.3 Offline, `llm.route`)에서만 켜도록 가이드에 명시.
4. **색인**: `<Vault>/.myelin/index.db`(git ignore). 테이블 `notes`(frontmatter 컬럼 + body + mtime/size/sha256), `note_domains`, `note_tags`, `links`, `parse_errors`, FTS5 `notes_fts`(**trigram** 토크나이저). 증분 갱신은 (mtime_ns, size) 서명 비교. 스키마 버전 불일치 시 재구축. 색인은 캐시이며 언제든 삭제·재생성 가능.
5. **검색 = 하이브리드.** 3자 이상 토큰은 FTS5 MATCH(모두 인용 → 구문 주입 불가, AND 결합), 2자 이하 토큰(한국어 2음절 어휘: 예산·실험)은 `LIKE %t%` 로 AND 결합. 토큰이 없으면 오류(fail-closed, "전체 매치" 금지). 순위는 bm25(title 4 · body 1 · tags 2).
6. **myelin.yaml 필드 추가** (ADR-0004 보강): `mcp: {write_draft: bool=false, expose_confidential: bool=false}`.
7. **플러그인 번들 아님**(ADR-0002 D7): 사용자가 Claude Desktop/Code 설정에 직접 등록. 가이드 `docs/guides/mcp-setup.md`.

## 대안과 기각
- 임베딩 검색: P4 범위 밖(정본 "선택: 로컬 임베딩"). 색인 스키마에 열을 예약하지 않고 별도 테이블로 추가 가능.
- unicode61 토크나이저: 한국어 조사 결합("미엘린을")에 약함. trigram + LIKE 보완이 5,000 노트에서 p95 < 300ms 를 만족.

## 결과
- MCP 가 Vault 를 바꾸는 경로는 write_draft 하나이며 Guard 와 같은 디렉터리 정책을 따른다. Hub(P6)·CLI 는 같은 `VaultIndex` 를 재사용해 전체 스캔을 대체할 수 있다(Backlog).
