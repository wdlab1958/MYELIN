# MYELIN — 형식 검증 보고서

- 프로젝트: **MYELIN** (`/home/ubuntu-02/ai_project/MYELIN`, branch `main`, remote `git@github.com:wdlab1958/MYELIN.git`)
- 검사한 commit: `3690adae5a5f2a093d33e225cd2cd7c752ccd85c`
- 날짜: 2026-11-21 · Run `20261121-115639-myelin`
- 도구: wdproof 0.1.0 · TLC 2026.10.28.014557 (rev: 56d37a9) · openjdk version "21.0.13.1" 2026-11-17 · Lean 4.34.0 · python (3.12.3 9.1.1)
- 에이전트: claude · claude-opus-5-5 · 에이전트 비용(USD) 5.25
- 작성: WDLAB-Proof-Skills 자동 파이프라인 (판정은 결정적 검증기, 서술은 에이전트)

## 1. 판정 요약

| 항목 | 값 |
|---|---|
| 관심사(Concern) | `mcp-config-revocation-stale` (derived from `consent-revocation`) |
| Finding F1 | **FIXED** (severity high) — MCP 서버가 기동 시 캐시한 myelin.yaml 로 write_draft·expose_confidential 을 판정해, 디스크에 기록된 동의 철회 뒤에도 초안 생성과 confidential 본문 반출을 계속한다 |
| 달성 레벨 | **L3** |
| 경계 | `Calls=2, Caps=2` — 1,555 states generated / 919 distinct / depth 15 |
| 3-config | `MC.cfg` PASS · `MC_3.cfg` PASS · `MC_bug.cfg` FAIL (Inv_NoDraftAfterRevoke) · `MC_bug_p2.cfg` FAIL (Inv_NoConfidentialAfterRevoke) · `MC_sanity.cfg` FAIL (Sanity_ReleaseThenRevoke) |
| 신뢰 기반 | TLC 2026.10.28.014557 (rev: 56d37a9); Lean 4.34.0 kernel; the frozen property statements (PROPERTIES.md); model↔code correspondence (CORRESPONDENCE.md + reproduction test) |
| 정책 / 내보내기 | `fix-on-branch` — branch wdproof/20261121-115639-myelin created in target repository; working tree untouched |
| 수정 파일 | `packages/myelin-mcp/src/myelin_mcp/service.py` (적용됨) |

> "검증됨"은 위 경계와 추상화 안에서 반례가 없다는 뜻이며, 코드가 모든 입력에 대해 정확하다는 뜻이 아니다. 판정은 관심사 1개에 대한 것이고 프로젝트 전체에 대한 것이 아니다.

| 단계 | 상태 | 비고 |
|---|---|---|
| S0 Intake | ok | 2 uncommitted change(s) in the target are NOT part of this run (HEAD is analysed) |
| S1 Baseline | ok |  |
| S2 Candidates | ok |  |
| S3 Scope & Properties | ok |  |
| S4 Model & Check | ok | code matches: bug · 919 states · depth 15 |
| S5 Reproduce | ok |  |
| S6 Root Cause | ok |  |
| S7 Fix & Re-verify | ok | applied |
| S8 Promote | ok |  |
| S9 Report | ok |  |

## 2. 프로젝트 개요와 후보표

| 순위 | 후보 | 위치 | 버그 클래스 | blast × conc. | 패턴 | 선택 |
|---|---|---|---|---|---|---|
| 1 | mcp-config-revocation-stale — MCP 서버가 기동 시 읽은 myelin.yaml 로 write_draft 허용·confidential 노출을 판정해, Hub Settings 에서 철회한 동의가 반영되지 않는다 | `packages/myelin-mcp/src/myelin_mcp/service.py:59-84` | check-then-act | H × H | consent-revocation | **✓** |
| 2 | hub-add-domain-stale-vault — Hub add_domain 이 _mutation 진입 전에 잡은 Vault 를 core add_domain 에 넘겨, 그 사이 CLI 가 추가한 Domain 을 myelin.yaml 에서 지운다 | `packages/myelin-hub/api/src/myelin_hub_api/service.py:926-1014` | lost-update | H × M | lease-fencing | — |
| 3 | commons-publish-base-branch — 직렬화되지 않은 Commons 게시가 다른 게시의 publish/<id> 브랜치를 base 로 읽어 PR 에 남의 노트를 섞고 clone 을 엉뚱한 브랜치에 남긴다 | `packages/myelin-core/src/myelin_core/commons.py:319-404` | race | M × M | — | — |
| 4 | hub-mutation-rollback-clobber — _mutation 실패 복원이 본문 실행 중 다른 프로세스가 쓴 내용을 스냅샷으로 덮는다 | `packages/myelin-hub/api/src/myelin_hub_api/service.py:305-339` | lost-update | M × L | — | — |
| 5 | promote-dest-check-then-write — promote 가 dest.exists() 검사 뒤 write_text 로 써서, 그 사이 생긴 같은 이름의 사람 노트를 덮는다 | `packages/myelin-hub/api/src/myelin_hub_api/service.py:699-713` | check-then-act | M × L | hitl-approval-gate | — |
| 6 | index-refresh-signature — 색인 갱신이 (mtime_ns, size) 서명만 비교해 같은 tick·같은 크기 재작성을 놓친다 | `packages/myelin-core/src/myelin_core/index.py:303-349` | dataflow-loss | M × L | — | — |
| 7 | reload-drops-index-under-readers — myelin.yaml 이 순간적으로 파싱 불가일 때 reload 가 공유 SQLite 연결을 닫아 동시 질의가 500 으로 끝난다 | `packages/myelin-hub/api/src/myelin_hub_api/service.py:235-261` | race | L × L | — | — |
| 8 | add-domain-rollback-residue — Hub add_domain 실패 롤백이 .obsidian/ 디렉터리 생성을 되돌리지 않는다 | `packages/myelin-hub/api/src/myelin_hub_api/service.py:994-1011` | other | L × L | — | — |

