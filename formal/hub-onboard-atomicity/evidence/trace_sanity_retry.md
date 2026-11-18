| # | Action | Code | Changed |
|---|---|---|---|
| 1 | `Init` |  | `config` = FALSE; `committed` = FALSE; `step` = 0; `phase` = "idle"; `retried` = FALSE; `pack` = FALSE; `scaffold` = FALSE; `repo` = FALSE |
| 2 | `Start` | packages/myelin-hub/api/src/myelin_hub_api/service.py:1055-1078 | `phase` = "running" |
| 3 | `Fail` | packages/myelin-hub/api/src/myelin_hub_api/service.py:1074-1078 | `phase` = "failed" |
| 4 | `Start` | packages/myelin-hub/api/src/myelin_hub_api/service.py:1055-1078 | `phase` = "running"; `retried` = TRUE |
| 5 | `WritePack` | packages/myelin-hub/api/src/myelin_hub_api/service.py:1232-1273 | `step` = 1; `pack` = TRUE |
| 6 | `InitVault` | packages/myelin-hub/api/src/myelin_hub_api/service.py:1080-1113 | `config` = TRUE; `step` = 2 |
| 7 | `Welcome` | packages/myelin-hub/api/src/myelin_hub_api/service.py:1108-1111 | `step` = 3; `scaffold` = TRUE |
| 8 | `GitCommit` ⚠ | packages/myelin-hub/api/src/myelin_hub_api/service.py:359-384 | `committed` = TRUE; `step` = 4; `phase` = "ok"; `repo` = TRUE |
