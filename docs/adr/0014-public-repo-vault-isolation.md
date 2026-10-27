# ADR-0014: 공개 저장소와 개인 Vault·로컬 Commons 의 분리 — 코드만 재배포한다

- 상태: Accepted · 일자: 2026-10-27 · Phase: P9 (운영 규칙)
- 근거: Brian 지시(2026-10-27) "Public Project 로 소스코드가 공개되어 있으므로 집과 회사의 로컬 PC 에서 생성된 어떠한 Vault 도 커밋하거나 푸시하지 않는다. 다만 집과 회사에서 업그레이드하거나 패치한 코드는 재배포하여 사용자들에게 제공한다." 정본 §3(정본은 Vault 의 Markdown + Git), §4.4 Personal 모드, ADR-0010 Commons 정책, 위협 모델 T-Commons 유출, `KEY_ROTATION_GUIDE-2026-05-31.md` 의 교훈(히스토리에 남은 비밀은 회수 불가).

## 결정

### 1. 세 종류의 git 저장소를 섞지 않는다
| 저장소 | 위치 | 원격 | 커밋 | push |
|---|---|---|---|---|
| **제품 코드** (공개) | `~/ai_project/MYELIN` | github.com/wdlab1958/MYELIN | 코드·문서·합성 fixture 만 | **한다** — 집·회사의 패치를 `main` 으로 모아 재배포 |
| **개인 Vault** | `~/Vaults/<me>` (집·회사 각각) | **없음** | 제품 런타임이 `[myelin:<skill>]` 로 로컬 커밋 | **금지** |
| **로컬 Commons** | `~/ai_project/MYELIN/Local_Commons` (`myelin commons init`) | 없음 (`commons.enabled: false`) | publish 흐름이 로컬 커밋 | **금지** (조직 Commons 를 쓰기로 결정하면 별도 ADR) |

- 개인 Vault 와 Local Commons 는 **원격을 등록하지 않는다**. 장치로 `.git/hooks/pre-push` 가 모든 push 를 `exit 1` 로 거부한다(집·회사 PC 모두 설치). 누가 원격을 붙이더라도 push 는 실패한다.
- 제품 저장소의 `.gitignore` 는 `Local_Commons/`·`Vaults/` 를 무시한다 — Commons clone 이 저장소 트리 안에 있어도 코드 커밋에 섞이지 않는다.
- Vault 안의 개인 Pack(`<Vault>/packs/me.*`), `myelin.yaml`, 노트, `_patches/` 는 모두 Vault 쪽이다. 공개 저장소의 `packs/` 는 **core·reference Pack 만** 담는다(합성 예시, 개인 Domain 재정의는 Vault 의 `me.my-domains` 로).

### 2. 재배포는 코드 경로 하나뿐이다
- 집 또는 회사에서 고친 코드는 `P{n}: <type>(<scope>)` 커밋 → `git push origin main` → CI green → `CHANGELOG.md` 와 버전(`v1.x.y`) 태그. 사용자는 `git pull && scripts/install.sh --vault <v>` (관리자 가이드 §5) 로 받는다.
- Vault 포맷(Frontmatter v2·`myelin.yaml`)에 영향을 주는 패치는 ADR 선행, `myelin doctor` 로 마이그레이션 검증(기존 규칙 유지).
- 두 PC 사이의 **코드** 동기화는 GitHub `main` 으로만 한다. Vault 는 PC 마다 따로 두고 동기화하지 않는다(필요하면 Commons publish 경로로 노트 단위 공유 — 비식별·사람 확인 필수, ADR-0010).

### 3. 커밋 전 검사 (fail-closed)
- 제품 저장소에 `*.md` 노트처럼 보이는 Frontmatter v2 파일(`id: YYYYMMDD-HHMM-…` + `origin:`)이 `tests/fixtures/`·`docs/` 밖에 들어오면 리뷰에서 거부한다. 개인 Vault 경로(`~/Vaults`, `Local_Commons`)의 파일은 어떤 이유로도 공개 저장소 커밋에 넣지 않는다.
- 비밀·고객 데이터 금지 규칙(CLAUDE.md)은 그대로다. 비밀이 히스토리에 들어가면 회수 불가 → 키 회전으로만 해소된다는 2026-05-31 교훈을 전제로 한다.

## 결과
- 공개 저장소는 "코드 + 합성 데이터" 만 남고, 지식(Vault)은 소유자의 PC 를 떠나지 않는다 — 정본 §4.4 "조직은 Vault 를 열람하지 않는다" 와 일치.
- 집·회사 어느 쪽에서 패치해도 재배포 경로가 하나라 버전이 갈라지지 않는다.
- 대가: Vault 는 PC 간 자동 동기화가 없다. 같은 지식을 두 곳에서 쓰려면 Commons(조직 원격) 결정이 필요하며 그때 별도 ADR 로 다룬다.

## 적용 기록 (2026-10-27)
- `~/Vaults/me/.git/hooks/pre-push`, `Local_Commons/.git/hooks/pre-push` 설치 · 두 저장소 원격 없음 확인.
- `.gitignore` 에 `Local_Commons/`·`Vaults/` 추가. `myelin commons init ~/ai_project/MYELIN/Local_Commons` 실행(`commons.local` 과 일치, `enabled: false` 유지).
- 백로그: `myelin init` / `doctor --install-hook` 가 pre-push 거부 장치도 함께 설치하도록 제품화(테스트 포함) — 다음 패치에서.
