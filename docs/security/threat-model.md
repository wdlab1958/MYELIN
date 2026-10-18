# MYELIN v1.0 위협 모델 (STRIDE) — P8-T1

- 일자: 2026-10-18 · 범위: Vault · Claude Code Plugin(Guard) · MCP · Hub · Commons · 공급망 · 설치
- 심각도: **High**(공격자가 사람 승인 없이 Vault 를 바꾸거나 기밀을 밖으로 보낼 수 있음) / Medium / Low
- 판정 규칙: High 는 v1.0 에서 **모두 조치**(P8-T2, 회귀 테스트 동반). Medium 은 완화 + Backlog. Low 는 기록.

## 자산과 신뢰 경계
| 자산 | 설명 |
|---|---|
| A1 Vault 정본 | `10_Domains/`, `40_IP/`(confidential), `myelin.yaml`, `CLAUDE.md` — 사람 승인 영역 |
| A2 AI 초안 영역 | `00_Inbox/ai-drafts/`, `_patches/`, `80_Outputs/drafts/`, `50_Journal/`, `40_IP/candidates/`(L3) |
| A3 기밀 | `classification: confidential` 노트, `40_IP/**` |
| A4 Commons | 사내 git — 공개 승인 노트·Registry·익명 지표 |
| A5 자격 | git 자격, `gh` 토큰, Claude 플랜 |

경계: ① Claude(외부 LLM) ↔ 로컬(Guard/Plugin) ② 로컬 프로세스(MCP/Hub) ↔ Vault 파일 ③ 개인 Vault ↔ Commons(사내망) ④ 브라우저 ↔ Hub(localhost).

## 위협 표