선택 근거: C1 은 1순위(blast H × concurrency H)이며 모델링 가능하다. MCP 서버(VaultService)는 기동 시 Vault.open 으로 myelin.yaml 을 한 번 읽어 vault.config 에 캐시하고(packages/myelin-mcp/src/myelin_mcp/service.py:59-62), write_enabled(packages/myelin-mcp/src/myelin_mcp/service.py:83-84)·expose_confidential(packages/myelin-mcp/src/myelin_mcp/service.py:66-68)은 이 캐시만 본다. 도구 호출마다 색인은 refresh 하지만 설정은 다시 읽지 않으므로, 사용자가 Hub Settings(PUT /api/settings → packages/myelin-hub/api/src/myelin_hub_api/service.py:813-848)에서 mcp.write_draft=false·level=0·expose_confidential=false 로 저장해 철회를 커밋해도 장수명 MCP 프로세스는 초안 쓰기와 confidential 본문 반출을 계속한다. 이는 consent-revocation 패턴의 Check→Revoke→Fetch TOCTOU 와 같은 구조이며, 여기서 'Check' 는 기동 시 캐시 적재로 늘어나 창이 몇 시간 단위가 된다. 패턴의 Inv_NoReleaseAfterRevoke 를 write_draft·expose_confidential 두 권한으로 나누어 동결하고, 반출 시점을 파일 생성(open('x'))과 색인 본문 읽기로 정의한다. 다른 프로세스 간 단일 사실(설정 파일 상태)과 프로세스 캐시 사이의 인터리빙 전수 탐색이 목적이므로 TLA+/TLC 가 적합하다.

## 3. Finding 상세

### F1 — FIXED: MCP 서버가 기동 시 캐시한 myelin.yaml 로 write_draft·expose_confidential 을 판정해, 디스크에 기록된 동의 철회 뒤에도 초안 생성과 confidential 본문 반출을 계속한다

MYELIN 의 MCP 서버는 Claude Code 세션이 시작될 때 한 번 떠서 세션이 끝날 때까지 살아 있는 별도 프로세스다. 이 서버는 시작할 때 myelin.yaml 을 읽어 'AI 초안 쓰기 허용(mcp.write_draft·level)'과 'confidential 노출 허용(mcp.expose_confidential)'을 메모리에 저장해 두고, 이후 모든 도구 호출에서 그 메모리 값만 확인한다. 노트 색인은 호출마다 새로 고치지만 설정 파일은 다시 읽지 않는다. 그래서 사용자가 Hub Settings 화면에서 초안 쓰기나 confidential 노출을 끄고 저장(커밋까지 성공)해도, 이미 떠 있는 MCP 서버는 그 사실을 모른 채 00_Inbox/ai-drafts 에 계속 초안을 만들고 confidential·40_IP 노트 본문을 LLM 컨텍스트로 계속 내보낸다. 이 상태는 세션을 재시작할 때까지 이어지며, 한 번 내보낸 본문은 되돌릴 수 없다. 재현 테스트(packages/myelin-mcp/tests/test_formal_mcp_config_revocation.py)는 서비스를 연 뒤 myelin.yaml 에 철회를 기록하고 도구를 호출하는 순서만으로 두 위반을 결정적으로 보여 준다. Hub 는 같은 문제를 '결정 전에 myelin.yaml 바이트를 비교해 바뀌었으면 다시 읽기'로 이미 고쳤고, MCP 서비스에도 같은 재적재(실패 시 권한 거부)를 락 안에서 수행해야 한다.

- 위반 속성: `Inv_NoDraftAfterRevoke` · 심각도: high
- 최소 트레이스: Open (cache=file={write:TRUE, expose:TRUE}, registered=TRUE) → Revoke("write") (file.write=FALSE, cache.write=TRUE 유지) → Begin(c1, kind=write, revokedAtBegin=TRUE) → Check(c1) [cache.write=TRUE 로 허용] → Prepare(c1) → Release(c1) ⇒ leakedW=1 (Inv_NoDraftAfterRevoke 위반). 같은 모양으로 Revoke("expose") → get_note/search_notes 가 Inv_NoConfidentialAfterRevoke 도 위반(MC_bug_p2.cfg).

