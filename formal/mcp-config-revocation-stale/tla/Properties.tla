------------------------- MODULE Properties -------------------------
(* FROZEN properties P1, P2 from PROPERTIES.md. Do not weaken.          *)
EXTENDS Spec

TypeOK ==
    /\ file  \in [Caps -> BOOLEAN]
    /\ cache \in [Caps -> BOOLEAN]
    /\ registered \in BOOLEAN
    /\ opened \in BOOLEAN
    /\ lock \in Calls \cup {NoCall}
    /\ pc \in [Calls -> {"idle", "check", "prepare", "release", "released", "denied", "done"}]
    /\ kind \in [Calls -> Caps]
    /\ revokedAtBegin \in [Calls -> BOOLEAN]
    /\ released \in 0..Cardinality(Calls)
    /\ leakedW  \in 0..Cardinality(Calls)
    /\ leakedX  \in 0..Cardinality(Calls)

\* P1: no draft file created by a call that began after write was revoked on disk
Inv_NoDraftAfterRevoke == leakedW = 0

\* P2: no confidential body released by a call that began after expose was revoked
Inv_NoConfidentialAfterRevoke == leakedX = 0

\* S1 SANITY (must FAIL): a release and a revocation both reachable in one run
Sanity_ReleaseThenRevoke == ~(released >= 1 /\ \E c \in Caps : ~file[c])
=============================================================================
