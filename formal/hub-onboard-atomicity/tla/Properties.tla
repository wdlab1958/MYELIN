---------------------------- MODULE Properties ----------------------------
(* Frozen properties for concern hub-onboard-atomicity (G2 — HITL: pending Brian review). *)
(* Do not weaken. Any change here is a "model change" that the report must state.        *)
EXTENDS Spec

\* P8 (protocol, frozen) — a failed onboarding leaves no half-initialised Vault: nothing the
\* request created remains.
\* src: packages/myelin-hub/api/src/myelin_hub_api/service.py:1140-1143 (onboard() docstring: all-or-nothing; before the patch the except-branch said "no half-initialised directory left behind" and removed only the personal pack)
\*      docs/adr/0009-hub-write-policy.md:9 (§2 onboarding = init_vault + welcome 초안 + git init, 정확히 하나의 commit)
P8_FailedLeavesNothing ==
    phase = "failed" => ~pack /\ ~config /\ ~scaffold /\ ~repo

\* P9 (protocol, frozen) — when no request is running, a Vault whose myelin.yaml lists the
\* personal pack has that pack on disk (a Domain is always declared by an installed pack).
\* src: docs/adr/0004-myelin-yaml-schema.md:12 (`packs` 는 Pack 이름 …), docs/adr/0004-myelin-yaml-schema.md:10 (모든 Domain ID 는 Pack 이 선언)
\*      packages/myelin-hub/api/src/myelin_hub_api/service.py:1316-1320 (_write_personal_pack docstring)
P9_ConfigHasItsPack ==
    (phase # "running" /\ config /\ Custom) => pack

\* P10 (protocol, frozen) — a Vault created by onboarding has its `[myelin:init]` commit.
\* src: docs/adr/0009-hub-write-policy.md:9, docs/adr/0009-hub-write-policy.md:11 (§4 첫 쓰기에서 git init + [myelin:init] 커밋)
P10_VaultIsCommitted ==
    (phase # "running" /\ config) => committed

\* C4 (code-level)
C4_TypeOK == TypeOK

----------------------------------------------------------------------------
\* Sanity invariants — MUST FAIL.
S_NeverOk      == phase # "ok"                 \* onboarding can succeed
S_NeverRetryOk == ~(phase = "ok" /\ retried)   \* …and can succeed on a retry after a failure
=============================================================================