| # | 액션 | 코드 | 상태 변화 |
|---|---|---|---|
| 1 | `Open` | `packages/myelin-mcp/src/myelin_mcp/service.py:59-62` | serve()(server.py:162) → VaultService.open → Vault.open 이 myelin.yaml 을 한 번 읽어 self.vault.config 에 캐시: cache = file = {write:TRUE, expose:TRUE}; build_server 가 write_enabled 를 보고 write_draft 도구를 등록(server.py:127), registered=TRUE |
| 2 | `Revoke("write")` | `packages/myelin-hub/api/src/myelin_hub_api/service.py:834` | 다른 프로세스(Hub PUT /api/settings save_settings, CLI 또는 편집기)가 myelin.yaml 에 mcp.write_draft: false (또는 level: 0) 를 기록: file.write=FALSE. MCP 프로세스의 cache.write 는 TRUE 그대로 |
| 3 | `Begin(c1)` | `packages/myelin-mcp/src/myelin_mcp/service.py:47` | write_draft 도구 호출이 _serialized 의 self._lock 획득: lock=c1, kind=write, revokedAtBegin[c1]=TRUE (철회가 이미 디스크에 있음) |
| 4 | `Check(c1)` | `packages/myelin-mcp/src/myelin_mcp/service.py:232-235` | if not self.write_enabled 가 캐시(service.py:83-84 self.vault.config.mcp.write_draft and level>=1)만 읽어 TRUE → 거부하지 않음, pc=prepare. 설정 재적재 경로가 없다 |
| 5 | `Prepare(c1)` | `packages/myelin-mcp/src/myelin_mcp/service.py:236-281` | 제목·타입 검증, 템플릿 읽기, 00_Inbox/ai-drafts mkdir — 정책과 무관한 I/O, pc=release |
| 6 | `Release(c1)` | `packages/myelin-mcp/src/myelin_mcp/service.py:283-284` | target.open("x") 로 00_Inbox/ai-drafts/<title>.md 생성: released=1, leakedW=1 → Inv_NoDraftAfterRevoke 위반 |
| 7 | `End(c1)` | `packages/myelin-mcp/src/myelin_mcp/service.py:47-48` | 락 해제 후 stdio 로 성공 응답: lock=NoCall, pc=done |

**원인 분석**

| 항목 | 값 |
|---|---|
| 계층 | system |
| 버그 클래스 | check-then-act (consent-revocation (stale authorization cache / TOCTOU)) |
| 위치 | `packages/myelin-mcp/src/myelin_mcp/service.py:59-89` |
| 메커니즘 | VaultService 는 기동 시 Vault.open 으로 myelin.yaml 을 한 번만 읽어 self.vault.config 에 보관하고(service.py:59-62), 권한 판정 프로퍼티 write_enabled(service.py:83-84)와 expose_confidential(service.py:66-68)·_hidden(service.py:86-89)은 이 프로세스 메모리 사본만 본다. 도구 호출(search_notes·get_note·write_draft 등)은 매번 index.refresh() 로 노트 색인은 갱신하지만 설정 파일은 다시 읽지 않는다. myelin.yaml 은 Hub·CLI·편집기가 함께 쓰는 공유 파일인데, '권한 확인(Check)'이 기동 시점으로 고정되어 있어 그 뒤의 철회와 실제 쓰기/반출(Act) 사이에 프로세스 수명 전체만큼의 TOCTOU 창이 생긴다. Hub 는 같은 문제를 _reload_if_changed(바이트 비교 재적재, myelin_hub_api/service.py:269-282)로 고쳤지만 MCP 쪽에는 대응 경로가 없다. |
| 발생 조건 | 사용자가 Claude Code 세션(MCP 서버 장수명 stdio 프로세스)을 열어 둔 채 Hub Settings 에서 mcp.write_draft 를 끄거나 level 을 0 으로 내리거나 mcp.expose_confidential 을 끄고 저장한다(또는 CLI/편집기로 myelin.yaml 을 수정한다). 특별한 타이밍이 필요 없고, 이후 세션이 재기동될 때까지(수 시간~수 일) 모든 write_draft 호출이 초안을 만들고, 로컬 세션의 get_note/search_notes/query_frontmatter 가 confidential·40_IP 본문과 경로를 계속 응답에 담는다. 철회 저장 성공 메시지와 git 커밋이 남아 사용자는 철회가 적용됐다고 믿는다. |
| 기존 테스트가 놓친 이유 | 기존 테스트(test_mcp_adversarial.py:235-251, test_service.py:16-48, 108-123)는 모두 정책을 myelin.yaml 에 먼저 써 둔 뒤 VaultService.open 을 호출해, '기동 시점 설정이 올바르게 적용되는가'만 검사한다. 서비스가 열린 뒤 다른 프로세스가 설정을 바꾸는 순서(Open → Revoke → 호출)를 만드는 테스트가 없어서, 캐시가 갱신되지 않는다는 사실이 드러나지 않았다. Hub 쪽 같은 결함(hub-config-stale-cache F1)을 고칠 때도 범위가 HubService 로 한정되었다. |

