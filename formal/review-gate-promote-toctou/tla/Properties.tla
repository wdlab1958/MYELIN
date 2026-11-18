---------------------------- MODULE Properties ----------------------------
(* Frozen properties for concern review-gate-promote-toctou (G2 — HITL: pending Brian review). *)
(* Do not weaken. Any change here is a "model change" that the report must state.            *)
EXTENDS Spec

\* P3 (protocol, frozen) — what becomes `verified` is exactly what the human read before
\* clicking Promote. A promotion is a human judgement about a specific text; verifying a text
\* nobody read turns the Review Gate into a rubber stamp.
\* src: docs/adr/0009-hub-write-policy.md:4 (정본 §1.2 "HITL 승격 — verified 승격은 Hub 의 Review Gate 에서 사람의 클릭으로만")
\*      docs/adr/0009-hub-write-policy.md:14 ("AI 는 초안만, 승격은 사람만")
\*      packages/myelin-hub/web/src/pages/Review.tsx:13 ("읽음 확인: Promote 는 본문을 연 뒤에만")
\*      packages/myelin-hub/web/src/pages/Review.tsx:68 ("승격은 사람이 읽은 뒤에만 — 먼저 내용을 읽는다")
P3_VerifiedIsWhatWasRead == \A n \in Notes : verified[n] # None => verified[n] = approved[n]

\* C2 (code-level) — variable domains stay in range.
C2_TypeOK == TypeOK

----------------------------------------------------------------------------
\* Sanity invariants — MUST FAIL (MC_sanity*.cfg): the interesting states are reachable.
S_NeverVerified == \A n \in Notes : verified[n] = None        \* a promote can succeed
S_NeverRefused  == ~refused                                    \* the 409 path is taken
S_NeverRewrittenThenVerified == \A n \in Notes : verified[n] = None \/ verified[n] = 0   \* a rewritten draft can still be promoted after re-reading
=============================================================================
