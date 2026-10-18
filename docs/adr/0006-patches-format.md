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
