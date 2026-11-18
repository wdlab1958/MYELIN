------------------------------- MODULE Spec -------------------------------
(* MYELIN Hub — Review Gate: "내용 읽기" (read) -> Promote (click) vs. a writer of the draft *)
(* Concern: review-gate-promote-toctou (formal/review-gate-promote-toctou/SCOPE.md)       *)
(*                                                                                       *)
(* Actors                                                                                *)
(*   Writer   — anything that may rewrite a file in 00_Inbox/ai-drafts/ while it waits   *)
(*              for review: a Claude Code skill (/distill, /ingest — Guard allows this   *)
(*              directory at level >= 1), the MCP write_draft tool, Obsidian.            *)
(*   Browser  — Hub Review page: "내용 읽기" fetches the body; Promote is enabled only    *)
(*              after the body was opened.                                               *)
(*   Hub      — HubService.promote(): reads the draft file *now* and moves it to         *)
(*              10_Domains/<D>/ with status verified.                                    *)
(*                                                                                       *)
(* Fix toggle                                                                            *)
(*   DigestCheck  The Promote click echoes the digest of the content the human read      *)
(*                (same idea as apply_patch's digest, service.py:763); the Hub   *)
(*                refuses (409) when the draft file no longer has that content.          *)
(* Granularity: one action = one HTTP request handler, one click, or one file write.     *)
EXTENDS Naturals

CONSTANTS Notes,        \* model values: drafts waiting in ai-drafts, e.g. {n1, n2}
          MaxVer,       \* bound on rewrites per draft (content versions 0..MaxVer)
          DigestCheck   \* BOOLEAN — the fix

ASSUME MaxVer \in Nat /\ DigestCheck \in BOOLEAN

None == MaxVer + 1          \* "absent" marker, outside the version range
Vers == 0..MaxVer
Opt  == 0..(MaxVer + 1)

VARIABLES
    draft,      \* [Notes -> Opt]  content of 00_Inbox/ai-drafts/<n>.md (None once promoted)
    shown,      \* [Notes -> Opt]  body the Review page currently displays for n
    pending,    \* [Notes -> Opt]  Promote request in flight: the content the human had read when clicking
    verified,   \* [Notes -> Opt]  content written to 10_Domains/<D>/<n>.md with status verified
    approved,   \* [Notes -> Opt]  history: what the human had read for the click that promoted n
    refused     \* BOOLEAN         history: some Promote was refused with 409 (digest mismatch)

vars == <<draft, shown, pending, verified, approved, refused>>

TypeOK ==
    /\ draft \in [Notes -> Opt] /\ shown \in [Notes -> Opt] /\ pending \in [Notes -> Opt]
    /\ verified \in [Notes -> Opt] /\ approved \in [Notes -> Opt] /\ refused \in BOOLEAN

Init ==
    /\ draft = [n \in Notes |-> 0]
    /\ shown = [n \in Notes |-> None] /\ pending = [n \in Notes |-> None]
    /\ verified = [n \in Notes |-> None] /\ approved = [n \in Notes |-> None]
    /\ refused = FALSE

----------------------------------------------------------------------------
\* A writer replaces the draft while it waits for review.
\* src: plugin/hooks/guard_bash.py:1-5 (AI writes are confined to — and allowed in — the Level-allowed directories, i.e. 00_Inbox/ai-drafts)
\*      docs/adr/0009-hub-write-policy.md:14 ("AI 는 초안만, 승격은 사람만")
WriterRewrite(n) ==
    /\ draft[n] # None /\ draft[n] < MaxVer
    /\ draft' = [draft EXCEPT ![n] = @ + 1]
    /\ UNCHANGED <<shown, pending, verified, approved, refused>>

\* "내용 읽기": GET /api/notes/<path> — the page now shows the current content.
\* src: packages/myelin-hub/web/src/pages/Review.tsx:16-20 openBody()
\*      packages/myelin-hub/api/src/myelin_hub_api/service.py:578-597 note() — body and digest from the same bytes
BrowserRead(n) ==
    /\ draft[n] # None
    /\ shown' = [shown EXCEPT ![n] = draft[n]]
    /\ UNCHANGED <<draft, pending, verified, approved, refused>>

\* The human clicks Promote (enabled only after the body was opened).
\* src: packages/myelin-hub/web/src/pages/Review.tsx:68 (Promote button: disabled until bodies[d.path] is set; sends { digest: digests[d.path] })
HumanClick(n) ==
    /\ shown[n] # None /\ pending[n] = None
    /\ pending' = [pending EXCEPT ![n] = shown[n]]
    /\ UNCHANGED <<draft, shown, verified, approved, refused>>

\* POST /api/review/promote/<path>: the Hub reads the draft file as it is now and verifies it.
\* src: packages/myelin-hub/api/src/myelin_hub_api/service.py:645-715 promote() — `raw_bytes = src.read_bytes()` (663), digest check -> 409 (664-668)
\*      packages/myelin-hub/api/src/myelin_hub_api/app.py:289-292
HubPromote(n) ==
    /\ pending[n] # None
    /\ pending' = [pending EXCEPT ![n] = None]
    /\ IF draft[n] = None
         THEN UNCHANGED <<draft, shown, verified, approved, refused>>      \* 404 draft not found
         ELSE IF DigestCheck /\ draft[n] # pending[n]
           THEN /\ refused' = TRUE                                         \* 409: read it again
                /\ shown' = [shown EXCEPT ![n] = None]
                /\ UNCHANGED <<draft, verified, approved>>
           ELSE /\ verified' = [verified EXCEPT ![n] = draft[n]]
                /\ approved' = [approved EXCEPT ![n] = pending[n]]
                /\ draft' = [draft EXCEPT ![n] = None]
                /\ shown' = [shown EXCEPT ![n] = None]
                /\ UNCHANGED refused

Next == \E n \in Notes : WriterRewrite(n) \/ BrowserRead(n) \/ HumanClick(n) \/ HubPromote(n)

\* Safety only. Stuttering is allowed: after every draft is promoted nothing is enabled.
Spec == Init /\ [][Next]_vars
=============================================================================
