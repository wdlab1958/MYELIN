# ADR-0012: 노트 myelin 강도(strength)·재사용 지표·Commons 인용 모델

- 상태: Accepted · 일자: 2026-10-18 · Phase: P9
- 근거: 정본 §1 "반복해서 연결·재사용할수록 그 지식 경로가 빨라진다(쓸수록 빨라지는 지식 신경망)", §9.1 "재사용 시 인용 링크로 기여가 보이게", §11.1 개인 지표, §11.2 조직 지표 "재사용 — Commons 노트가 타인 노트에 인용된 횟수 ≥ 50/월"(미구현이었음), ADR-0010 Commons 정책.
- 선행: 지금까지 시스템이 측정하는 것은 `verified` 여부(이진 링)와 수량 KPI 뿐이었다. 재사용·속도는 측정되지 않았고, Commons 기여는 평판으로 집계되지 않았다. 이 ADR 은 그 간극을 정의로 메운다.

## 결정

### 1. 노트별 myelin 강도 (strength 0..3)

노트는 **검증(verified)** 되는 순간이 아니라 **재사용될수록** myelinated 된다. 각 노트에 대해 색인(`VaultIndex.reuse()`)과 전수 스캔(`compute_stats`)이 **같은 함수** `myelin_core.stats.compute_reuse()` 로 다음 계수를 구한다.

| 계수 | 정의 |
|---|---|
| `inbound` | 이 노트를 본문 wikilink 로 가리키는 **서로 다른 노트 수**. 링크 대상은 파일 stem · H1 제목 · 노트 id 로 해석한다(고아 노트 비율과 같은 해석 규칙 + 제목/id). 자기 링크는 세지 않는다. |
| `output_uses` | `80_Outputs/` 아래 노트 중 이 노트를 frontmatter `source:` 항목(`[[…]]`, 노트 id, 원문자열) 또는 본문 링크로 참조하는 **서로 다른 산출물 수**. |
| `commons_cited` | 이 노트의 Commons 사본(`published_from == id`)이 **타인에게 인용된 횟수**(§3). Commons clone 이 설정되지 않으면 0. |

강도는 상수(`stats.py` 의 `STRENGTH*`)로 고정한다.

| strength | 조건 | 뜻 |
|---|---|---|
| 0 | `status != verified` | 아직 myelinated 아님 — 재사용이 많아도 검증 없이는 0 (fail-closed) |
| 1 | verified | 검증됨 |
| 2 | verified ∧ (`inbound ≥ 2` ∨ `output_uses ≥ 1`) | **재사용됨(reused)** |
| 3 | verified ∧ (`commons_cited ≥ 1` ∨ (`inbound ≥ 5` ∧ `output_uses ≥ 2`)) | 허브(hub) — 조직이 쓰거나, 내 신경망의 교차점 |

- 노출: `/api/notes`, `/api/search`, `/api/notes/{ref}` 행에 `inbound · output_uses · commons_cited · strength` 를 추가한다(기존 키 유지). Hub 의 My Domains 노트 표·검색 결과 표는 **텍스트 라벨**("myelin ×N", 0 은 "—") 칩으로 표시한다 — 색만으로 상태를 말하지 않는다(§8.3 가드레일). Dashboard 는 강도 1/2/3 별 노트 수와 "verified 중 재사용된 비율" 카드를 보인다.
- Obsidian 테마의 `cssclasses: mx-strength-N` 은 이번에 넣지 않는다(토큰 생성물 golden 과의 drift 위험; 필요 시 별도 ADR).

### 2. 속도·재사용 KPI (정본 §11.1 보강)

`TARGETS`/`BOUNDS` 에 셋을 추가하고 `/api/stats.kpi`, `myelin stats`, Hub Dashboard, 익명 지표 페이로드에 노출한다. 값이 없으면 `None`("-", 판정 없음).

| KPI | 정의 | 목표 |
|---|---|---|
| `reuse_ratio` | strength ≥ 2 인 verified 노트 수 / verified 노트 수 | ≥ 0.30 |
| `reuse_lag_days` | 모든 (산출물, 출처 노트) 쌍에 대해 `산출물.created − 출처.created` 일수의 **중앙값**. 산출물 또는 해석되는 출처가 없으면 None | ≤ 30 |
| `compose_sources_avg` | 산출물(`80_Outputs/**`) 1건당 **verified** 출처 노트 수의 평균 | ≥ 3 |

