# ADR-0009: Team Commons · 비식별 · opt-in 익명 지표

- 상태: Accepted (조직 정책 3종 합의 전 — 가장 보수적인 기본값)
- 일자: 2026-10-18
- Phase: P7

## 맥락
명세 §9.1: 개인 Vault 불가침, 공개는 개인의 행위, 챔피언 PR 검토, 출처 보존, 지표는 opt-in 익명.
P7 프롬프트: "개인 Vault 내용을 외부로 보내는 모든 경로는 사용자 확인 단계를 거치게 하라."
§9.1의 사전 합의 정책(지식 소유권·외부 AI 사용 범위·직무발명)은 아직 합의되지 않았다 → 기본값은 가장 닫힌 쪽.

## 결정

### 1. 설정 스키마 (`myelin.yaml`)
- `commons.path` 추가 — Commons 저장소의 **로컬 clone** (절대경로, Vault와 서로 포함 관계 금지). `enabled` 기본 `false`.
- `metrics.opt_in` 추가 — 기본 `false`.
- `render_config` 는 새 키를 쓰지 않는다 (기본값) → 기존 Vault·golden snapshot 불변. 켜는 방법: `myelin commons link`, Hub Settings.

### 2. Commons 저장소 (`myelin commons init <dir> --org`)
`notes/<DOMAIN>/` · `registry/packs.yaml`(Pack Registry, 스키마 검증) · `policy/deid.yaml`(금지어·허용 목록·내부 도메인) ·
`CONTRIBUTING.md` · GitHub/GitLab PR 템플릿(사람 확인 체크리스트) · `CODEOWNERS`(챔피언). Vault·MYELIN 소스 안에는 만들지 않는다.
조직 내부 git 서버의 비공개 저장소로 쓴다 — 공개 저장소에는 Example Org 템플릿만.

### 3. 공개 자격 — 하나라도 어기면 차단 (fail-closed)
`status: verified` · `share: true` · `classification ∈ {public, internal}` · `40_IP/` 아님 · `llm.route` 로컬 전용 경로 아님 ·
type이 moc/fleeting/idea-ip 아님 · Commons 켜짐·연결 정상 · 같은 브랜치/같은 파일 없음.
Gate는 status(4) × share(2) × classification(3) × 위치(2) = 48 조합 전부와 type·꺼짐·라우팅 경우를 검사한다.

### 4. 비식별 자동 검사 (`myelin_core.deid`)
이메일 · IPv4/IPv6 · 전화 · 주민/외국인등록번호 · 카드(Luhn) · 개인키 · 클라우드 키 · 토큰 · `password=` 류 ·
내부 URL(.local/.internal/.corp 등 + 정책의 내부 도메인) · 정책 금지어(고객명). **찾으면 모두 차단** — 경고로 넘기지 않는다.
오탐은 Commons의 `policy/deid.yaml` `allow` 로만 푼다(챔피언 관리). 화면에는 찾은 값을 가려서 보여 준다.
자동 검사는 사람 검토를 대신하지 않는다 → 아래 사람 확인 5항목.

### 5. 공개 흐름 — 사람 행위 3번
1. **제안**: 작성자가 확인 5항목(고객명·기밀·개인정보·직무발명·공개 동의)을 모두 체크 → Commons clone에 `publish/<id>` 브랜치 commit.
   - 임시 index + `commit-tree` + `update-ref`(없을 때만) — 사용자의 Commons 작업 트리·index·현재 브랜치를 건드리지 않는다.
   - **Vault 파일은 바뀌지 않는다.**
   - 공개본: `share`·`source`·`projects` 제거(개인 Vault 구조 노출 방지), `title`·`author`·`commons_of`(원 id)·`published` 추가.
2. **보내기**: 별도 버튼 + 확인(`confirm: true`) → `git push -u origin publish/<id>`. Vault 내용이 기기 밖으로 나가는 **유일한** 경로.
   MYELIN은 PR을 직접 만들지 않는다 — git 호스트가 push 결과로 PR 링크를 준다(호스트 API 토큰을 다루지 않음).
3. **merge**: 챔피언이 PR에서 비식별을 다시 확인한 뒤 merge (MYELIN 밖).

### 6. opt-in 익명 지표 (`myelin metrics`)
- `metrics.opt_in: true` 일 때만 만든다. **파일로만 내보내고 네트워크로 보내지 않는다** — 사람이 내용을 보고 직접 제출.
- 담는 것: ISO 주, Level, core·org Pack 이름, Domain 수, 구간화한 개수(0·1-4·5-9·…·1000+), 비율(소수 1자리), 켜짐 여부.
- 담지 않는 것: 이름·이메일·경로·제목·노트 id·Domain id·태그·날짜·reference/개인 Pack 이름(사람을 가리킬 수 있음).

## 결과
- 공개 경로마다 사람 확인이 있고, 자동 검사는 차단만 한다.
- 정책 3종 합의 후 바뀔 수 있는 것: `llm.route` 기본값, 공개 가능 classification, 금지어 목록, 직무발명 항목 문구.
