# ADR-0004: myelin.yaml 스키마 확정 사항

- 상태: Accepted · 일자: 2026-10-18 · Phase: P2
- 근거: 정본 §5.3 (예시만 제시, 필드 제약 없음), §5.4 3+1 규칙

## 결정

1. **필드는 정본 예시 그대로**: `owner{name,team,email}`, `language`, `packs[]`, `domains{primary,research,growth}`, `level`, `llm{default,route}`, `commons{enabled,remote}`. 미지 필드 금지(Pack과 동일 정책, ADR-0003 §3).
2. **`domains.extra: []` 추가** — §5.4의 "+1 (선택)" Domain을 담는 유일한 자리. `myelin add-domain` 은 항상 `extra` 에 추가한다(primary/research/growth 변경은 사람이 파일을 편집).
3. **`domains.primary` 만 필수.** research/growth 는 선택 — 온보딩 마찰을 줄이기 위해(§3 Low-friction Onboarding). 모든 Domain ID는 서로 달라야 하고, 설정된 Pack 중 하나가 선언해야 한다(scaffold 시 검사).
4. `level` 은 0~3 정수. `llm.default` ∈ {claude, local}. `llm.route` 값 ∈ {claude, local}, 키는 classification 값 또는 경로 glob. `commons.enabled: true` 면 `remote` 필수.
5. `packs` 는 Pack 이름 또는 요구사항 표기(`org.x>=1.0`) 허용, `myelin.core` 필수 포함.
6. 파일은 `dump_config()` 가 생성하며 사람이 편집한다. 재생성 시 사람의 주석은 보존되지 않는다(설정은 데이터이므로 허용) — Vault `CLAUDE.md` 와 `90_System/taxonomy.md` 는 반대로 personal 블록을 보존한다.

## 결과

- `myelin init` 비대화형 플래그 = 위 필드와 1:1. 대화형 마법사도 같은 모델을 채운다.
- `doctor` 의 `domain` 규칙은 `domains.all_ids` 를 "등록된 Domain" 으로 본다.
