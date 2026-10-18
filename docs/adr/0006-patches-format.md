# ADR-0006: `_patches/` 제안 파일 형식

- 상태: Accepted · 일자: 2026-10-18 · Phase: P3
- 근거: 정본 §3 HITL Oversight, §4.2 "/link (patch 제안 → 사람 승인)", §6.1 `_patches/`, §7.1 /link 쓰기 범위

## 결정

- 파일: `_patches/<YYYYMMDD-HHMM>-<slug>.patch.md`. `_patches/` 는 노트 스캔(doctor/stats/색인)에서 제외된다.
- Frontmatter(미지 필드 금지):

| 필드 | 값 |
|---|---|
| `patch` | `1` (형식 버전) |
| `target` | Vault 상대경로(`..`·절대경로·`_patches/` 내부 금지) |
| `kind` | `append` \| `replace` \| `frontmatter` |
| `origin` | `claude` \| `human` \| `mixed` |
| `skill` | 제안한 Skill 이름(`link`, `review` …) |
| `created` | 날짜 |
| `rationale` | 한 줄 근거(필수) |
| `status` | `proposed` → `approved` \| `rejected` → `applied` (Hub 가 바꾼다) |

- 본문 섹션: `append` → `## append`; `replace` → `## before`(대상에 정확히 1회 존재) + `## after`; `frontmatter` → `## set`(`key: value` 줄). 필수 섹션은 비어 있을 수 없다.
- **적용은 사람만**: Hub Review Gate(P6)가 approved 로 바꾸고 적용 후 Git commit(`[myelin:link] apply patch …`). CLI/Skill 은 적용 기능을 갖지 않는다.
- 파서/모델: `myelin_core.patches` (`parse_patch`, `read_patch`). 잘못된 patch 는 `PatchError`.

## 대안
- unified diff 만 사용: 사람이 Hub 에서 읽기 어렵고 MOC 같은 리스트 파일에 과하다. `replace` 가 필요할 때만 before/after 를 쓴다.

## 보강 (2026-10-18, Desktop 라인 P9 이식)
- `append` 에 선택 필드 `under`(제목 텍스트) 추가 — 그 제목 구획 끝에 붙인다. 제목이 없으면 거부.
- `frontmatter` 의 `## set` 은 허용 키 집합 `tags·source·projects·aliases·confidence` 만. status·origin·id·reviewed·classification·share 는 Review Gate 전용.
- **적용은 계획(plan) → 검사 → diff 미리보기 → digest 확인 → 적용** 순서. plan 의 fail-closed 규칙: 대상이 Vault 안 유효 노트, `40_IP/` 밖, confidential 아님, verified 노트에 미검증 AI 노트 링크 추가 금지, 결과 frontmatter 유효.
- Hub 는 미리보기 시 patch 파일의 digest(sha256 앞 16자)를 돌려주고, Apply 요청은 같은 digest 를 보내야 한다(화면과 파일이 달라지면 409).
- 적용/거부된 patch 는 `_patches/applied/`·`_patches/rejected/` 로 이동(status 갱신)해 제안 이력을 Vault 에 남긴다.
