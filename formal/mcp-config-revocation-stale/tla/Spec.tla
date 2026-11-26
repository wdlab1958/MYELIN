---------------------------- MODULE Spec ----------------------------
(***************************************************************************)
(* mcp-config-revocation-stale — pattern P06 consent-revocation, refined.  *)
(*                                                                         *)
(* MCP server process loads myelin.yaml once at startup (Open) and judges  *)
(* write_draft / expose_confidential from that in-memory copy (cache).     *)
(* Another process (Hub PUT /api/settings, CLI, editor) revokes a          *)
(* permission on disk (Revoke). Tool calls are serialized by the service   *)
(* RLock: Begin -> Check -> Prepare -> Release -> End.                     *)
(*                                                                         *)
(* FIX = FALSE : Check uses cache (current code, service.py:83-84,66-68)   *)
(* FIX = TRUE  : Check reloads myelin.yaml if changed (under the lock),    *)
(*               i.e. cache' = file, and judges from the disk value.       *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

CONSTANTS Calls,   \* tool calls, e.g. {"c1", "c2"}
          FIX

Caps   == {"write", "expose"}
NoCall == "none"

VARIABLES file,           \* permission bits on disk (myelin.yaml)
          cache,          \* MCP process copy (VaultService.vault.config)
          registered,     \* write_draft tool registered at startup
          opened,         \* server started at least once
          lock,           \* service RLock holder
          pc, kind,       \* per-call program counter and tool kind
          revokedAtBegin, \* ghost: permission was FALSE on disk at Begin (A5)
          released, leakedW, leakedX  \* ghosts

vars == <<file, cache, registered, opened, lock, pc, kind,
          revokedAtBegin, released, leakedW, leakedX>>

Init ==
    /\ file           = [c \in Caps |-> TRUE]
    /\ cache          = [c \in Caps |-> TRUE]
    /\ registered     = FALSE
    /\ opened         = FALSE
    /\ lock           = NoCall
    /\ pc             = [r \in Calls |-> "idle"]
    /\ kind           = [r \in Calls |-> "expose"]
    /\ revokedAtBegin = [r \in Calls |-> FALSE]
    /\ released       = 0
    /\ leakedW        = 0
    /\ leakedX        = 0

\* server.py:160-167 serve(): VaultService.open (load_config) + build_server
Open ==
    /\ lock = NoCall
    /\ cache'      = file
    /\ registered' = file["write"]
    /\ opened'     = TRUE
    /\ UNCHANGED <<file, lock, pc, kind, revokedAtBegin, released, leakedW, leakedX>>

\* Hub save_settings (service.py:834) / CLI / editor: atomic, monotone (A3, A4)
Revoke(c) ==
    /\ file[c]
    /\ file' = [file EXCEPT ![c] = FALSE]
    /\ UNCHANGED <<cache, registered, opened, lock, pc, kind,
                   revokedAtBegin, released, leakedW, leakedX>>

\* handler -> _guard -> _serialized: acquire self._lock
Begin(r) ==
    /\ opened
    /\ lock = NoCall
    /\ pc[r] = "idle"
    /\ \E k \in Caps :
          /\ (k = "write" => registered)
          /\ kind' = [kind EXCEPT ![r] = k]
          /\ revokedAtBegin' = [revokedAtBegin EXCEPT ![r] = ~file[k]]
    /\ lock' = r
    /\ pc'   = [pc EXCEPT ![r] = "check"]
    /\ UNCHANGED <<file, cache, registered, opened, released, leakedW, leakedX>>

\* service.py:232-235 write_enabled / 134,138,151 expose_confidential
Check(r) ==
    /\ pc[r] = "check"
    /\ LET allowed == IF FIX THEN file[kind[r]] ELSE cache[kind[r]]
       IN pc' = [pc EXCEPT ![r] = IF allowed THEN "prepare" ELSE "denied"]
    /\ cache' = IF FIX THEN file ELSE cache
    /\ UNCHANGED <<file, registered, opened, lock, kind,
                   revokedAtBegin, released, leakedW, leakedX>>

\* template read / mkdir / index.refresh / index.get (policy-independent I/O)
Prepare(r) ==
    /\ pc[r] = "prepare"
    /\ pc' = [pc EXCEPT ![r] = "release"]
    /\ UNCHANGED <<file, cache, registered, opened, lock, kind,
                   revokedAtBegin, released, leakedW, leakedX>>

\* release point: target.open("x") (283-284) / index.body / search (155,128-135)
Release(r) ==
    /\ pc[r] = "release"
    /\ pc'       = [pc EXCEPT ![r] = "released"]
    /\ released' = released + 1
    /\ leakedW'  = IF kind[r] = "write"  /\ revokedAtBegin[r] THEN leakedW + 1 ELSE leakedW
    /\ leakedX'  = IF kind[r] = "expose" /\ revokedAtBegin[r] THEN leakedX + 1 ELSE leakedX
    /\ UNCHANGED <<file, cache, registered, opened, lock, kind, revokedAtBegin>>

\* release lock, reply on stdio
End(r) ==
    /\ pc[r] \in {"released", "denied"}
    /\ lock = r
    /\ pc'   = [pc EXCEPT ![r] = "done"]
    /\ lock' = NoCall
    /\ UNCHANGED <<file, cache, registered, opened, kind,
                   revokedAtBegin, released, leakedW, leakedX>>

Next ==
    \/ Open
    \/ \E c \in Caps : Revoke(c)
    \/ \E r \in Calls : Begin(r) \/ Check(r) \/ Prepare(r) \/ Release(r) \/ End(r)

Spec == Init /\ [][Next]_vars
=============================================================================
