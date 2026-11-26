---------------------------- MODULE Properties ----------------------------
(* Frozen properties for concern hub-pack-save-atomicity (G2 — HITL: pending Brian review). *)
(* Do not weaken. Any change here is a "model change" that the report must state.          *)
EXTENDS Spec

\* P4 (protocol, frozen) — when no save is in flight, pack.yaml on disk is a pack the loader
\* accepts: a rejected text is never left behind.
\* src: packages/myelin-hub/api/src/myelin_hub_api/service.py:1012-1018 (save_pack docstring: "written to <Vault>/packs/<name>/pack.yaml and loader-validated")
\*      docs/adr/0009-hub-write-policy.md:9 (§2 save_pack 은 쓰기 동작 6종 중 하나)
P4_DiskLoadable == AllDone => final \in good

\* P5 (protocol, frozen) — a 200 "저장됨 · commit …" means the commit recorded the text that
\* request submitted.
\* src: packages/myelin-hub/web/src/pages/Packs.tsx:41 (save(): "저장됨 · commit <sha>")
\*      docs/adr/0009-hub-write-policy.md:9 (각 동작은 정확히 하나의 git commit 으로 끝난다)
P5_OkMeansSaved == \A r \in Reqs : resp[r] = "ok" => saved[r] = content[r]

\* P6 (protocol, frozen) — all-or-nothing: when no save is in flight, pack.yaml on disk equals
\* the committed pack.yaml (the Vault is left either untouched or fully committed).
\* src: packages/myelin-hub/api/src/myelin_hub_api/service.py:304-310 (_mutation docstring, "ADR-0009: every mutation is exactly one commit — the Vault is left either untouched or fully committed, never half-moved")
\*      docs/adr/0009-hub-write-policy.md:9
P6_AllOrNothing == AllDone => final = head

\* P7 (protocol, frozen) — two overlapping saves never fail each other.
\* src: packages/myelin-hub/api/src/myelin_hub_api/service.py:124-128 (_serialised docstring: "a double click or two tabs must not race each other (… surface as a 500)")
P7_NoRaceError == ~raceError

\* C3 (code-level) — variable domains stay in range.
C3_TypeOK == TypeOK

----------------------------------------------------------------------------
\* Sanity invariants — MUST FAIL: the interesting states are reachable under the fix.
S_NeverOk       == \A r \in Reqs : resp[r] # "ok"
S_NeverRejected == \A r \in Reqs : resp[r] # "rejected"
S_NeverBothOk   == \E r \in Reqs : resp[r] # "ok"
=============================================================================