코드 매핑: `packages/myelin-mcp/src/myelin_mcp/service.py:59-62`, `packages/myelin-mcp/src/myelin_mcp/service.py:65-68`, `packages/myelin-mcp/src/myelin_mcp/service.py:82-89`, `packages/myelin-mcp/src/myelin_mcp/service.py:126-138`, `packages/myelin-mcp/src/myelin_mcp/service.py:142-156`, `packages/myelin-mcp/src/myelin_mcp/service.py:232-235`, `packages/myelin-mcp/src/myelin_mcp/service.py:283-284`, `packages/myelin-mcp/src/myelin_mcp/server.py:127-148`, `packages/myelin-mcp/src/myelin_mcp/server.py:160-167`, `packages/myelin-hub/api/src/myelin_hub_api/service.py:813-848`

**재현 테스트와 수정 전 결과**

`packages/myelin-mcp/tests/test_formal_mcp_config_revocation.py` — 수정 전 코드(base commit)에서 속성 단언으로 실패해야 한다. → **OK** (`evidence/test_before.log`)

```
E       AssertionError: P1 Inv_NoDraftAfterRevoke violated: a write_draft call that started after `mcp.write_draft: false` was on disk created 00_Inbox/ai-drafts/철회 후 초안.md
E       assert not True
E        +  where True = exists()
E        +    where exists = PosixPath('/tmp/pytest-of-ubuntu-02/pytest-102/test_p1_no_draft_after_write_d0/basic/00_Inbox/ai-drafts/철회 후 초안.md').exists
E       AssertionError: P2 Inv_NoConfidentialAfterRevoke violated: get_note started after `mcp.expose_confidential: false` was on disk returned the body of 40_IP/candidates/Agentic CAD 검증 루프.md
E       assert (False is True)
FAILED packages/myelin-mcp/tests/test_formal_mcp_config_revocation.py::test_p1_no_draft_after_write_draft_revoked
FAILED packages/myelin-mcp/tests/test_formal_mcp_config_revocation.py::test_p2_no_confidential_after_expose_revoked
2 failed in 0.15s
```

**수정** — 적용됨 (`evidence/patches/F1-mcp-config-revocation-stale.diff`)

