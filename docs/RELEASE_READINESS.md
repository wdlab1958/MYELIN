# 출하 점검표 (Release Readiness) — v1.4.0 · 2026-11-26

> ✅ 근거 있음 · ⚠️ 부분/한계 있음 · ❌ 미완료. "근거"는 이 저장소 안의 파일이나 테스트다. 측정하지 않은 것은 측정하지 않았다고 적는다.
> MYELIN 은 고객에게 파는 상품이 아니라 One Cycle Dev. Framework 의 정보 자산을 관리하는 내부 개인 지식 관리 서비스다.

## 1. 선결 과제 (사업 모델 v2.1 §5.5 · WBS 2.5)

| 항목 | 상태 | 근거 |
|---|---|---|
| 2.5.1 형식 검증 수정 반영 — "설정 철회 후에도 기밀 본문 반출"(MCP) | ✅ | `packages/myelin-mcp/src/myelin_mcp/service.py` `_reload_if_changed` · `packages/myelin-mcp/tests/test_formal_mcp_config_revocation.py`(수정 제거 시 실패 확인) · `formal/mcp-config-revocation-stale/`(TLC + Lean) |
| 2.5.1 F3 — `add-domain` 의 `git add -A` | ✅ | `packages/myelin-cli/src/myelin_cli/app.py` `_stage_only` · `test_cli.py::test_add_domain_commits_only_its_own_paths` · `formal/hub-config-stale-cache/repro/repro_F3_*.py` exit 0 |
| 2.5.1 `formal/` 의 나머지 — 미수정 CONFIRMED | ✅ 0건 | `formal/README.md` 표 · `formal/findings.json` |
| 2.5.1 의심 후보(2026-11-21 라운드) | ⚠️ | C2·C3·C5·C6 재현 후 수정(`test_formal_candidates.py`, `test_index.py`). **C4·C7·C8, MCP 부수 발견 F2·F4 는 미수정**(기록, `formal/README.md`) |
| 2.5.1 형식 검증 게이트 | ✅ | `formal/mcp-config-revocation-stale/evidence/run_all_2026-11-26.log`(31개 설정) · `lean_audit_2026-11-26.log` · `correspondence_check.py` 0 broken |
| 2.5.2 버전 표기 통일 | ✅ | 단일 원천 `packages/myelin-core/src/myelin_core/_version.py` · `scripts/sync_version.py --check` · `tests/test_version.py`. (Claude Code plugin 은 별도 버전) |
| 2.5.3 A3 Domain Pack 2종 완성 | ⚠️ | `packs/a3.security-consulting`(587줄) · `packs/a3.incident-response`(627줄), `scripts/validate_packs.py` + 임시 Vault `myelin add-domain` + 템플릿 19개 렌더 → doctor 0 errors. **용어는 A3 컨설턴트 확인 전**(사람의 일) |
| 2.5.4 사내 파일럿 5명 · 담당자 지정 | ❌ | 사람이 해야 한다. 준비물만: `docs/guides/pilot-kit.md`, `scripts/pilot.py`. 파일럿 기록(`docs/reports/P7/pilot-results.jsonl`) 없음 |
| 2.5.5 Hub 팀 공유 인증 | ⚠️ | Team 모드 구현(ADR-0016) · `test_team_mode.py` 39건. 사용자 관리 화면·토큰 만료·SSO 없음, 침투 시험 미실시, 웹 UI 토큰 입력은 e2e 미확인 |
| 2.5.5 고객 정보 기록 금지 지침 + 장치 | ⚠️ | `docs/guides/knowledge-management-policy.md` · `myelin_core/infoguard.py`(ADR-0017) · `test_infoguard.py` 27건 외. 패턴 검사의 한계(미탐) 있음, 실제 노트로 오탐·미탐률 미측정, 지침은 법무·보안 검토 전 |
| 1.6 명칭·상표 확인 | ❌ | 사람이 해야 한다(KIPRIS 제9류·제42류). `docs/reports/P8/naming-check.md` 에 결과 미기입. 코드 쪽 준비: 표시 이름 상수 `myelin_core.product.PRODUCT_NAME` |
| 3.6 · 3.5 One Cycle 인계 수신 | ⚠️ | `myelin onecycle import-findings` · `packs/wdlab.onecycle` · 라우팅 규칙(ADR-0018) · `test_onecycle.py` 28건 · `test_guard_onecycle_hub.py` 10건 · `docs/onecycle/HANDOFF.md`. 다섯 플랫폼의 실제 내보내기를 이어 돌린 시험은 하지 않음 |

