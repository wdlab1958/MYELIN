# 두 구현 비교 — GitHub `main`(Fable 세션) vs `opus-v1.0-2026-10-18`(이 세션)

- 일자: 2026-10-18
- 배경: 같은 명세(Rev 2.0)로 두 Claude 세션이 각각 P0~P8을 구현했다. 두 이력에는 공통 조상이 없다.
  - 10:39에 `main` 이 Fable 세션의 이력으로 바뀌었다.
  - 이 세션의 이력은 브랜치로 보존되어 있다.
- 결정: Brian. 이 문서는 사실 비교다. 아래 확인 방법은 다음과 같다.
  - Fable `main` 은 실제로 checkout 해 테스트를 돌렸다.
  - 보안 항목은 코드를 직접 읽고 확인했다.

## 1. 브랜치
| 브랜치 | 내용 |
|---|---|
| `main` (db938b6) | Fable 5.1 세션 — 78 커밋, v1.0.0 태그 주장 |
| `fable-v1.0` (4da023c) | Fable 이력의 다른 끝 |
| `main-alt-2026-10-18` (4a24b14) | 이 세션의 P7까지 (Fable 세션이 보존) |
| `opus-v1.0-2026-10-18` (최신) | 이 세션의 P8까지 — 이 문서 포함 |

## 2. 상태
| | main (Fable) | opus (이 세션) |
|---|---|---|
| 테스트 | 406 passed, 1 skipped (직접 실행) | 481 passed (Playwright e2e 포함) |
| P7 사람 항목 | 열림 | 열림 (PEND) |
| P8 상표 | "KIPRIS 직접 조회 필요"라고 적었으나 `v1.0.0` 태그를 주장 | 사람 검토 전까지 Gate PEND, 태그 보류 |
| 조직 Pack | **`a3.security-consulting`, `a3.incident-response`** (공개 저장소) | `org.*` Example Org만 — 앞서 정한 "중립화 후 공개" 원칙대로 |

## 3. 보안 — 코드로 확인한 차이
| 항목 | main (Fable) | opus (이 세션) |
|---|---|---|
| Hub 바인딩 | loopback만 | loopback만 |
| Host·Origin 검사 | 있음. 단 `testserver` 가 운영 허용 목록에 들어 있고, Origin이 없는 POST는 통과 | 있음. POST는 의도 헤더·같은 출처 Origin·JSON이 모두 필수 |
| **세션 토큰** (같은 PC의 다른 사용자·프로세스) | 없음 — 127.0.0.1 포트에 접속하면 노트 GET 가능 | 실행마다 임의 토큰 → HttpOnly·SameSite=Strict 쿠키, `/api` 401 |
| **Pack 템플릿 코드 실행** (Templater `<%* %>`, `tp.user`) | 검사 없음 | 허용 목록만, 위반 Pack 거부 |
| **승격 commit 범위** | `git commit -m …` 에 경로를 지정하지 않음 → 사용자가 따로 stage해 둔 변경까지 Hub commit에 섞인다 | `git commit -- <바뀐 경로>` + `GIT_LITERAL_PATHSPECS` |
| **commit 실패 시** | 파일은 이미 옮겨진 채 500 오류 → Vault가 반쯤 바뀐 상태로 남음 | 파일 원복 + stage 원복 |
| **이동 대상이 심볼릭 링크** | `dest.exists()` 만 확인 → 깨진 링크를 따라 Vault 밖에 쓸 수 있음 | 경로 구성요소 링크 검사 + `O_EXCL|O_NOFOLLOW` |
| 승격 시 화면-파일 일치 | 경로만 받음 | 화면에 표시한 id를 함께 보내야 함 (보지 않은 노트 승격 방지) |
| 본문 보존 | 파서를 거쳐 다시 씀 | 원문 바이트 유지 (CRLF·BOM), 독립 검토 6건 반영 |
| git 설정 | Vault `.git/config` 에 `MYELIN Hub` 이름을 영구 기록 | 설정이 없을 때만 그 commit에 `-c` 로 Vault 주인 이름 |
| 승격 시 origin | `claude → mixed` 로 바꿈 | `claude` 유지 (승격률 지표의 근거) — 명세 해석 차이 |
| Commons 공개 | 확인 체크 + push가 한 요청에 가능 | 제안(로컬 브랜치)과 보내기(push)가 분리된 두 번의 확인 |
| 지표 제출 | `metrics send` — Commons clone에 기록 (사용자 확인) | 파일로만 내보내고 사람이 직접 제출 |

## 4. main에만 있는 기능 (opus에 없음)
- Hub에서 `_patches` 적용·반려 (링크 제안 patch 처리)
- `pack-propose`, `metrics aggregate`, 온보딩·첫 승격 이벤트 기록
- `install.sh` 가 플러그인 마켓플레이스·MCP·Obsidian 테마까지 설정, `CHANGELOG.md`, `make install/ttfv`
- 인덱스 기반 통계, `expose_confidential` MCP 정책 블록

## 5. 선택지
| 안 | 내용 | 비용 |
|---|---|---|
| A. opus를 main으로 | 보안 차이 6건이 해결된 상태에서 출발. main에만 있는 기능(4절)은 필요하면 옮긴다 | main 강제 교체 (Fable 이력은 브랜치로 남음). Fable이 붙인 태그 정리 |
| B. main 유지 | Fable 이력을 정본으로. 3절의 보안 수정 6건과 A3 중립화를 main에 PR로 옮긴다 | 수정을 다른 코드 구조에 다시 구현하고 테스트도 다시 써야 함 |
| C. 보류 | 두 브랜치를 그대로 두고 파일럿·상표 확인부터 | 공개 main에 A3 Pack이 계속 노출된 상태 |

**급한 것:** 어느 안이든 공개 `main` 의 A3 Pack·문서를 빨리 중립화해야 한다.
- 이미 공개된 이력에는 계속 남는다. 민감하다면 저장소 이력 정리(force push, GitHub 지원 요청)를 따로 검토해야 한다.
