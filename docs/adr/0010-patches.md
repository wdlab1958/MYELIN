# ADR-0010: 구조화 patch — Claude가 제안하고 사람이 Hub에서 적용

- 상태: Accepted
- 일자: 2026-10-18
- Phase: P9 (Claude Desktop 구현의 `_patches` 적용 기능 이식)

## 맥락
`/myelin:link`(Level 2)는 사람 영역 노트(MOC 등)를 직접 고치지 못하고 `_patches/` 에 제안만 쓴다 (ADR-0002).
P3~P8에서는 제안이 자유 형식 체크리스트라 사람이 손으로 옮겨야 했다.
Claude Desktop 구현은 구조화 patch와 Hub 적용 기능을 갖고 있었다 → 형식을 받아들이되 안전 검사를 더해 옮긴다.

## 결정
- 형식: `_patches/<YYYYMMDD-HHMM>-<slug>.patch.md`, YAML frontmatter(`patch: 1`, `target`, `kind`, `under`?, `origin`,
  `skill`, `created`, `rationale`, `status`) + 구획(`## append` | `## before`·`## after` | `## set`). 알 수 없는 키는 오류.
- **대상 하나 = patch 하나.** 대상은 지식 노트(내용 폴더 `.md`)만. Vault 밖·심볼릭 링크·`40_IP/`·confidential 은 거부.
- `append`: 대상 끝, 또는 `under` 제목 구획의 끝(제목은 정확히 한 번 있어야 함).
  `replace`: `before` 가 본문에 정확히 한 번. `frontmatter`: `tags·source·projects·aliases·confidence` 만 —
  `status·origin·id·reviewed·classification·share` 는 Review Gate·사람의 몫이라 patch로 못 바꾼다.
- 적용 결과가 노트 스키마를 통과해야 하고 id가 같아야 한다. **verified 노트가 미검증 AI 노트를 새로 링크하게 되면 거부.**
  없는 노트로 가는 링크는 경고로 보여 준다.
- 원문 줄바꿈(CRLF)·BOM을 유지하고, 바뀐 부분 외에는 바이트 그대로.
- Hub Review Gate의 Patches 목록에서 diff를 보고 **사람이 클릭**해야 적용·반려된다 (ADR-0008 쓰기 규칙 그대로).
  적용·반려는 git commit으로 남고, patch 파일은 지우지 않고 `_patches/applied/`·`_patches/rejected/` 로 옮겨
  `status`·`decided` 를 기록한다. commit이 실패하면 파일을 되돌린다.
- 자유 형식(구조화 아님) patch는 목록에 "수동"으로 표시되고, 반려(보관)만 할 수 있다.

## 결과
- MOC 갱신 같은 반복 작업이 "diff 보고 한 번 클릭"이 된다. 사람 영역 쓰기는 여전히 사람의 클릭뿐이다.
- `/link` 스킬 출력 계약을 구조화 형식으로 바꿨다. 계약 테스트가 Guard·doctor·patch 파서·적용 계획을 모두 통과하는지 확인한다.
