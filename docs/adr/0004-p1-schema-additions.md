# ADR-0004: P1 스키마 보강 (명세 §5.2 · §6.2 대비)

- 상태: Accepted
- 일자: 2026-10-18
- Phase: P1

## 맥락
명세 Rev 2.0의 Pack·frontmatter 스키마를 구현하면서, 명세가 정하지 않았거나 모호한 부분을 확정해야 했다.
CLAUDE.md 규칙상 스키마 추가는 ADR로 남긴다.

## 결정
| # | 항목 | 결정 | 이유 |
|---|---|---|---|
| 1 | Domain ID | 설명적 ID(`EMBEDDED-SW`) + 선택 필드 **`label`**(≤6자, 예: `D2`) | `D1`~`D4` 같은 짧은 ID는 여러 Pack을 함께 쓸 때 충돌한다. 화면(Domain Orb)에는 `label` 을 쓴다 |
| 2 | Domain ID 형식 | `^[A-Z][A-Z0-9]*(-[A-Z0-9]+)*$`, ≤32자 | frontmatter `domain` 과 같은 규칙. 기존 `D2` 형식도 유효 |
| 3 | `accent` | `violet · cyan · lime · magenta` + **`amber · slate`** | Domain이 4개를 넘으면 색이 부족하다. 토큰 값은 P5에서 정의 |
| 4 | Pack 매니페스트 | 알 수 없는 필드 = 오류 (`extra=forbid`) | Pack은 배포물이므로 오타를 조용히 무시하면 안 된다 (fail-closed) |
| 5 | Frontmatter | 알 수 없는 필드 보존 (`extra=allow`) | 사용자 Vault에는 Obsidian·다른 플러그인 필드가 섞인다. lesson의 `era` 도 여기 해당 |
| 6 | Taxonomy·Interview 파일 | `TaxonomyFile{terms[]}`, `InterviewBank{domains: {ID: [Question]}}` 스키마 신설 | 명세는 파일만 언급. P3 `/interview` 와 P2 taxonomy 렌더링의 입력 계약 |
| 7 | Interview bank 검사 | 도메인이 bank를 참조하면 그 bank에 해당 Domain 질문이 1개 이상 있어야 함 | 빈 인터뷰 방지 |
| 8 | 참조 경로 | Pack 내부 상대경로만. `..`·절대경로·심볼릭 링크 탈출 금지 | Pack은 외부에서 받는 데이터다 |
| 9 | Pack 디렉터리명 | 디렉터리명 = `pack` 이름 | Registry(P7)에서 이름으로 찾기 위함 |
| 10 | 노트 템플릿 | 9종 (노트 유형 수와 일치, `checklist` 포함) | P1 계획서의 "8종"은 Rev 1.0 기준이었음 |
| 11 | `reviewed` | `created` 보다 이를 수 없음 | 명백한 입력 오류 차단 |
| 12 | Pack 버전 | 엄격한 `MAJOR.MINOR.PATCH`, `requires` 는 `>= > <= < == !=` 와 `,` 조합 | 외부 의존성 없이 필요한 만큼만 |

## 결과
- `schemas/*.json` 4종이 모델에서 생성되며, Gate가 일치 여부를 검사한다.
- 템플릿의 `tp.user.slug` 는 Templater 사용자 스크립트가 필요하다 → P2에서 제공하거나 `init` 이 id를 직접 렌더링한다.
