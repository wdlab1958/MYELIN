| # | Action | Code | Changed |
|---|---|---|---|
| 1 | `Init` |  | `final` = "O"; `lock` = "none"; `good` = {"O", "A"}; `backup` = (r1 :> "-" @@ r2 :> "-"); `resp` = (r1 :> "-" @@ r2 :> "-"); `raceError` = FALSE; `content` = (r1 :> "A" @@ r2 :> "A"); `pc` = (r1 :> "start" @@ r2 :> "start"); `head` = "O"; `saved` = (r1 :> "-" @@ r2 :> "-"); `tmp` = "-" |
| 2 | `WriteTmp(r1)` | packages/myelin-hub/api/src/myelin_hub_api/service.py:938-988 | `lock` = r1; `pc` = (r1 :> "wrote" @@ r2 :> "start"); `tmp` = "A" |
| 3 | `ReadBackup(r1)` | packages/myelin-hub/api/src/myelin_hub_api/service.py:938-988 | `backup` = (r1 :> "O" @@ r2 :> "-"); `pc` = (r1 :> "backed" @@ r2 :> "start") |
| 4 | `Move(r1)` | packages/myelin-hub/api/src/myelin_hub_api/service.py:938-988 | `final` = "A"; `pc` = (r1 :> "moved" @@ r2 :> "start"); `tmp` = "-" |
| 5 | `LoadOkCommit(r1)` ⚠ |  | `lock` = "none"; `resp` = (r1 :> "ok" @@ r2 :> "-"); `pc` = (r1 :> "done" @@ r2 :> "start"); `head` = "A"; `saved` = (r1 :> "A" @@ r2 :> "-") |
