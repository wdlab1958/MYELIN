# Correspondence: hub-onboard-atomicity

Spec commit: `c29d83f` + 2026-11-18 패치(F7). 줄 번호는 패치 적용 후 기준. 수정 전 `onboard` 는 `c29d83f` 의 `service.py` 852~906행.

| Model element | Kind | Source (file:line) | Abstraction / Assumption |
|---|---|---|---|
| `pack` | variable | `<Vault>/packs/me.my-domains/pack.yaml` — `packages/myelin-hub/api/src/myelin_hub_api/service.py:1232-1273` | |
| `config` | variable | `<Vault>/myelin.yaml` — `packages/myelin-core/src/myelin_core/scaffold.py:249-274` init_vault() | |
| `scaffold` | variable | welcome 초안·`.myelin/` — `packages/myelin-hub/api/src/myelin_hub_api/service.py:1108-1111`, `packages/myelin-hub/api/src/myelin_hub_api/service.py:1115-1146` | scaffold plan 의 다른 파일은 `config` 와 같은 운명(A2) |
| `repo`, `committed` | variable | `.git/`, `[myelin:init]` — `packages/myelin-hub/api/src/myelin_hub_api/service.py:359-384` ensure_git() | |
| `Start` | action | `packages/myelin-hub/api/src/myelin_hub_api/app.py:334-336` → `packages/myelin-hub/api/src/myelin_hub_api/service.py:1055-1078` (이미 Vault 면 409: 1061-1064) | |
| `WritePack` | action | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1069-1071` → `packages/myelin-hub/api/src/myelin_hub_api/service.py:1232-1273` | `Custom` |
| `InitVault` | action | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1080-1113` (init_vault 1101) | 원자적(A1) |
| `Welcome` | action | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1108-1111` | |
| `GitCommit` | action | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1112` → `packages/myelin-hub/api/src/myelin_hub_api/service.py:359-384` | |
| `Fail` | action (env) | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1074-1078` → `packages/myelin-hub/api/src/myelin_hub_api/service.py:136-212` _OnboardUndo | 어느 단계 뒤에서든 |
| `FullRollback` | constant (fix F7) | `packages/myelin-hub/api/src/myelin_hub_api/service.py:136-212`, `packages/myelin-hub/api/src/myelin_hub_api/service.py:1068`, `packages/myelin-hub/api/src/myelin_hub_api/service.py:1074-1078` | `evidence/patches/F7-onboard-all-or-nothing.diff` |
| `P8_FailedLeavesNothing` | invariant | ← `packages/myelin-hub/api/src/myelin_hub_api/service.py:1057-1060`, `docs/adr/0009-hub-write-policy.md:9` | 동결 |
| `P9_ConfigHasItsPack` | invariant | ← `docs/adr/0004-myelin-yaml-schema.md:12`, `packages/myelin-hub/api/src/myelin_hub_api/service.py:1233-1237` | 동결 |
| `P10_VaultIsCommitted` | invariant | ← `docs/adr/0009-hub-write-policy.md:9`, `docs/adr/0009-hub-write-policy.md:11` | 동결 |
