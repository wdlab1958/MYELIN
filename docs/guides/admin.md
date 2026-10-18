# 관리자 가이드 — 조직 도입 (Team 모드)

대상: 도입 담당자, Domain 챔피언, 보안 담당. 개인 사용은 [user.md](user.md).

## 1. 원칙 (명세 §9.1)
| 원칙 | 운영에서의 의미 |
|---|---|
| 개인 Vault 불가침 | 관리자는 개인 Vault에 접근하지 않는다. 중앙 서버·수집 에이전트 없음 |
| 공개는 개인의 행위 | Commons에는 작성자가 제안·보내기를 직접 누른 노트만 들어온다 |
| Commons 검토 | Domain 챔피언이 PR에서 비식별을 다시 확인한 뒤 merge |
| 출처 보존 | 공개본에 author · commons_of(원 id) · published |
| 지표는 opt-in 익명 | 구성원이 동의하고, 파일을 보고, 직접 제출 |

## 2. 도입 전 합의 (사람)
1. **지식 소유권** — 업무 노트(회사 자산)와 개인 연구 노트 구분, 퇴사 시 처리.
2. **외부 AI 사용 범위** — 고객 데이터·진단 결과의 Claude 처리 허용 범위 → `llm.route` 기본값·classification 정책.
3. **직무발명** — `40_IP/` 처리 절차, 외부 AI 업로드 금지 범위.
4. 회사 승인 Claude 플랜.
합의 전에는 Commons를 켜지 않습니다 (기본 off). 개인 Vault 사용은 시작할 수 있습니다.

## 3. Commons 저장소
```bash
myelin commons init ~/org-commons --org "우리 조직"
cd ~/org-commons && git remote add origin <조직 내부 git 서버의 비공개 저장소> && git push -u origin HEAD
```
- **공개 호스팅의 public 저장소에 두지 마세요.**
- `policy/deid.yaml`: `deny` 에 고객사·기관명·내부 코드명, `internal_domains` 에 사내 도메인, `allow` 에 오탐 허용(예: 문서용 IP 대역).
  이 파일 자체가 민감할 수 있습니다 — Commons 밖으로 내보내지 마세요.
- `CODEOWNERS` 에 Domain별 챔피언, 브랜치 보호(리뷰 1명 이상)를 git 서버에서 설정.
- 구성원: clone 후 `myelin commons link ~/MyVault ~/org-commons`.

## 4. Pack Registry · Org Pack
- Pack은 **데이터**입니다 (YAML·Markdown). 새 Domain에 코드 변경이 필요하면 설계를 재검토합니다.
- 조직 Pack은 **별도 private 저장소**에서 관리하고 `registry/packs.yaml` 에 등록:
  ```yaml
  registry: 1
  org: 우리 조직
  packs:
    - name: org.security-consulting
      version: 0.2.0
      source: https://git.example.internal/kb/org-packs.git#org.security-consulting
      status: pilot          # draft | pilot | stable | deprecated
      champions: ['@champion']
      domains: [SEC-CONSULT]
  ```
- 템플릿에는 Templater 표현식 중 `tp.date.now`·`tp.date.today`·`tp.file.title` 만 쓸 수 있습니다.
  `<%* %>`·`tp.user`·`tp.system`·`tp.web` 는 Pack 검증에서 거부됩니다 (임의 코드 실행 방지).
- 예시: 공개 저장소의 `packs/org.security-consulting`, `packs/org.incident-response`.

## 5. 배포
- 구성원 설치: [install.md](install.md) — `install.sh` 는 홈 폴더에만 설치하고 sudo를 쓰지 않습니다.
- 버전 고정: `install.sh --ref v1.0.0`. 사내 미러: `MYELIN_REPO=<내부 미러 URL>`.
- 오프라인·폐쇄망: uv 캐시와 npm 캐시를 미리 채운 뒤 `--source <내부 미러>`.

## 6. 파일럿 · 지표
- 운영 절차: [docs/pilot/guide.md](../pilot/guide.md), 60분 워크숍: [docs/pilot/workshop.md](../pilot/workshop.md).
- 조직 지표(명세 §11.2)는 구성원이 제출한 `myelin metrics` 파일을 집계합니다. 구간화된 숫자뿐이므로 개인 비교에 쓰지 마세요.

## 7. 보안 점검
- 위협 모델: [docs/security/threat-model.md](../security/threat-model.md) — High 0.
- 정기: `make gate P=8`, `uvx pip-audit`, `npm audit --omit=dev`.
- 사고 대응: 공개되지 말아야 할 노트가 Commons에 merge 되었다면 → 해당 commit revert + 이력 정리(git 서버 정책), 작성자에게 원본 classification 확인 요청, `policy/deid.yaml` 에 금지어 추가.
