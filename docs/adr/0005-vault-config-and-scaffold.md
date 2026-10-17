# ADR-0005: Vault 설정·생성·위치 정책

- 상태: Accepted
- 일자: 2026-10-18
- Phase: P2

## 맥락
P2는 실제 사용자 Vault를 만들고 고친다. 사용자 데이터를 다루는 첫 Phase이므로
설정 파일 형식, 파일을 쓰는 규칙, Vault를 둘 수 있는 위치를 확정한다.
또한 저장소가 public으로 전환되면서(2026-10-18), 개인 노트가 공개 저장소로 새는 경로를 막아야 한다.

## 결정

### 1. `myelin.yaml` 스키마 (명세 §5.3 확정)
- `myelin: 1`(설정 스키마 버전), `owner{name, team?, email?}`, `language`, `packs[]`(myelin.core 필수),
  `domains{primary, research?, growth?, extra[≤1]}`, `level 0~3`, `llm{default, route}`, `commons{enabled, remote}`.
- 알 수 없는 필드는 오류. 한 Domain은 한 역할만.
- **3+1 규칙**을 스키마로 강제: `extra` 는 최대 1개. 이미 찬 역할에 `add-domain` 하면 거부.
- 명세 예시의 `owner.team`·`email` 은 선택 필드.

### 2. `90_System/myelin.lock.yaml`
- 설치된 Pack·Domain(id, label, name, accent)의 스냅샷. init·add-domain이 생성하는 **시스템 파일**.
- doctor·stats는 Pack 소스 없이 lock만으로 Domain을 안다 → 오프라인·이동한 Vault에서도 동작.

### 3. 파일 쓰기 규칙
| 대상 | 규칙 |
|---|---|
| 노트 (`00_Inbox`~`99_Archive`) | **절대 수정하지 않음.** 새 파일만 만들고, 이름이 겹치면 전체 작업 중단 |
| `myelin.yaml` | ruamel round-trip으로 사용자의 주석·순서·들여쓰기 보존. 결과를 다시 검증한 뒤 씀 |
| `myelin.lock.yaml` | 전체 재생성 (사용자가 고치지 않는 파일) |
| `taxonomy.md`, `interviews.md` | 끝에 절을 **덧붙이기만** 함 (사용자 편집 보존) |
| Vault `CLAUDE.md` | `<!-- myelin:generated:start/end -->` 구간만 교체. 마커가 없으면 건드리지 않음 |

모든 작업은 plan → apply 2단계이며, apply는 충돌이 하나라도 있으면 **아무것도 쓰지 않는다**.

### 4. 템플릿 id (ADR-0004 후속)
- `tp.user.slug` (Templater 사용자 스크립트 필요)를 버리고 내장 함수만 쓴다:
  `id: <% tp.date.now("YYYYMMDD-HHmm-ssSSS") %>` → 예: `20261018-0712-45123` (스키마 패턴 일치).
- 한글 제목에서도 동작하고 추가 설정이 없다. id는 불변 식별자일 뿐 의미를 담지 않는다.
- myelin.core 1.0.0 → **1.1.0**, org.security-consulting 0.1.0 → 0.1.1.
- 확인 필요: 실제 Obsidian + Templater에서 생성되는지 (P5/P6 수동 점검 항목).

### 5. Vault 위치 (개인정보 보호, P2-T10)
- `init` 거부: MYELIN 소스 폴더 안, 다른 git 저장소 안, 비어 있지 않은 폴더, 파일 경로.
- `doctor` 위치 규칙: 소스 폴더 안 = error / 다른 git 안 = warning / 공개 호스팅 원격 = warning.
  (원격 저장소가 실제로 비공개인지는 네트워크 없이 알 수 없으므로 확인을 요청하는 경고로 둔다.)
- 저장소 안의 테스트 fixture Vault는 `--no-location` / `check_location=False` 로 검사한다.

### 6. doctor 범위
- 검사 대상은 내용 폴더(`00_Inbox`…`99_Archive`)의 `.md` 만. `90_System`(템플릿에는 Templater 문법이 있어 frontmatter가 유효하지 않다), `_patches`, 숨김 폴더는 제외.
- 고아 검사 제외: MOC, fleeting, Inbox 노트. 링크 해석은 파일명 또는 Vault 상대경로, 같은 이름이 여럿이면 가장 짧은 경로.
- error가 있으면 exit 1, `--strict` 이면 warning도 exit 1.

## 결과
- golden snapshot(`tests/fixtures/vaults/golden/brian`)은 CLI를 임시 폴더에서 실행해 만든다 — Vault를 소스 안에 직접 만들 수 없기 때문.
- 내장 Pack 경로 탐색: `--packs` → `$MYELIN_PACKS` → 패키지 내장 `_packs` → 소스 트리. 휠에 Pack을 넣는 패키징은 P8에서.
