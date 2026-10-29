# formal/ — MYELIN 형식 검증 (WDLAB-STD-VERIFY-001 v1.0)

| concern | 대상 | 결과 (2026-10-29) |
|---|---|---|
| [`hub-config-stale-cache/`](hub-config-stale-cache/SCOPE.md) | Hub 가 캐시한 `myelin.yaml` vs CLI `myelin add-domain` vs Settings 저장 | **F1 FIXED** (Hub 가 파일 변경을 요청마다 감지해 재로드) · **F2 CONFIRMED** (Settings GET→PUT 창, If-Match 제안, HITL) · **F3 CONFIRMED** (CLI `git add -A` 커밋 범위, 제안만) · 모델 **BOUNDED-PASS** `Doms={d1,d2}` 72 states / depth 7, `{d1,d2,d3}` 432 / depth 9 |

무엇을 모델링했나: 세 행위자(CLI 프로세스 · Hub 서버 · 브라우저 Settings 페이지)가 `<Vault>/myelin.yaml` 의 Domain 목록을 공유하는 인터리빙을 TLA+ 로 전수 탐색했다. 속성은 `tla/Properties.tla` 에 동결(P1 결정은 파일 기준, P2 Settings 저장은 Domain 을 지우지 않음). fix 토글 `ReloadOnRequest`(구현) · `IfMatch`(제안).

## 실행
```bash
TLC_WORKERS=4 formal/run_all.sh          # 3-config 게이트: MC PASS · MC_bug/MC_bug_p2/MC_partial/MC_sanity FAIL(12) · MC_3 PASS
.venv/bin/python -m pytest packages/myelin-hub/api/tests/test_config_reload.py -v     # F1 재현 테스트 (수정 후 통과)
.venv/bin/python formal/hub-config-stale-cache/repro/repro_F2_settings_put_window.py  # F2: exit 1 (미수정)
.venv/bin/python formal/hub-config-stale-cache/repro/repro_F3_add_domain_commit_scope.py  # F3: exit 1 (미수정)
```
TLC 는 `~/.cache/proof-skills/tla2tools.jar`(`$TLA2TOOLS` 로 지정 가능) + Java 21 을 쓴다. 루트 모듈은 `Properties.tla`(`EXTENDS Spec`).

## 파일
- `CANDIDATES.md` G0 후보표 · `findings.json` 기계 판독 결과(proof-skills 스키마 + `wdlab` 블록) · `TOOLCHAIN.lock` · `run_all.sh`
- `<concern>/SCOPE.md` · `CORRESPONDENCE.md`(모델 ↔ `file:line`) · `tla/` · `evidence/`(TLC 로그·트레이스·테스트 전/후·mutation·패치 diff) · `repro/`(스위트 밖 재현 스크립트)
- `reports/2026-10-29-hub-config-stale-cache.md` 보고서 사본 (docx: `~/ai_project/Proof-Skills/MYELIN_ProofSkills_Report_2026-10-29.docx`)

예외 기록: Lean 4 미설치로 L3 는 주장하지 않는다(유한 상태 속성이라 승격 필요성도 낮음). Artifact HTML 대신 docx 보고서를 발행했다.