| ID | 구성 | STRIDE | 위협 | 통제 | 잔여 | 심각도 | 상태 |
|---|---|---|---|---|---|---|---|
| T01 | Guard | Tampering | Claude 가 Write/Edit 로 사람 승인 영역 수정 | PreToolUse hook, Level 별 허용 경로, symlink/`..` 해석, 판단 불가 차단(ADR-0005) · settings.json `Edit(...)` deny | hook 미설치 세션 | Medium | 설치 스크립트가 plugin 등록·검증, Vault CLAUDE.md 가 규칙 명시 |
| T02 | Guard | Tampering | Bash 우회(리다이렉션·tee·sed -i·mv·rm·인라인/stdin 인터프리터·Vault 내부 스크립트 실행·`$(…)`·`cd`+쓰기·줄바꿈/주석/래퍼/키워드 접두·find/awk/curl/wget·git 비-읽기 서브커맨드·**`git commit --no-verify`**) | `guard_bash.py` 허용 목록형 판정 + 적대 테스트 394 케이스(`tests/plugin/test_guard_adversarial.py`) + Bash deny/ask 접두어 · **EXTERNAL 세션에서 `40_IP/**` 쓰기는 Level 3 에도 차단**(ADR-0011 §2, `test_guard_write.py::test_level_matrix`, `test_guard_bash.py::test_level_matrix_bash`, `test_guard_read.py::test_bash_write_to_ip_blocked_external_even_at_level_3`) · `--no-verify`/`-n` 차단(`test_guard_bash.py::BLOCKED_L1`) | Vault **밖** 스크립트·패키지 설치·네트워크 송신(`curl -T`, `scp`)은 쓰기 정책 범위 밖 | Medium | 조치(QA 2026-10-18): 12 우회 경로 차단 → 회귀 테스트 고정. 잔여는 settings.json ask(`bash/sh/perl/ruby/curl/wget`) + 커밋 이력 사후 감사 + **T21 pre-commit 장치가 커밋 단계에서 재검사** |
| T03 | Guard | Elevation | AI 가 `myelin.yaml level` 을 올려 허용 경로 확장 | `myelin.yaml` 은 쓰기 금지 경로(Guard+deny), Hub 설정 저장은 사람 클릭 | — | Low | 통제됨 |
| T04 | Guard | Repudiation | AI 커밋이 사람 커밋과 섞임 | `[myelin:<skill>]` 접두사, `origin` 추적, git commit 은 ask | — | Low | 통제됨 |
| T05 | MCP | Info disclosure | confidential/40_IP 본문이 외부 Claude 로 유출 | 기본 `expose_confidential: false` — 검색 제외·본문 대체(ADR-0007) · **`true` 는 프로세스가 LOCAL(`MYELIN_LLM=local`)일 때만 유효, 아니면 stderr 경고 + false 동작, 도구 설명·instructions 에 기밀 언급 없음**(ADR-0011 §3, `packages/myelin-mcp/tests/test_routing.py` 12 tests) | 로컬 세션 운영자가 변수를 잘못 켠 채 외부 클라이언트를 붙이는 경우(사람 행위) | Low | 조치(2026-10-18): 가이드 규칙 → 장치. "소유자가 켜고 외부 세션에 사용" 잔여 제거 |
| T06 | MCP | Tampering | `write_draft` 로 ai-drafts 밖 쓰기/덮어쓰기 | 도구 자체가 opt-in+Level, 경로 검증, `x` 모드, 검증 실패 시 삭제 | — | Low | 통제됨 |
| T07 | MCP | Info disclosure | `get_note` 경로 이탈(`..`, symlink) | `safe_rel` 경계 검사, 존재 여부 비노출 | — | Low | 통제됨(7 tests) |
| T08 | Hub | Tampering | 악성 사이트 탭이 Hub 쓰기 API 호출(CSRF) / DNS rebinding | 쓰기는 커스텀 헤더 필수(cross-site 는 CORS preflight 실패), **Host/Origin 검증 미들웨어** | — | **High → 조치** | `HostOriginGuard`: Host 가 loopback 이 아니거나 Origin 이 loopback 이 아니면 403 · 회귀 `test_host_and_origin_guard` |
| T09 | Hub | Info disclosure | 정적 SPA 서빙 `/{full_path}` 경로 이탈로 dist 밖 파일 읽기 | **resolve 후 dist 내부 검증** | — | **High → 조치** | 회귀 `test_static_no_path_traversal`(`..`, `%2e%2e`, `assets/../..`) |
| T10 | Hub | Spoofing | 같은 호스트의 다른 로컬 사용자가 Hub 포트 접근 | loopback 바인딩, 비-loopback 기동 거부 | 공유 호스트 | Medium | Team 모드 인증(Backlog), 가이드에 공유 호스트 금지 |
| T11 | Hub | Tampering | Pack 편집기로 `me.*` 외 경로 쓰기 | 이름 = Pack 정규식 + `me.` 접두 + 로더 검증 | — | Low | 통제됨 |
| T12 | Commons | Info disclosure | confidential/share:false 노트 공개 | 하드 게이트(쓰기 전 차단) | — | Low | 통제됨(차단 100% 테스트) |
| T13 | Commons | Info disclosure | 고객명·IP 가 본문에 남은 채 공개 | 비식별 스캔(내장 7 + deid.yaml) + 사용자 확인 + 챔피언 PR 리뷰 | 스캔이 모르는 식별자 | Medium | deid.yaml 운영 + 챔피언 리뷰(2중) · Backlog: Commons CI 재스캔 |
| T14 | Commons | Info disclosure | 익명 지표에 식별 정보 혼입 | 허용 키 집합·익명성 가드·opt-in | — | Low | 통제됨 |
| T15 | Commons | Tampering | publish 가 main 에 직접 커밋 | 브랜치 전용, base 복귀 | 수동 merge | Low | 챔피언 merge 규칙 |
| T16 | 공급망 | Tampering | 의존성 변조/취약점 | `uv.lock`·`package-lock.json` 고정, hook 은 표준 라이브러리만 | 잠금 갱신 시 검토 | Medium | Gate 에 `uv lock --check` · `npm audit` 결과 릴리스 노트 기록 |
| T17 | 설치 | Tampering | 설치 스크립트가 사용자 파일 덮어씀 | 기존 파일 보존(`.myelin` 접미/`.bak`), 드라이런 | — | Low | `tests/test_install.py` |
| T18 | Vault | Denial | 색인 DB 손상 | 캐시 — 삭제 후 재구축, 스키마 버전 검사 | — | Low | 통제됨 |
| T19 | Plugin | Spoofing | 변조된 marketplace 에서 plugin 설치 | 로컬 marketplace(저장소 경로)만 안내, `claude plugin validate --strict` | — | Low | 가이드 |
| T20 | Guard·MCP | Info disclosure | **외부 세션의 기밀 읽기** — 외부 Claude Code 세션이 Read/Grep/Glob/Bash(`cat`, `grep -r`, `rg`, `find`, `git show`…)로 `40_IP/**`·`classification: confidential` 노트를 읽어 외부 모델로 보냄(v1.0 까지 `llm.route` 는 CLAUDE.md 문장일 뿐) | `guard_read.py`(PreToolUse `Read\|Grep\|Glob`) + `guard_bash.py` 읽기 채널 판정: 세션이 `MYELIN_LLM=local` 이 아니면 40_IP 경로(symlink·`..`·NFD·글로브·중괄호 해소 후)·confidential frontmatter(표준 라이브러리 파싱, 판단 불가=차단)·Vault 전체 검색(40_IP 에 파일 있거나 confidential 노트 존재)·patch 출력 git 명령 차단 · settings.json `Read(./40_IP/**)` deny(2차) · MCP T05 (ADR-0011 §1~§4) | 40_IP 밖 confidential 노트의 **제목**(Glob/ls/find) · `.myelin/index.db` 본문 캐시 · Vault 밖 스크립트 · git 이력 속 과거 기밀 · frontmatter 없는 `.md` · 플러그인 미설치 세션(T01) | Medium | 조치(2026-10-18): `tests/plugin/test_guard_read.py` 118 tests(Read 40_IP/confidential/spellings/unjudgeable/symlink/`..`/NFD/env 변형/nested vault, Grep·Glob 루트 판정, Bash 읽기 40+ 차단·26 허용 사례, LOCAL 허용) · 잔여는 ADR-0011 "잔여 위험" 에 기록, 제목 노출·index.db 는 Backlog |
| T21 | Vault·git | Tampering / Repudiation | **Claude Code 밖 도구의 승인 영역 커밋** — Obsidian Git·터미널·다른 에이전트가 `origin: claude` 초안을 `10_Domains/` 에 그대로 커밋하거나 `verified` 를 `reviewed` 없이 커밋(Guard 는 Claude Code 안에서만 동작) | Vault git **pre-commit 장치**: `90_System/hooks/pre-commit`(스캐폴드) → `.git/hooks/pre-commit`(`myelin init` / `myelin doctor --install-hook`, 755) 이 `myelin doctor --staged` 실행 — 인덱스 blob 기준 ERROR 규칙(`ai-scope`: origin claude 가 Level 쓰기 범위 밖, `temporal`, `confidential-share`, `schema`, `domain`) 위반 시 커밋 거부, CLI 부재 시 fail-closed 거부 · Hub Promote(origin mixed+reviewed)·Reject(99_Archive deprecated) 는 통과 · AI 의 `git commit --no-verify` 는 guard_bash 가 차단 (ADR-0011 §5) | 사람의 `--no-verify`·hook 삭제·`core.hooksPath`(사람 권한) · Hub `ensure_git` 은 아직 hook 을 설치하지 않음(두 줄 변경 대기) · 다른 pre-commit 이 이미 있으면 설치 거부(사람이 합쳐야 함) · 링크 그래프 규칙은 커밋 게이트 밖 | Medium | 조치(2026-10-18): `packages/myelin-cli/tests/test_cli_devices.py` 31 tests(설치/재설치/타 hook 보존/`--staged` 8 오류·9 통과 사례/인덱스 vs 작업 트리/Level 범위/중첩 Vault/실제 git 커밋 거부→허용/`--no-verify` 사람 우회/CLI 부재 fail-closed/add-domain 통과) · Hub 연결은 Backlog |

