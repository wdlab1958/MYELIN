# MYELIN Commons — 저장소 구조와 Pack Registry 포맷 (P7-T1, ADR-0010)

```
commons/                      # git@git.a3sc.internal:myelin/commons.git (사내)
├── README.md
├── CHAMPIONS.md              # Domain 챔피언 (PR 리뷰어)
├── deid.yaml                 # 공통 비식별 용어/정규식 (각 Vault 의 90_System/deid.yaml 이 보강)
├── registry/
│   ├── index.yaml            # Pack Registry 목록 (아래 포맷)
│   └── packs/<name>/         # Org/Reference Pack 전체 (pack.yaml, taxonomy, interviews, templates)
├── notes/<DOMAIN>/<id>-<slug>.md   # 공개 승인된 Evergreen 노트
├── proposals/packs/<name>/   # 개인 Pack → Org Pack 제안 (+ PROPOSAL.md)
└── metrics/<owner-hash>/<YYYY-Www>.json   # opt-in 익명 지표
```

## registry/index.yaml
```yaml
packs:
  - name: a3.security-consulting
    version: 1.0.0
    kind: org
    maintainer: A3-AI WG
    path: registry/packs/a3.security-consulting
    domains: [SEC-CONSULT]
    champions: []            # 비어 있으면 "초안". 챔피언 이름이 들어가야 확정
    updated: 2026-10-18
```
- `myelin commons add-pack <pack dir> --commons <clone> [--champion 이름]` 이 복사·갱신한다.
- 구성원은 `myelin.yaml packs:` 에 이름만 적고, `MYELIN_PACKS=<clone>/registry/packs` 로 Registry 를 Pack 검색 루트에 넣는다.

## 공개 노트 frontmatter (추가 필드)
| 필드 | 값 |
|---|---|
| `author` | 작성자 이름 (출처 보존) |
| `published_from` | 원 노트 id |
| `published_by` | 익명 해시 `sha256(email|name)[:12]` |
| `published` | 공개일 |

## 브랜치 규약
- 노트: `publish/<note-id>` · Pack 제안: `propose/<pack>` · main 직접 커밋 금지 · merge 는 챔피언.
