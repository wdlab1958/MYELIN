| # | Action | Code | Changed |
|---|---|---|---|
| 1 | `Init` |  | `pending` = (n1 :> 3 @@ n2 :> 3); `draft` = (n1 :> 0 @@ n2 :> 0); `refused` = FALSE; `shown` = (n1 :> 3 @@ n2 :> 3); `approved` = (n1 :> 3 @@ n2 :> 3); `verified` = (n1 :> 3 @@ n2 :> 3) |
| 2 | `WriterRewrite(n1)` | plugin/hooks/guard_bash.py:1-5 | `draft` = (n1 :> 1 @@ n2 :> 0) |
| 3 | `BrowserRead(n1)` | packages/myelin-hub/web/src/pages/Review.tsx:16-20 | `shown` = (n1 :> 1 @@ n2 :> 3) |
| 4 | `HumanClick(n1)` | packages/myelin-hub/web/src/pages/Review.tsx:68 | `pending` = (n1 :> 1 @@ n2 :> 3) |
| 5 | `HubPromote(n1)` ⚠ | packages/myelin-hub/api/src/myelin_hub_api/service.py:645-715 | `pending` = (n1 :> 3 @@ n2 :> 3); `draft` = (n1 :> 3 @@ n2 :> 0); `shown` = (n1 :> 3 @@ n2 :> 3); `approved` = (n1 :> 1 @@ n2 :> 3); `verified` = (n1 :> 1 @@ n2 :> 3) |
