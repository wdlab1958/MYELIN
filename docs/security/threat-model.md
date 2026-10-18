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
| T02 | Guard | Tampering | Bash 우회(리다이렉션·tee·sed -i·mv·rm·인라인 인터프리터·`$(…)`·`cd`+쓰기) | `guard_bash.py` 90 케이스 차단 + Bash deny 접두어 | **스크립트 파일 실행** 부작용 미검사 | Medium | 완화(P8-T2): settings.json 에 `Bash(python *)`·`Bash(python3 *)`·`Bash(uv run python *)`·`Bash(node *)` **ask** · 커밋 이력 사후 감사 |
| T03 | Guard | Elevation | AI 가 `myelin.yaml level` 을 올려 허용 경로 확장 | `myelin.yaml` 은 쓰기 금지 경로(Guard+deny), Hub 설정 저장은 사람 클릭 | — | Low | 통제됨 |
| T04 | Guard | Repudiation | AI 커밋이 사람 커밋과 섞임 | `[myelin:<skill>]` 접두사, `origin` 추적, git commit 은 ask | — | Low | 통제됨 |
| T05 | MCP | Info disclosure | confidential/40_IP 본문이 외부 Claude 로 유출 | 기본 `expose_confidential: false` — 검색 제외·본문 대체(ADR-0007) | 소유자가 켜고 외부 세션에 사용 | Medium | 가이드 명시(로컬 LLM 세션에서만) |
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

## High 항목 조치 결과 (P8-T2)
| ID | 조치 | 회귀 테스트 |
|---|---|---|
| T08 | `HostOriginGuard` 미들웨어(Host ∈ {localhost, 127.0.0.1, [::1]}, Origin 없거나 loopback) | `packages/myelin-hub/api/tests/test_api.py::test_host_and_origin_guard` |
| T09 | `spa()` 가 `WEB_DIST` 내부로 resolve 되는 파일만 반환 | `…::test_static_no_path_traversal` |

**High 잔여: 0.** Medium 4건(T01, T02, T05, T10, T13, T16 중 완화 적용)은 릴리스 노트 "알려진 제약" 에 기재.
