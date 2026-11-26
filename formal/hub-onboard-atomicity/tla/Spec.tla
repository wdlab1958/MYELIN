------------------------------- MODULE Spec -------------------------------
(* MYELIN Hub — POST /api/onboarding (onboard): a step fails part-way.                   *)
(* Concern: hub-onboard-atomicity (formal/hub-onboard-atomicity/SCOPE.md)                *)
(*                                                                                       *)
(* One request, four writing steps, and an environment that may fail the request after   *)
(* any of them (the realistic case: the first commit is refused by the Vault pre-commit  *)
(* device because the chosen folder already holds a note without frontmatter).           *)
(*                                                                                       *)
(*   1 WritePack   packs/me.my-domains/pack.yaml   (only when the wizard defines Domains) *)
(*   2 InitVault   myelin.yaml (lists me.my-domains) + scaffold                           *)
(*   3 Welcome     .myelin/ events + the welcome draft                                    *)
(*   4 GitCommit   git init + pre-commit hook + `[myelin:init]` commit                    *)
(*                                                                                       *)
(* Fix toggle                                                                            *)
(*   FullRollback  on failure every file this request created is removed (not only the   *)
(*                 personal pack), so the folder is as it was and onboarding can be      *)
(*                 retried after the cause is fixed.                                     *)
EXTENDS Naturals

CONSTANTS FullRollback,   \* BOOLEAN — the fix
          Custom          \* BOOLEAN — the wizard defines its own Domains (creates a personal pack)

ASSUME FullRollback \in BOOLEAN /\ Custom \in BOOLEAN

VARIABLES
    step,       \* 0..4 completed steps of the request in flight
    phase,      \* "idle" | "running" | "ok" | "failed"
    pack,       \* BOOLEAN  packs/me.my-domains/pack.yaml exists
    config,     \* BOOLEAN  myelin.yaml exists (and lists me.my-domains when Custom)
    scaffold,   \* BOOLEAN  welcome draft / runtime files exist
    repo,       \* BOOLEAN  .git exists
    committed,  \* BOOLEAN  the `[myelin:init]` commit exists
    retried     \* BOOLEAN  history: a second onboarding request was accepted after a failure

vars == <<step, phase, pack, config, scaffold, repo, committed, retried>>

TypeOK ==
    /\ step \in 0..4 /\ phase \in {"idle", "running", "ok", "failed"}
    /\ pack \in BOOLEAN /\ config \in BOOLEAN /\ scaffold \in BOOLEAN
    /\ repo \in BOOLEAN /\ committed \in BOOLEAN /\ retried \in BOOLEAN

Init ==
    /\ step = 0 /\ phase = "idle"
    /\ pack = FALSE /\ config = FALSE /\ scaffold = FALSE /\ repo = FALSE /\ committed = FALSE
    /\ retried = FALSE

\* POST /api/onboarding is accepted only when the folder is not a Vault yet (else 409).
\* src: packages/myelin-hub/api/src/myelin_hub_api/service.py:1138-1161 onboard() — 409 when already a Vault (1061-1064)
Start ==
    /\ phase \in {"idle", "failed"} /\ ~config
    /\ retried' = (retried \/ phase = "failed")
    /\ phase' = "running" /\ step' = 0
    /\ UNCHANGED <<pack, config, scaffold, repo, committed>>

\* src: packages/myelin-hub/api/src/myelin_hub_api/service.py:1315-1356 _write_personal_pack()
WritePack ==
    /\ phase = "running" /\ step = 0
    /\ pack' = (pack \/ Custom) /\ step' = 1
    /\ UNCHANGED <<phase, config, scaffold, repo, committed, retried>>

\* src: packages/myelin-hub/api/src/myelin_hub_api/service.py:1163-1196 _onboard() -> scaffold.init_vault() (1101)
InitVault ==
    /\ phase = "running" /\ step = 1
    /\ config' = TRUE /\ step' = 2
    /\ UNCHANGED <<phase, pack, scaffold, repo, committed, retried>>

\* src: packages/myelin-hub/api/src/myelin_hub_api/service.py:1191-1194 reload(), record_event(), _write_welcome()
Welcome ==
    /\ phase = "running" /\ step = 2
    /\ scaffold' = TRUE /\ step' = 3
    /\ UNCHANGED <<phase, pack, config, repo, committed, retried>>

\* src: packages/myelin-hub/api/src/myelin_hub_api/service.py:368-393 ensure_git(): git init, hook, add -A, commit
GitCommit ==
    /\ phase = "running" /\ step = 3
    /\ repo' = TRUE /\ committed' = TRUE /\ step' = 4 /\ phase' = "ok"
    /\ UNCHANGED <<pack, config, scaffold, retried>>

\* The request fails after `step` completed steps. A failure during step 4 happens after
\* `git init` (the repository exists) and before the commit.
\* Before the patch the handler removed only the personal pack (service.py onboard(): "no
\* half-initialised directory left behind").
\* src: packages/myelin-hub/api/src/myelin_hub_api/service.py:1157-1161 onboard() except-branch -> packages/myelin-hub/api/src/myelin_hub_api/service.py:138-214 _OnboardUndo (files_first, rest)
Fail ==
    /\ phase = "running" /\ step \in 0..3
    /\ phase' = "failed"
    /\ IF FullRollback
         THEN /\ pack' = FALSE /\ config' = FALSE /\ scaffold' = FALSE /\ repo' = FALSE
         ELSE /\ pack' = FALSE
              /\ repo' = (step = 3)
              /\ UNCHANGED <<config, scaffold>>
    /\ UNCHANGED <<step, committed, retried>>

Next == Start \/ WritePack \/ InitVault \/ Welcome \/ GitCommit \/ Fail

Spec == Init /\ [][Next]_vars
=============================================================================