packages/myelin-mcp/src/myelin_mcp/service.py: VaultService 가 기동 시 적재한 myelin.yaml 바이트(_config_bytes)를 기억하고, _serialized 래퍼가 서비스 락을 잡은 직후(도구 본문 실행 전) _reload_if_changed() 를 호출한다. 디스크 바이트가 마지막 적재본과 다르면 Vault.open 으로 설정을 다시 읽어 self.vault 와 self.index.vault 를 교체한다(Hub F1 _reload_if_changed 와 같은 방식, mtime 이 아닌 바이트 비교). 재적재가 ConfigError(파일 없음·부분 쓰기·잘못된 YAML/스키마)면 이전 권한을 유지하지 않고 MCPError 로 그 호출을 거부하며 _config_bytes 를 None 으로 지워 다음 호출에서도 다시 검사한다(fail-closed, SCOPE A3). 모델의 FIX=TRUE 분기(Check 시 cache' = file 후 디스크 값으로 판정)와 일치하므로 Spec.tla 는 바꾸지 않았다.

- 동작이 바뀌는 범위: MCP 서버 기동 후 다른 프로세스(Hub PUT /api/settings, CLI, 편집기)가 myelin.yaml 을 바꾼 경우에만 동작이 달라진다: (1) mcp.write_draft:false 또는 level:0 이 기록된 뒤 시작된 write_draft 호출은 MCPError 로 거부되고 초안 파일을 만들지 않는다; (2) mcp.expose_confidential:false 가 기록된 뒤 시작된 search_notes/get_note/query_frontmatter/역링크는 confidential·40_IP 를 숨기고 본문을 REDACTED 로 돌려준다; (3) 반대로 기동 후 허용/도메인/레벨 변경도 다음 호출부터 반영된다(list_domains·write_draft 도메인 검증 포함, 단 write_draft 도구 등록 목록은 여전히 기동 시 기준); (4) 기동 후 myelin.yaml 이 삭제되거나 무효가 되면 모든 도구 호출이 MCPError 로 거부된다(이전에는 기동 시 사본으로 계속 동작). 파일이 바뀌지 않은 경우의 동작과 공개 함수 시그니처는 그대로이며, 호출마다 myelin.yaml 을 한 번 read_bytes 하는 비용이 추가된다.
- 검토한 대안: mtime/size 비교로 재적재 — 같은 tick 안의 편집을 놓칠 수 있어 바이트 비교를 택함(Hub F1 과 동일 근거) / 재적재 실패 시 이전 캐시 유지 — A3 가 금지하는 fail-open, 부분 쓰기 창에서 철회를 무시하게 됨 / 재적재 실패 시 권한만 FALSE 로 강등하고 다른 도구는 계속 허용 — 더 가용성이 높지만 config 없는 상태의 의미를 따로 정의해야 해서 전체 거부(fail-closed)를 택함 / inotify/watchdog 파일 감시 — 의존성 추가와 이벤트 지연 창이 남아 호출 진입 시 동기 검사보다 약함 / write_draft 도구 등록 목록도 갱신(tools/list_changed 알림) — ADR-0007 '도구 자체가 없다' 문구와 맞지만 범위 밖(side finding) / 판정 지점(write_enabled/expose_confidential 프로퍼티)에서만 매번 디스크를 읽기 — 한 호출 안에서 판정마다 다른 설정을 볼 수 있어 호출 단위 일관성이 깨짐

```diff
diff --git a/packages/myelin-mcp/src/myelin_mcp/service.py b/packages/myelin-mcp/src/myelin_mcp/service.py
index 706b2c7..98fd126 100644
--- a/packages/myelin-mcp/src/myelin_mcp/service.py
+++ b/packages/myelin-mcp/src/myelin_mcp/service.py
@@ -21,6 +21,7 @@ from functools import wraps
 from pathlib import Path
 from typing import Any
 
+from myelin_core.config import CONFIG_FILE, ConfigError
 from myelin_core.index import VaultIndex, open_index
 from myelin_core.levels import LLM_ENV, LLM_LOCAL, is_local_session
 from myelin_core.render import make_note_id, render_template
@@ -45,6 +46,7 @@ def _serialized[**P, T](fn: Callable[P, T]) -> Callable[P, T]:
         self = args[0]
         assert isinstance(self, VaultService)
         with self._lock:
+            self._reload_if_changed()
             return fn(*args, **kwargs)
 
     return inner
@@ -55,11 +57,46 @@ class VaultService:
     vault: Vault
     index: VaultIndex
     _lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)
+    # Bytes of myelin.yaml the current `vault.config` was loaded from (None = unknown).
+    _config_bytes: bytes | None = field(default=None, repr=False, compare=False)
 
     @classmethod
     def open(cls, root: Path, *, refresh: bool = True) -> VaultService:
+        # Read the bytes first: if the file changes before load_config, the next call reloads.
+        raw = cls._read_config_bytes_at(Path(root).resolve())
         vault = Vault.open(root)
-        return cls(vault=vault, index=open_index(vault, refresh=refresh))
+        svc = cls(vault=vault, index=open_index(vault, refresh=refresh))
+        svc._config_bytes = raw
+        return svc
+
+    @staticmethod
+    def _read_config_bytes_at(root: Path) -> bytes | None:
+        try:
+            return (root / CONFIG_FILE).read_bytes()
+        except OSError:
+            return None
+
+    def _reload_if_changed(self) -> None:
+        """Re-read myelin.yaml (under the service lock) when it changed on disk since the last load.
+
+        The policy (`mcp.write_draft`, `level`, `mcp.expose_confidential`) is owned by the file,
+        which other processes (Hub Settings, CLI, an editor) rewrite while this server runs. A tool
+        call that starts after a revocation is on disk must see it — formal/mcp-config-revocation-
+        stale (F1); same approach as the Hub's `_reload_if_changed`. Fail-closed: an unreadable or
+        invalid file refuses the call (and is re-checked on every call) instead of keeping the old
+        permissions.
+        """
+        raw = self._read_config_bytes_at(self.vault.root)
+        if raw is not None and raw == self._config_bytes:
+            return
+        try:
+            vault = Vault.open(self.vault.root)
+        except ConfigError as exc:
+            self._config_bytes = None
+            raise MCPError(f"myelin.yaml is invalid — refusing until fixed: {exc}") from None
+        self.vault = vault
+        self.index.vault = vault
+        self._config_bytes = raw
 
     # ------------------------------------------------------------------ policy helpers
     @property
```

수정 후 증거:

| 검사 | 결과 | 메시지 |
|---|---|---|
| schema:fix | PASS | valid |
| patch_audit | PASS | minimal patch: 1 file(s), +38/-1, public API unchanged |
| frozen_properties | PASS | 3 frozen file(s) unchanged |
| repro_after_fix | PASS | 2 reproduction test(s) pass after the fix |
| regression | PASS | no regression: 1297 passed (baseline 1295) |
| three_config | PASS | 5 configs match expectations; MC: 919 distinct states, depth 15 |
| mutation | PASS | fix reverted -> reproduction fails again by assertion; fix re-applied |

## 4. 검증된 것과 경계

| 시점 | 설정 | 기대 | 결과 | 위반 속성 | 상태 수 (distinct) | 깊이 |
|---|---|---|---|---|---|---|
| 수정 전 | `MC.cfg` | PASS | **PASS** | — | 919 | 15 |
| 수정 전 | `MC_3.cfg` | PASS | **PASS** | — | 5531 | 20 |
| 수정 전 | `MC_bug.cfg` | FAIL | **FAIL** | Inv_NoDraftAfterRevoke | 129 | 7 |
| 수정 전 | `MC_bug_p2.cfg` | FAIL | **FAIL** | Inv_NoConfidentialAfterRevoke | 141 | 7 |
| 수정 전 | `MC_sanity.cfg` | FAIL | **FAIL** | Sanity_ReleaseThenRevoke | 161 | 7 |
| 수정 후 | `MC.cfg` | PASS | **PASS** | — | 919 | 15 |
| 수정 후 | `MC_3.cfg` | PASS | **PASS** | — | 5531 | 20 |
| 수정 후 | `MC_bug.cfg` | FAIL | **FAIL** | Inv_NoDraftAfterRevoke | 130 | 7 |
| 수정 후 | `MC_bug_p2.cfg` | FAIL | **FAIL** | Inv_NoConfidentialAfterRevoke | 140 | 7 |
| 수정 후 | `MC_sanity.cfg` | FAIL | **FAIL** | Sanity_ReleaseThenRevoke | 158 | 7 |

**동결 속성** (`formal/mcp-config-revocation-stale/PROPERTIES.md`)

| ID | Property | Kind | Source | Frozen |
|---|---|---|---|---|
| P1 | `Inv_NoDraftAfterRevoke` — `mcp.write_draft: false` 또는 `level: 0` 이 디스크에 기록된 뒤 시작된 도구 호출은 `00_Inbox/ai-drafts/` 에 파일을 만들지 않는다. TLA+: `leakedW = 0` (ghost: 호출 시작 시 `file["write"] = FALSE` 였던 호출의 `Release` 횟수) | safety (invariant) | `docs/adr/0007-mcp-policy.md:9` ("`write_draft` 는 `mcp.write_draft: true` **그리고** `level >= 1` 일 때만"); `docs/spec/MYELIN_Rev2.0.md:604` ("Level ≥ 1 + 설정에서 명시 허용 시"); `docs/spec/MYELIN_Rev2.0.md:1020`; `packages/myelin-mcp/src/myelin_mcp/service.py:9-10` (모듈 docstring); `packages/myelin-mcp/src/myelin_mcp/service.py:232-235` (거부 메시지 "disabled (myelin.yaml mcp.write_draft: false or level 0)"); `docs/guides/mcp-setup.md:43,48`; `packages/myelin-hub/web/src/pages/Settings.tsx:53` (Hub 의 철회 UI); `PHASE_STATE.md:64`; 테스트 `packages/myelin-mcp/tests/test_mcp_adversarial.py:235-251`, `packages/myelin-mcp/tests/test_service.py:108-123` | ✅ |
| P2 | `Inv_NoConfidentialAfterRevoke` — `mcp.expose_confidential: false` 가 디스크에 기록된 뒤 시작된 도구 호출은 confidential/`40_IP/**` 노트의 본문을 응답에 넣지 않는다(검색 결과 포함). TLA+: `leakedX = 0` (ghost: 호출 시작 시 `file["expose"] = FALSE` 였던 호출의 `Release` 횟수) | safety (invariant) | `docs/adr/0007-mcp-policy.md:10` ("`false`(기본) 이면 … 검색 결과에서 제외 … 본문은 `[confidential — body withheld …]`"); `docs/adr/0011-confidential-routing-devices.md:41`; `docs/spec/MYELIN_Rev2.0.md:601` ("confidential은 local 클라이언트만"); `packages/myelin-mcp/src/myelin_mcp/service.py:5-8` (모듈 docstring); `packages/myelin-mcp/src/myelin_mcp/service.py:30` (`REDACTED`); `docs/guides/mcp-setup.md:49-51`; `packages/myelin-hub/web/src/pages/Settings.tsx:54`; `CLAUDE.md` Engineering Rules "Fail-closed"; 테스트 `packages/myelin-mcp/tests/test_service.py:16-48` | ✅ |
| T1 | `TypeOK` — 변수 치역(`file`, `cache ∈ [Caps → BOOLEAN]`, `registered ∈ BOOLEAN`, `lock ∈ Calls ∪ {NoCall}`, `pc`, `kind`, `revokedAtBegin`, 카운터 `∈ 0..Cardinality(Calls)`) | type invariant | `tla/Spec.tla` (작성 예정) | — |
| S1 | `Sanity_ReleaseThenRevoke == ~(released >= 1 /\ \E c \in Caps : ~file[c])` — **반드시 FAIL**: 반출과 철회가 한 실행 안에서 모두 도달 가능함을 보인다(모델이 공허하지 않음) | sanity (reachability) | 패턴 `consent-revocation/tla/Properties.tla` | — |

**Lean 4**: PROVEN — lake build ok, sorry 0, standard axioms only

## 5. 신뢰 기반과 버그를 숨길 수 있는 추상화

- 신뢰해야 하는 것: TLC 2026.10.28.014557 (rev: 56d37a9); Lean 4.34.0 kernel; the frozen property statements (PROPERTIES.md); model↔code correspondence (CORRESPONDENCE.md + reproduction test)
- 추상화:
  - A1: myelin.yaml 설정을 권한 2비트로 축약 — write = mcp.write_draft ∧ level≥1, expose = mcp.expose_confidential
  - A2: is_local_session() = TRUE 고정 (MYELIN_LLM 은 프로세스 수명 동안 불변)
  - A3: 철회(Revoke)는 원자적 1 action; truncate+write 사이의 부분 파일 창은 모델 밖이며 fix 는 ConfigError 시 fail-closed 라고 가정
  - A4: 권한은 TRUE→FALSE 단조(재허용 없음)
  - A5: 위반 판정은 Begin(락 획득) 시점의 디스크 권한 기준 — Check~Release 사이의 철회는 위반으로 세지 않음
  - A6: confidential 노트 분류·경로 고정
  - A7: MCP 프로세스 1개, 호출은 _serialized RLock 으로 직렬화(lock 변수)
  - A8: Open(재기동)은 lock 이 비어 있을 때 언제든 가능, 공정성 없음
  - A9: Release 이후(stdio 응답 이후)는 범위 밖
  - A10: 도구를 write / expose 두 종류로 축약; 입력 검증 실패와 Prepare 내부 I/O 는 한 action 으로 묶음

## 6. 기존 테스트 결과 (L0/L1)

- 1295 통과 · 0 실패 · 0 오류 · 명령: `/home/ubuntu-02/ai_project/MYELIN/.venv/bin/python -m pytest -q -p no:cacheprovider`

## 7. 미검증 범위

검증하지 않은 후보:

- C2 hub-add-domain-stale-vault — Hub add_domain 이 _mutation 진입 전에 잡은 Vault 를 core add_domain 에 넘겨, 그 사이 CLI 가 추가한 Domain 을 myelin.yaml 에서 지운다 — `packages/myelin-hub/api/src/myelin_hub_api/service.py:926-1014` (lost-update, H × M)
- C3 commons-publish-base-branch — 직렬화되지 않은 Commons 게시가 다른 게시의 publish/<id> 브랜치를 base 로 읽어 PR 에 남의 노트를 섞고 clone 을 엉뚱한 브랜치에 남긴다 — `packages/myelin-core/src/myelin_core/commons.py:319-404` (race, M × M)
- C4 hub-mutation-rollback-clobber — _mutation 실패 복원이 본문 실행 중 다른 프로세스가 쓴 내용을 스냅샷으로 덮는다 — `packages/myelin-hub/api/src/myelin_hub_api/service.py:305-339` (lost-update, M × L)
- C5 promote-dest-check-then-write — promote 가 dest.exists() 검사 뒤 write_text 로 써서, 그 사이 생긴 같은 이름의 사람 노트를 덮는다 — `packages/myelin-hub/api/src/myelin_hub_api/service.py:699-713` (check-then-act, M × L)
- C6 index-refresh-signature — 색인 갱신이 (mtime_ns, size) 서명만 비교해 같은 tick·같은 크기 재작성을 놓친다 — `packages/myelin-core/src/myelin_core/index.py:303-349` (dataflow-loss, M × L)
- C7 reload-drops-index-under-readers — myelin.yaml 이 순간적으로 파싱 불가일 때 reload 가 공유 SQLite 연결을 닫아 동시 질의가 500 으로 끝난다 — `packages/myelin-hub/api/src/myelin_hub_api/service.py:235-261` (race, L × L)
- C8 add-domain-rollback-residue — Hub add_domain 실패 롤백이 .obsidian/ 디렉터리 생성을 되돌리지 않는다 — `packages/myelin-hub/api/src/myelin_hub_api/service.py:994-1011` (other, L × L)

부수 발견 (재현·수정하지 않음):

- **F2** write_draft 도구 등록이 기동 시 1회 결정되어, 철회 후에도 도구 목록에 남는다(ADR-0007 '도구 자체가 없다'와 불일치) — `packages/myelin-mcp/src/myelin_mcp/server.py:127`: F1 을 호출 시 재적재로 고쳐도 등록 목록은 기동 시 기준이라, 철회 뒤 도구는 보이지만 호출이 거부된다. 안전성은 유지되나 ADR 문구와 다르며 tools/list_changed 알림도 없다. 반대로 기동 후 허용으로 바꾼 경우 재기동 전에는 도구가 나타나지 않는다. 검증하지 않음.
- **F3** write_draft 의 Domain 검증과 list_domains 가 캐시된 config 를 사용해, 기동 뒤 추가·삭제된 Domain 을 반영하지 않는다 — `packages/myelin-mcp/src/myelin_mcp/service.py:245-247`: self.vault.config.domains.all_ids(245-247)와 list_domains(184-210)의 level·domains·packs 도 같은 기동 시 캐시를 본다. 기동 후 myelin add-domain 으로 추가된 Domain 으로의 초안 쓰기가 거부되고, list_domains 는 옛 목록·옛 level 을 보고한다. 권한 철회와 같은 원인이지만 동결 속성 밖이라 검증하지 않음.
- **F4** 철회(Check)와 반출(Release) 사이 같은 호출 안의 수 ms 창은 fix 후에도 남는다 — `packages/myelin-mcp/src/myelin_mcp/service.py:142-155`: 설정 파일 읽기와 SQLite 본문 읽기를 프로세스 간 원자적으로 묶을 수 없어, 호출이 락을 잡은 뒤 끼어든 철회는 그 호출에는 반영되지 않는다(모델 가정 A5 로 위반에서 제외). 실질 위험은 낮다. 검증하지 않음.

## 8. 재실행 명령어

```bash
wdproof run MYELIN                # full pipeline on the current HEAD
cd <project> && ./formal/run_all.sh   # three-config gate only (needs java + tla2tools.jar)
python -m pytest packages/myelin-mcp/tests/test_formal_mcp_config_revocation.py
```

## 9. HITL 승인 이력

| ID | 게이트 | 종류 | 내용 | 적용 | 상태 | 승인자 |
|---|---|---|---|---|---|---|
| H1 | G2 | property-freeze | Frozen properties for concern 'mcp-config-revocation-stale' were harvested by the agent — confirm they express the intended behaviour. | 예 | **pending** | — |
| H2 | G7 | non-obvious-fix | Fix for F1 (mcp-config-revocation-stale) is marked non-obvious: packages/myelin-mcp/src/myelin_mcp/service.py: VaultService 가 기동 시 적재한 myelin.yaml 바이트(_config_bytes)를 기억하고, _serialized 래퍼가 서비스 락을 잡은 직후(도구 본문 실행 전) _reload_if_changed() 를 호출한다. 디스크 바이트가 마지막 적재본과 다르면 | 예 | **pending** | — |

## 10. 후속 제안

- `wdproof review` 로 승인 대기 항목 처리
- W5: `wdproof ci install` 로 3-config 게이트와 드리프트 검사를 CI에 등록
- W7: `wdproof run --promote` 로 안전성 속성을 Lean 4 로 승격 (모든 크기에 대한 증명)
- 다음 순위 후보에 대해 재실행 (wdproof.yaml 의 hints 로 지정)

## 11. Definition of Done 체크리스트

| 단계 | 검사 | 결과 | 메시지 |
|---|---|---|---|
| S2 | schema:candidates | [x] | valid |
| S2 | source_untouched | [x] | source files unchanged |
| S2 | candidate_pointers | [x] | 8 candidate(s) point at real code |
| S3 | schema:selected | [x] | valid |
| S3 | source_untouched | [x] | source files unchanged |
| S3 | correspondence | [x] | 48 pointer(s) valid across 12 file(s) |
| S4 | frozen_properties | [x] | 1 frozen file(s) unchanged |
| S4 | source_untouched | [x] | source files unchanged |
| S4 | schema:model | [x] | valid |
| S4 | correspondence | [x] | 48 pointer(s) valid across 12 file(s) |
| S4 | three_config | [x] | 5 configs match expectations; MC: 919 distinct states, depth 15 |
| S5 | schema:repro | [x] | valid |
| S5 | source_untouched | [x] | source files unchanged |
| S5 | reproduce | [x] | 2 test(s) fail on unchanged code by assertion: packages.myelin-mcp.tests.test_formal_mcp_config_revocation::test_p1_no_draft_after_write_draft_revoked, packages.myelin-mcp.tests.test_formal_mcp_config_revocation::test_p2 |
| S6 | schema:findings_draft | [x] | valid |
| S6 | source_untouched | [x] | source files unchanged |
| S6 | root_cause_location | [x] | root-cause location agrees with the correspondence table |
| S7 | schema:fix | [x] | valid |
| S7 | patch_audit | [x] | minimal patch: 1 file(s), +38/-1, public API unchanged |
| S7 | frozen_properties | [x] | 3 frozen file(s) unchanged |
| S7 | repro_after_fix | [x] | 2 reproduction test(s) pass after the fix |
| S7 | regression | [x] | no regression: 1297 passed (baseline 1295) |
| S7 | three_config | [x] | 5 configs match expectations; MC: 919 distinct states, depth 15 |
| S7 | mutation | [x] | fix reverted -> reproduction fails again by assertion; fix re-applied |
| S8 | lean_trust | [x] | lake build ok · sorry 0 · standard axioms only |
| S8 | frozen_properties | [x] | 3 frozen file(s) unchanged |

## 12. 변경 파일과 산출물

- 수정 파일: `packages/myelin-mcp/src/myelin_mcp/service.py`
- 재현 테스트: `packages/myelin-mcp/tests/test_formal_mcp_config_revocation.py`
- 산출물: `formal/` (README.md, TOOLCHAIN.lock, CANDIDATES.md, findings.json, run_all.sh, `mcp-config-revocation-stale/`{SCOPE.md, PROPERTIES.md, CORRESPONDENCE.md, tla/, evidence/})
- 브랜치: `wdproof/20261121-115639-myelin`
