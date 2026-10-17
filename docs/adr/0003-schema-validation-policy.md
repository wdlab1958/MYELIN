# ADR-0003: 스키마 검증 정책 (Frontmatter v2 · Pack)

- 상태: Accepted · 일자: 2026-10-18 · Phase: P1
- 근거: 정본 §6.2, §5.2, CLAUDE.md "스키마 변경은 ADR 선행"

## 결정

1. **정본 필드만 모델에 둔다.** Frontmatter 12필드(§6.2), Pack/Domain 필드(§5.2)는 정본 그대로. 필드 추가 없음.
2. **Frontmatter의 미지 필드는 허용·보존**(`extra="allow"`). Obsidian 사용자가 `aliases`, `cssclasses` 등을 쓰는 것이 일반적이며, 거부하면 기존 Vault 도입이 막힌다. 미지 필드는 doctor가 info 수준으로 보고(P2).
3. **Pack/Domain의 미지 필드는 금지**(`extra="forbid"`). Pack은 MYELIN이 소유하는 선언이며 오타(`sub_moc:` 등)를 조기에 잡아야 한다.
4. **교차 필드 모순은 파싱 오류가 아니라 doctor 규칙.** `confidential + share:true`, `reviewed < created`, `verified without reviewed`, `moc without domain` 은 `Frontmatter.consistency_issues()`로 노출하고 노트는 파싱된다. 정본 §6.2가 이 검출을 doctor에 배정했기 때문.
5. **형식 규칙**: `id` = `YYYYMMDD-HHMM-slug`(날짜·시각 실재 검사), Domain ID = `^[A-Z][A-Z0-9-]{0,31}$`, tag = 소문자/숫자/`/`/`_`/`-`, Pack 이름 = `owner.name`(소문자 점 구분), 버전 = semver(2자리 `1.0`은 `1.0.0`으로 정규화).
6. **Domain `accent`는 Emboss 토큰 이름의 닫힌 집합** `{violet, lime, cyan, magenta}`. `design/tokens.json`에 해당 색이 있어야 하며 테스트가 동기화를 검사한다. 확장은 tokens.json(데이터) + 이 집합 갱신으로만.
7. **스칼라 → 리스트 관용 허용**: `domain: D1`, `tags: rtos` 처럼 단일 값은 1원소 리스트로 받는다.

## 결과

- 사용자 Vault 호환성 유지, Pack 작성 오류는 즉시 노출(fail-closed).
- doctor(P2)는 `consistency_issues()`를 그대로 규칙으로 사용한다.
