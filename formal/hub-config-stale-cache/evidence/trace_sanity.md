| # | Action | Code | Changed |
|---|---|---|---|
| 1 | `Init` |  | `formBase` = {}; `badAccept` = FALSE; `cache` = {}; `accepted` = {}; `file` = {}; `formLoaded` = FALSE; `form` = {}; `badReject` = FALSE; `lost` = {} |
| 2 | `CliAddDomain(d1)` | packages/myelin-core/src/myelin_core/scaffold.py:307-316,352 | `file` = {d1} |
| 3 | `HubPromote(d1)` ⚠ | packages/myelin-hub/api/src/myelin_hub_api/service.py:645-680 | `cache` = {d1}; `accepted` = {d1} |
