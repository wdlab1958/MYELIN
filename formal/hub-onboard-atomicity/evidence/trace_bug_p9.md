| # | Action | Code | Changed |
|---|---|---|---|
| 1 | `Init` |  | `config` = FALSE; `committed` = FALSE; `step` = 0; `phase` = "idle"; `retried` = FALSE; `pack` = FALSE; `scaffold` = FALSE; `repo` = FALSE |
| 2 | `Start` | packages/myelin-hub/api/src/myelin_hub_api/service.py:1055-1078 | `phase` = "running" |
| 3 | `WritePack` | packages/myelin-hub/api/src/myelin_hub_api/service.py:1232-1273 | `step` = 1; `pack` = TRUE |
| 4 | `InitVault` | packages/myelin-hub/api/src/myelin_hub_api/service.py:1080-1113 | `config` = TRUE; `step` = 2 |
| 5 | `Fail` ⚠ | packages/myelin-hub/api/src/myelin_hub_api/service.py:1074-1078 | `phase` = "failed"; `pack` = FALSE |
