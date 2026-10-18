# ADR-0010: Commons 공개·비식별·익명 지표 정책

- 상태: Accepted · 일자: 2026-10-18 · Phase: P7
- 근거: 정본 §9.1 Team Commons 원칙, §11.2 조직 지표(opt-in 익명 집계), §P7 착수 프롬프트 "개인 Vault 내용을 외부로 보내는 모든 경로는 사용자 확인 단계를 거치게 하라"

## 결정

1. **Commons 는 별도 git 저장소**(`registry/`, `notes/<DOMAIN>/`, `proposals/packs/`, `metrics/`). 로컬 clone 경로는 `myelin.yaml commons.local`, 원격은 `commons.remote`. `myelin commons init` 이 골격을 만든다.
2. **공개 조건(하드 게이트)**: `share: true` ∧ `status: verified` ∧ `classification ≤ internal` ∧ `40_IP/` 밖 ∧ confidential 노트 링크 없음. 하나라도 어긋나면 publish 는 **쓰기 전에** 실패한다(테스트: confidential/share:false 차단 100%).
3. **비식별 스캔**: IP·이메일·전화·주민번호·시크릿·내부 URL·기밀 표시어 내장 정규식 + `deid.yaml`(Commons 공통 + Vault `90_System/deid.yaml`)의 고객명·시스템명 용어/정규식. 적중 1건이라도 있으면 차단. 사람은 노트를 고치고 다시 시도한다(자동 치환은 하지 않는다 — 치환은 의미를 바꾼다).
4. **사용자 확인 단계 필수**: CLI 는 검사 결과를 보여 준 뒤 `y` 입력(또는 스크립트용 `--yes`), Hub 는 검사 결과 + "비식별 확인" 체크 + "Commons 제안" 클릭(헤더 ADR-0009). 코어 API 는 `confirmed=True` 가 없으면 아무것도 쓰지 않는다.
5. **공개 = 브랜치 + 커밋 + PR**: `publish/<note-id>` 브랜치에 커밋 1개. `--push` 시 원격 push, `gh` 가 있으면 PR 생성, 아니면 PR URL 안내. main 직접 커밋 금지. 공개 노트는 `author`·`published_from`(원 id)·`published_by`(익명 해시)·`published` 를 frontmatter 에 보존 → 인용 시 기여가 보인다(정본 §9.1 출처 보존).
6. **Pack 진화**: 개인 Pack → `propose/<name>` 브랜치의 `proposals/packs/<name>/` + `PROPOSAL.md`. 비식별 스캔 동일.
7. **익명 지표(opt-in)**: `commons.metrics_opt_in: true` 일 때만 `metrics/<owner-hash>/<week>.json` 을 쓴다. 페이로드는 **허용 키 11개의 스칼라만**(active, verified_7d, onboarding_minutes, published, proposals, notes, level, packs_count …). 소유자 식별은 `sha256(email|name)[:12]`. 노트 제목·경로·본문·이메일이 들어가면 `payload_is_anonymous()` 가 거부한다(테스트로 고정). 집계는 `myelin metrics aggregate <commons>`.
8. **온보딩 시간 계측**: Hub 온보딩/CLI init 이 `.myelin/metrics.jsonl` 에 `onboard_start`, 첫 승격이 `first_promote` 를 기록. `onboarding_minutes` = 두 시각의 차. 파일럿 Gate(≤ 15분) 는 이 값을 `scripts/pilot.py record` 로 모은다.
9. **Org Pack 확정**: Registry `index.yaml` 의 `champions` 가 비어 있으면 "초안". P7 산출물로 `org.security-consulting` 과 `org.incident-response` 를 Registry 에 올리되, 챔피언 서명(이름 기입)은 사람이 한다.

## 결과
- 개인 Vault 에서 밖으로 나가는 경로는 publish·propose·metrics 셋뿐이며 모두 확인 단계와 비식별/익명 검사를 지난다.
- myelin.yaml 필드 추가: `commons.local`, `commons.metrics_opt_in` (ADR-0004 보강).
