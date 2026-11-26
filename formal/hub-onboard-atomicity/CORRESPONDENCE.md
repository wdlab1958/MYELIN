# Correspondence: hub-onboard-atomicity

Spec commit: `c29d83f` + 2026-11-18 패치(F7). 줄 번호는 패치 적용 후 기준. 수정 전 `onboard` 는 `c29d83f` 의 `service.py` 852~906행.

| Model element | Kind | Source (file:line) | Abstraction / Assumption |
|---|---|---|---|
| `pack` | variable | `<Vault>/packs/me.my-domains/pack.yaml` — `packages/myelin-hub/api/src/myelin_hub_api/service.py:1315-1356` | |
| `config` | variable | `<Vault>/myelin.yaml` — `packages/myelin-core/src/myelin_core/scaffold.py:249-274` init_vault() | |
| `scaffold` | variable | welcome 초안·`.myelin/` — `packages/myelin-hub/api/src/myelin_hub_api/service.py:1191-1194`, `packages/myelin-hub/api/src/myelin_hub_api/service.py:1198-1229` | scaffold plan 의 다른 파일은 `config` 와 같은 운명(A2) |
| `repo`, `committed` | variable | `.git/`, `[myelin:init]` — `packages/myelin-hub/api/src/myelin_hub_api/service.py:368-393` ensure_git() | |
| `Start` | action | `packages/myelin-hub/api/src/myelin_hub_api/app.py:530-532` → `packages/myelin-hub/api/src/myelin_hub_api/service.py:1138-1161` (이미 Vault 면 409: 1061-1064) | |
| `WritePack` | action | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1152-1154` → `packages/myelin-hub/api/src/myelin_hub_api/service.py:1315-1356` | `Custom` |
| `InitVault` | action | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1163-1196` (init_vault 1101) | 원자적(A1) |
| `Welcome` | action | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1191-1194` | |
| `GitCommit` | action | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1195` → `packages/myelin-hub/api/src/myelin_hub_api/service.py:368-393` | |
| `Fail` | action (env) | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1157-1161` → `packages/myelin-hub/api/src/myelin_hub_api/service.py:138-214` _OnboardUndo | 어느 단계 뒤에서든 |
| `FullRollback` | constant (fix F7) | `packages/myelin-hub/api/src/myelin_hub_api/service.py:138-214`, `packages/myelin-hub/api/src/myelin_hub_api/service.py:1151`, `packages/myelin-hub/api/src/myelin_hub_api/service.py:1157-1161` | `evidence/patches/F7-onboard-all-or-nothing.diff` |
| `P8_FailedLeavesNothing` | invariant | ← `packages/myelin-hub/api/src/myelin_hub_api/service.py:1140-1143`, `docs/adr/0009-hub-write-policy.md:9` | 동결 |
| `P9_ConfigHasItsPack` | invariant | ← `docs/adr/0004-myelin-yaml-schema.md:12`, `packages/myelin-hub/api/src/myelin_hub_api/service.py:1316-1320` | 동결 |
| `P10_VaultIsCommitted` | invariant | ← `docs/adr/0009-hub-write-policy.md:9`, `docs/adr/0009-hub-write-policy.md:11` | 동결 |