## 2. 공통 항목

| 항목 | 상태 | 근거 |
|---|---|---|
| C1 라이선스 | ✅ | Apache-2.0 유지(`LICENSE`·`NOTICE`), README §12. 법무 검토 전 |
| C2 제3자 라이선스 | ⚠️ | `THIRD_PARTY_LICENSES.md` — 직접 의존성 24개(설치 메타데이터 기준), copyleft·비상업 0, 미확인 1(`hatchling`). 전이 의존성 미검토, Ollama 모델 라이선스는 사용자 책임 |
| C3 기본값 보안 | ✅ | 기본 계정·비밀번호·내장 키 없음. Personal 모드는 loopback 전용(`test_non_loopback_bind_needs_auth_hosts_and_tls`), Host/Origin 검증, CORS 헤더 없음(`test_host_origin_and_cors_defaults`). 비-loopback 은 인증 없이는 기동 거부. 쓰기는 클릭 헤더 필수(`test_writes_require_user_click`) |
| C3 loopback 무인증 | ⚠️ | 설계상 Personal 모드는 인증이 없다(정본 §4.4). 같은 PC 의 다른 로그인 사용자는 접근 가능 — 공유 호스트에서 띄우지 않는다(INSTALL §4) |
| C4 형식 검증 | ⚠️ | 위 2.5.1 행들 |
| C5 버전·CHANGELOG·설치 문서 | ⚠️ | `CHANGELOG.md` v1.4.0(2026-11-26) · `docs/INSTALL.md`. **망분리 설치 절차는 실제 망분리 PC 에서 검증하지 않음**. 하드웨어 요구 사양은 측정값 없음 |
| C6 README 정합 | ✅ | README 상태·형식 검증·명령·ADR·검증 요약·제약·라이선스 절 갱신 |

## 3. 검증 (2026-11-26 실행)

| 항목 | 상태 | 결과 |
|---|---|---|
| 전체 테스트 | ✅ | 1,418 passed · 1 skipped (`.venv/bin/python -m pytest -q`). 변경 전 1,295 passed · 1 skipped — 기존 실패 0 |
| ruff · ruff format · mypy(strict) | ✅ | 통과 |
| TLC 게이트 · Lean 감사 · 포인터 검사 | ✅ | 31개 설정 기대값 · 2개 프로젝트 clean · 0 broken |
| Hub 웹 타입 검사 | ✅ | `tsc --noEmit` 통과 |
| Hub 웹 빌드 · Playwright e2e | ❌ 미실행 | 실행 중인 Hub 에 영향을 주지 않으려고 `dist/` 를 다시 만들지 않았다. 적용하려면 `make web`, 확인은 `make e2e` |
| Phase Gate(`make gate P=9`) · 성능 벤치 · 접근성 검사 | ❌ 미실행 | `make` 대상이 `uv sync`(네트워크)를 부른다. 이전 결과는 `docs/reports/` |
| GitHub CI | ❌ 미확인 | 커밋·push 하지 않았다(작업 트리에만 있음) |

## 4. 재시작 후 달라지는 동작 (소유자 로컬 배포)

1. 새 필수 환경 변수·마이그레이션 **없음**. Personal 모드 Hub 는 인증 없이 그대로 뜬다.
2. 자격증명·주민번호·등록한 고객명이 든 초안은 승격과 커밋이 거부된다. 긴 코드 블록(30줄 초과)·IP·내부 URL 이 든 초안은 승격 때 확인을 한 번 더 묻는다.
3. `myelin add-domain`·`myelin obsidian setup` 의 커밋에 무관한 파일이 더 이상 들어가지 않는다(작업 트리에 그대로 남는다).
4. MCP 서버가 `myelin.yaml` 변경을 다음 호출부터 반영한다. 설정 파일이 깨져 있으면 고칠 때까지 모든 MCP 호출이 거부된다.
5. 색인이 첫 실행에서 일부 노트를 한 번 다시 읽는다(자동, 변경 감지 기준 변경).
6. Hub 웹 UI 변경(Team 토큰 입력, 가드 확인 창)은 `make web` 으로 다시 빌드해야 `dist/` 에 반영된다.