## High 항목 조치 결과 (P8-T2)
| ID | 조치 | 회귀 테스트 |
|---|---|---|
| T08 | `HostOriginGuard` 미들웨어(Host ∈ {localhost, 127.0.0.1, [::1]}, Origin 없거나 loopback) | `packages/myelin-hub/api/tests/test_api.py::test_host_and_origin_guard` |
| T09 | `spa()` 가 `WEB_DIST` 내부로 resolve 되는 파일만 반환 | `…::test_static_no_path_traversal` |

**High 잔여: 0.** Medium(T01, T02, T10, T13, T16, **T20, T21**)은 완화 적용 상태로 릴리스 노트 "알려진 제약" 에 기재. T05 는 2026-10-18 ADR-0011 조치로 Medium → Low.

## ADR-0011 조치 결과 (2026-10-18, v1.1)
| ID | 조치 | 회귀 테스트 |
|---|---|---|
| T20 | `plugin/hooks/guard_read.py` 신설(`Read\|Grep\|Glob`) · `guard_bash.py` EXTERNAL 읽기 채널 판정 · `guard_common.require_local_for_ip`(40_IP 쓰기는 LOCAL 만) · settings.json `Read(./40_IP/**)` | `tests/plugin/test_guard_read.py`, `test_guard_sync.py::test_llm_routing_constants_in_sync`, `test_guard_write.py::test_level_matrix`, `packages/myelin-cli/tests/test_cli_devices.py::test_settings_json_denies_read_of_ip`, golden `init-basic/.claude/settings.json` |
| T05 | `VaultService.expose_confidential` = opt-in AND `MYELIN_LLM=local` · `routing_warning()` stderr · 도구 설명/instructions 에서 기밀 언급 제거 | `packages/myelin-mcp/tests/test_routing.py` |
| T21 | `scaffold.PRE_COMMIT_BODY` + `install_git_hook()` · `myelin doctor --staged` / `--install-hook` · `doctor.run_doctor_staged`(`ai-scope` 규칙) · CLI `_git_commit_vault` 가 저장소 생성 시 설치하고 `MYELIN_BIN` 으로 자기 자신을 지정 | `packages/myelin-cli/tests/test_cli_devices.py`, golden `init-basic/90_System/hooks/pre-commit` |