`Stats` 에는 `by_strength` 히스토그램(`"0".."3"` → 노트 수)도 함께 담는다. `kpi_rows()` 의 튜플 형식은 유지한다.

### 3. Commons 인용 모델 ("기여가 평판이 된다")

Commons 노트는 `published_from`(원 id)·`author`(실명, 공개 필드)를 가진다(ADR-0010 §5). 인용은 두 층에서 셈한다.

1. **개인 Vault → Commons 노트 인용** (`commons.commons_citations(vault, clone)`): clone 의 `notes/**/*.md` 각 노트에 대해, 이 Vault 의 노트 중 그 노트의 **제목을 wikilink** 하거나 `source:` 에 그 **id/제목**을 적은 노트 수. 원 노트가 이 Vault 에 있는 것(내가 공개한 것)은 제외한다 — §11.2 의 정의는 "**타인** 노트에 인용된 횟수"다. 결과는 익명 지표 페이로드의 `cited_commons_ids` 로 보고한다. **id 만** 보내며 제목·경로는 보내지 않는다(`payload_is_anonymous()` 가 id 패턴이 아닌 항목을 거부한다; 이 키가 유일하게 허용되는 리스트 값이다).
2. **조직 집계** (`commons.commons_reuse(clone)`): 원 id → 인용 수. (a) `metrics/<owner>/*.json` 의 `cited_commons_ids` 를 **인용 소유자당 1회**(주간 파일이 반복되어도 중복 계산하지 않음)로 합산 — 호출자 자신의 보고는 `exclude_owner` 로 제외 — (b) clone 안의 다른 Commons 노트가 인용한 수를 더한다. 이 값이 각 노트의 `commons_cited` 가 되고, `metrics.aggregate()` 의 주간 표에는 `reuse` 열(그 주 보고된 인용 총합), `metrics.aggregate_reuse()` 에는 노트별 `reuse`·`reuse_total`·`top_contributors = [{author, published, cited}]` 가 담긴다. `author` 는 설계상 실명인 Commons 공개 필드이며 익명 페이로드에는 들어가지 않는다.

- `/api/commons/candidates` 행에 `published`(이미 Commons 에 있음)·`cited`(그 사본의 인용 수, 미공개면 0) 를, `/api/vault.commons` 에 `published_count`·`cited_total` 을 추가한다.
- `myelin metrics aggregate` 표는 주간 행만 출력하므로 `reuse` 열을 그대로 집어 올 수 있다; 기여자 표(`top_contributors`)는 CLI 가 `aggregate_reuse()` 를 호출해 출력해야 한다(myelin-cli 측 후속 작업).

### 4. Hub Commons 제안 → PR 까지 (정본 §9.1, gap M9)

`POST /api/commons/publish/{ref}` 본문 `{confirmed, push, pr}`. 커밋은 항상 1개(`publish/<id>` 브랜치). push·PR 은 커밋 **이후의 best effort** 다.

- clone 에 `origin` 이 없으면 `myelin.yaml commons.remote` 를 origin 으로 추가한 뒤 push 한다(`commons.ensure_origin`).
- push 실패(origin 없음·네트워크·인증)나 `gh` 부재는 500 이 아니라 **200** 으로 `pushed:false` / `pr_url:null` 과 `push_error` / `pr_error`, 그리고 사람이 할 다음 단계를 한국어로 적은 `next_step`(정확한 `git push -u origin …` / `gh pr create --fill --head …` 명령) 을 돌려준다. 커밋은 어떤 경우에도 잃지 않는다.
- 응답 키 `branch, commit, dest, pushed, pr_url` 은 유지하고 `push_error, pr_error, next_step` 을 더한다. PR 이 열리면 `next_step` 은 `null`.

## 결과
- 측정 대상이 "검증됐는가"에서 "검증되고 **쓰이는가**"로 넓어진다. Dashboard 의 재사용 비율·강도 분포가 §1 의 철학을 숫자로 보인다.
- 정본 §11.2 "재사용 ≥ 50/월" 이 처음으로 계측된다(`aggregate()[week]["reuse"]`).
- 익명 지표 페이로드 허용 키 4개 추가: `reuse_ratio, reuse_lag_days, compose_sources_avg, cited_commons_ids`(ADR-0010 §7 보강). 개인 식별·제목·경로 금지 원칙은 그대로다.
- 임계값(`STRENGTH2_*`, `STRENGTH3_*`, BOUNDS)은 3개월 파일럿 뒤 재조정 대상이다 — 바꾸면 이 ADR 을 개정한다.
