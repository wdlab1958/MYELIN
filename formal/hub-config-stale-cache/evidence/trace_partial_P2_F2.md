| # | Action | Code | Changed |
|---|---|---|---|
| 1 | `Init` |  | `formBase` = {}; `badAccept` = FALSE; `cache` = {}; `accepted` = {}; `file` = {}; `formLoaded` = FALSE; `form` = {}; `badReject` = FALSE; `lost` = {} |
| 2 | `BrowserGet` | packages/myelin-hub/web/src/pages/Settings.tsx:17 | `formLoaded` = TRUE |
| 3 | `CliAddDomain(d1)` | packages/myelin-core/src/myelin_core/scaffold.py:307-316,352 | `file` = {d1} |
| 4 | `BrowserPut` ⚠ | Settings.tsx:18-20 | `file` = {}; `formLoaded` = FALSE; `lost` = {d1} |
