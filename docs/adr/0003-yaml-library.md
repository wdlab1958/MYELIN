# ADR-0003: YAML 라이브러리 — ruamel.yaml

- 상태: Accepted
- 일자: 2026-10-18
- Phase: P1

## 맥락
MYELIN은 YAML을 두 곳에서 읽는다: 노트 frontmatter, Domain Pack(`pack.yaml`, taxonomy, interview bank).
P2(`add-domain`)와 P6(Hub Pack 편집기)에서는 사용자가 쓴 YAML을 **주석과 순서를 보존한 채** 수정해야 한다.

## 선택지
| | PyYAML | ruamel.yaml |
|---|---|---|
| YAML 버전 | 1.1 — `no`, `on`, `off` 가 boolean으로 바뀜 (예: 국가코드 `NO` → `False`) | 1.2 — 예측 가능한 스칼라 해석 |
| 주석·순서 보존 쓰기 | 불가 | round-trip 지원 |
| 안전 로딩 | `safe_load` | `YAML(typ="safe")` |
| 타입 정보 | 별도 stub | 패키지 내장 (`py.typed`) |

## 결정
- **ruamel.yaml** 을 사용한다.
- 읽기는 항상 `YAML(typ="safe", pure=True)` — 임의 객체 생성 금지. 중복 키는 오류로 처리한다.
- 쓰기(P2 이후)는 `typ="rt"` round-trip으로 사용자 파일의 주석·순서를 보존한다.
- YAML 문법 오류는 `loc` 에 `파일명:줄:열` 을 담은 구조화 오류로 변환한다.

## 결과
- frontmatter의 날짜는 YAML timestamp 또는 문자열 모두 Pydantic이 `date` 로 정규화한다.
- 의존성 1개 추가 (`ruamel.yaml>=0.18`).
