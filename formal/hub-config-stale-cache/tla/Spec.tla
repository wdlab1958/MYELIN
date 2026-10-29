------------------------------- MODULE Spec -------------------------------
(* MYELIN Hub — `<Vault>/myelin.yaml` 설정 캐시 vs CLI `myelin add-domain`             *)
(* Concern: hub-config-stale-cache (formal/hub-config-stale-cache/SCOPE.md)              *)
(*                                                                                       *)
(* Actors                                                                                *)
(*   CLI      — `myelin add-domain <ID>`: a separate process that rewrites myelin.yaml    *)
(*   Hub      — HubService (FastAPI) holding `self.vault.config` in memory                *)
(*   Browser  — Hub Settings page: fetch("/api/settings") then userPut("/api/settings")   *)
(* Shared resource: the Domain list of myelin.yaml (abstracted to the set of extra IDs).  *)
(*                                                                                       *)
(* Fix toggles                                                                           *)
(*   ReloadOnRequest  (F1, IMPLEMENTED)  HubService re-reads myelin.yaml before any       *)
(*                    decision when its bytes differ from the copy it loaded              *)
(*                    (service.py `_reload_if_changed`, called from `_v()` / `ready`).    *)
(*   IfMatch          (F2, PROPOSED, not in code)  PUT /api/settings is refused when      *)
(*                    myelin.yaml changed since the GET the form was built from.          *)
(* Granularity: one action = one HTTP request handler or one CLI write of myelin.yaml.    *)
EXTENDS Naturals, FiniteSets

CONSTANTS Doms,             \* model values: Domain IDs the CLI may add, e.g. {d1, d2}
          ReloadOnRequest,  \* BOOLEAN — fix F1
          IfMatch           \* BOOLEAN — fix F2 (proposed)

ASSUME ReloadOnRequest \in BOOLEAN /\ IfMatch \in BOOLEAN

VARIABLES
    file,        \* Domains written in <Vault>/myelin.yaml (the file on disk)
    cache,       \* HubService.vault.config.domains — the Hub's in-memory view
    form,        \* Browser: `current` = JSON of GET /api/settings (domains are not editable)
    formBase,    \* Browser: the file content the form was built from (abstract ETag)
    formLoaded,  \* Browser: GET done, PUT pending
    accepted,    \* history: Domains into which a promote was accepted
    badReject,   \* P1 witness: promote rejected although the Domain is in the file
    badAccept,   \* P1 witness: promote accepted although the Domain is not in the file
    lost         \* P2 witness: Domains removed from the file by a Settings save that never saw them

vars == <<file, cache, form, formBase, formLoaded, accepted, badReject, badAccept, lost>>

TypeOK ==
    /\ file \subseteq Doms /\ cache \subseteq Doms
    /\ form \subseteq Doms /\ formBase \subseteq Doms /\ formLoaded \in BOOLEAN
    /\ accepted \subseteq Doms /\ lost \subseteq Doms
    /\ badReject \in BOOLEAN /\ badAccept \in BOOLEAN

\* Hub process starts with the file read once (service.py:126-130 open() -> reload()).
Init ==
    /\ file = {} /\ cache = {}
    /\ form = {} /\ formBase = {} /\ formLoaded = FALSE
    /\ accepted = {} /\ badReject = FALSE /\ badAccept = FALSE /\ lost = {}

\* The Domain list a Hub request decides with.
\* src: packages/myelin-hub/api/src/myelin_hub_api/service.py:159-192 `_read_config_bytes` / `_reload_if_changed` / `ready` / `_v()`
\*      (before the F1 patch: service.py:158-169 — `_v()` returned the start-up `self.vault` unconditionally)
View == IF ReloadOnRequest THEN file ELSE cache

----------------------------------------------------------------------------
\* src: packages/myelin-core/src/myelin_core/scaffold.py:307-316,352 add_domain(): extra += [d]; write myelin.yaml
\*      packages/myelin-cli/src/myelin_cli/app.py:363-385 `myelin add-domain`
CliAddDomain(d) ==
    /\ d \notin file
    /\ file' = file \cup {d}
    /\ UNCHANGED <<cache, form, formBase, formLoaded, accepted, badReject, badAccept, lost>>

\* src: service.py:126-154 HubService.open()/reload() — the operator restarts the Hub (today's workaround)
HubRestart ==
    /\ cache' = file
    /\ UNCHANGED <<file, form, formBase, formLoaded, accepted, badReject, badAccept, lost>>

\* src: service.py:534-555 promote(): v = self._v() ... `if target_domain not in v.config.domains.all_ids: 422`
\*      (also domains() 419-439 and every other read of v.config.domains)
HubPromote(d) ==
    /\ cache' = View
    /\ (IF d \in View
          THEN /\ accepted' = accepted \cup {d}
               /\ badAccept' = (badAccept \/ d \notin file)
               /\ UNCHANGED badReject
          ELSE /\ badReject' = (badReject \/ d \in file)
               /\ UNCHANGED <<accepted, badAccept>>)
    /\ UNCHANGED <<file, form, formBase, formLoaded, lost>>

\* src: packages/myelin-hub/web/src/pages/Settings.tsx:17 `current = await fetch("/api/settings")`
\*      -> app.py:239 GET /api/settings -> service.py:672-674 settings(): v.config.model_dump()
BrowserGet ==
    /\ cache' = View
    /\ form' = View /\ formBase' = View /\ formLoaded' = TRUE
    /\ UNCHANGED <<file, accepted, badReject, badAccept, lost>>

\* src: Settings.tsx:18-20 `next = {...current, level, mcp, commons}; userPut("/api/settings", next)`
\*      -> app.py:298 PUT /api/settings -> service.py:676-700 save_settings(): write myelin.yaml, commit, reload()
BrowserPut ==
    /\ formLoaded
    /\ formLoaded' = FALSE
    /\ (IF IfMatch /\ file # formBase
          THEN UNCHANGED <<file, cache, lost>>          \* 412: the client must GET again
          ELSE /\ lost' = lost \cup (file \ form)       \* Domains the save silently drops
               /\ file' = form
               /\ cache' = form)                        \* save_settings() ends with reload()
    /\ UNCHANGED <<form, formBase, accepted, badReject, badAccept>>

Next ==
    \/ \E d \in Doms : CliAddDomain(d) \/ HubPromote(d)
    \/ HubRestart
    \/ BrowserGet
    \/ BrowserPut

\* HubPromote is always enabled, so the system never deadlocks; no fairness needed (safety only).
Spec == Init /\ [][Next]_vars
=============================================================================
