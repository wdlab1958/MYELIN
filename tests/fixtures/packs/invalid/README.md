# Invalid Pack fixtures (P1 Gate: 잘못된 Pack 10종 fixture 모두 명확한 오류 메시지)

| # | 디렉터리 (= pack 이름) | 기대 오류 (부분 문자열) |
|---|---|---|
| 01 | me.missing-pack-file | `pack.yaml not found` |
| 02 | me.bad-yaml | `invalid YAML` |
| 03 | me.empty-file | `file is empty` |
| 04 | me.unknown-field | `sub_moc: unknown field` |
| 05 | me.name-mismatch | `must match its directory name` |
| 06 | me.bad-accent | `accent 'amber' is not an Emboss accent token` |
| 07 | me.no-core | `must require myelin.core` |
| 08 | me.core-with-domains | `core pack must not declare domains` (pack: me.core-with-domains, kind: core) |
| 09 | me.missing-ref | `referenced path 'interviews.yaml' does not exist` |
| 10 | me.empty-templates | `contains no *.md templates` |
| 11 | me.iv-domain | `references domain 'Y' not declared` |
| 12 | me.bad-version | `invalid version 'v1'` |
| 13 | me.dup-domains | `duplicate domain id(s) in pack: ['X']` |
| 14 | me.path-escape | `must be relative and inside the pack directory` |

`packages/myelin-core/tests/test_invalid_packs.py` 가 이 표를 그대로 검증한다. 모든 오류는 `PackError` 이며 메시지에 파일 경로가 포함된다.
