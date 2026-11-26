------------------------------- MODULE Spec -------------------------------
(* MYELIN Hub — PUT /api/packs/<name> (save_pack): two overlapping saves, loader rejection, *)
(* and a failing git commit.                                                              *)
(* Concern: hub-pack-save-atomicity (formal/hub-pack-save-atomicity/SCOPE.md)             *)
(*                                                                                        *)
(* Actors: two request-handler threads of the Hub (FastAPI runs sync handlers in a        *)
(* thread pool) saving the same personal pack — a double click on "저장 (commit)" or two   *)
(* tabs. Shared resources: <Vault>/packs/<name>/pack.yaml, the fixed temp file            *)
(* pack.yaml.tmp next to it, and the Vault git repository.                                *)
(*                                                                                        *)
(* Fix toggles                                                                            *)
(*   Serialised  save_pack runs under HubService._write_lock like every other write       *)
(*               (`@_serialised`, service.py:122-133).                                    *)
(*   Rollback    when the commit fails, pack.yaml is restored to what it was before the   *)
(*               request (ADR-0009: untouched or fully committed).                        *)
(* Granularity: one action = one file-system step of save_pack (write tmp, read backup,   *)
(* move, load+restore or load+commit).                                                    *)
EXTENDS Naturals, FiniteSets

CONSTANTS Reqs,            \* model values: concurrent save requests, e.g. {r1, r2}
          Serialised,      \* BOOLEAN — fix (lock)
          Rollback,        \* BOOLEAN — fix (restore on commit failure)
          CommitMayFail    \* BOOLEAN — environment: the pre-commit device / git may refuse a commit

ASSUME Serialised \in BOOLEAN /\ Rollback \in BOOLEAN /\ CommitMayFail \in BOOLEAN

Texts == {"O", "A", "B"}     \* "O" = pack.yaml before the requests; "A","B" = submitted YAML texts
NoText == "-"

VARIABLES
    content,    \* [Reqs -> {"A","B"}]  the YAML each request submits (equal = a double click)
    good,       \* SUBSET Texts          texts the pack loader accepts ("O" always is)
    pc,         \* [Reqs -> {"start","wrote","backed","moved","done"}]
    lock,       \* Reqs \cup {NoReq}     holder of HubService._write_lock (only used when Serialised)
    tmp,        \* Texts \cup {NoText}   packs/<name>/pack.yaml.tmp
    final,      \* Texts                 packs/<name>/pack.yaml
    backup,     \* [Reqs -> Texts \cup {NoText}]  `backup` local of each request
    head,       \* Texts                 pack.yaml as of the last git commit
    resp,       \* [Reqs -> {"-","ok","rejected","error"}]  HTTP outcome: 200 / 422 / 500
    saved,      \* [Reqs -> Texts \cup {NoText}]  what the commit of a 200 response actually recorded
    raceError   \* BOOLEAN  a request died on the other request's temp file (FileNotFoundError -> 500)

vars == <<content, good, pc, lock, tmp, final, backup, head, resp, saved, raceError>>
NoReq == "none"

TypeOK ==
    /\ content \in [Reqs -> {"A", "B"}] /\ good \subseteq Texts /\ "O" \in good
    /\ pc \in [Reqs -> {"start", "wrote", "backed", "moved", "done"}]
    /\ lock \in Reqs \cup {NoReq}
    /\ tmp \in Texts \cup {NoText} /\ final \in Texts /\ head \in Texts
    /\ backup \in [Reqs -> Texts \cup {NoText}]
    /\ resp \in [Reqs -> {"-", "ok", "rejected", "error"}]
    /\ saved \in [Reqs -> Texts \cup {NoText}]
    /\ raceError \in BOOLEAN

\* Every combination of submitted texts and of loader verdicts is explored.
\* (All texts already passed the Pack schema check — validate_pack_yaml — before any write;
\*  "not in good" = rejected by load_pack: unresolved sidecar, bad template reference, ...)
Init ==
    /\ content \in [Reqs -> {"A", "B"}]
    /\ good \in {S \cup {"O"} : S \in SUBSET {"A", "B"}}
    /\ pc = [r \in Reqs |-> "start"]
    /\ lock = NoReq
    /\ tmp = NoText /\ final = "O" /\ head = "O"
    /\ backup = [r \in Reqs |-> NoText]
    /\ resp = [r \in Reqs |-> "-"]
    /\ saved = [r \in Reqs |-> NoText]
    /\ raceError = FALSE

Release(r) == lock' = IF Serialised THEN NoReq ELSE lock

----------------------------------------------------------------------------
\* tmp = pdir / "pack.yaml.tmp"; tmp.write_text(text)   (the request holds _write_lock: `@_serialised`, 938)
\* src: packages/myelin-hub/api/src/myelin_hub_api/service.py:1011-1071 save_pack() — 974
WriteTmp(r) ==
    /\ pc[r] = "start"
    /\ IF Serialised THEN lock = NoReq /\ lock' = r ELSE UNCHANGED lock
    /\ tmp' = content[r]
    /\ pc' = [pc EXCEPT ![r] = "wrote"]
    /\ UNCHANGED <<content, good, final, backup, head, resp, saved, raceError>>

\* backup = final.read_bytes() if final.is_file() else None
\* src: packages/myelin-hub/api/src/myelin_hub_api/service.py:1011-1071 save_pack() — 966
ReadBackup(r) ==
    /\ pc[r] = "wrote"
    /\ backup' = [backup EXCEPT ![r] = final]
    /\ pc' = [pc EXCEPT ![r] = "backed"]
    /\ UNCHANGED <<content, good, lock, tmp, final, head, resp, saved, raceError>>

\* shutil.move(tmp, final) — raises FileNotFoundError when the other request already moved the temp file
\* src: packages/myelin-hub/api/src/myelin_hub_api/service.py:1011-1071 save_pack() — 975
\*      packages/myelin-hub/api/src/myelin_hub_api/app.py:252-306 (OSError -> 500 "filesystem error")
Move(r) ==
    /\ pc[r] = "backed"
    /\ IF tmp = NoText
         THEN /\ raceError' = TRUE
              /\ resp' = [resp EXCEPT ![r] = "error"]
              /\ pc' = [pc EXCEPT ![r] = "done"]
              /\ Release(r)
              /\ UNCHANGED <<tmp, final>>
         ELSE /\ final' = tmp /\ tmp' = NoText
              /\ pc' = [pc EXCEPT ![r] = "moved"]
              /\ UNCHANGED <<resp, raceError, lock>>
    /\ UNCHANGED <<content, good, backup, head, saved>>

\* load_pack(pdir): rejected -> restore the backup, 422; accepted -> git commit, 200
\* (or the commit is refused -> 500; with Rollback the file is restored first)
\* src: packages/myelin-hub/api/src/myelin_hub_api/service.py:1011-1071 save_pack() — load_pack (977), _commit (980-984), _undo_pack_write on any failure (985-987)
\*      packages/myelin-hub/api/src/myelin_hub_api/service.py:1073-1117 _undo_pack_write()
\*      packages/myelin-hub/api/src/myelin_hub_api/service.py:395-399 _commit()
LoadRejected(r) ==
    /\ pc[r] = "moved" /\ final \notin good
    /\ final' = backup[r]
    /\ resp' = [resp EXCEPT ![r] = "rejected"]
    /\ pc' = [pc EXCEPT ![r] = "done"]
    /\ Release(r)
    /\ UNCHANGED <<content, good, tmp, backup, head, saved, raceError>>

LoadOkCommit(r) ==
    /\ pc[r] = "moved" /\ final \in good
    /\ head' = final
    /\ saved' = [saved EXCEPT ![r] = final]
    /\ resp' = [resp EXCEPT ![r] = "ok"]
    /\ pc' = [pc EXCEPT ![r] = "done"]
    /\ Release(r)
    /\ UNCHANGED <<content, good, tmp, final, backup, raceError>>

LoadOkCommitFails(r) ==
    /\ CommitMayFail
    /\ pc[r] = "moved" /\ final \in good
    /\ final' = IF Rollback THEN backup[r] ELSE final
    /\ resp' = [resp EXCEPT ![r] = "error"]
    /\ pc' = [pc EXCEPT ![r] = "done"]
    /\ Release(r)
    /\ UNCHANGED <<content, good, tmp, backup, head, saved, raceError>>

Next == \E r \in Reqs :
    WriteTmp(r) \/ ReadBackup(r) \/ Move(r) \/ LoadRejected(r) \/ LoadOkCommit(r) \/ LoadOkCommitFails(r)

AllDone == \A r \in Reqs : pc[r] = "done"

\* Safety only; when every request is done nothing is enabled (stuttering).
Spec == Init /\ [][Next]_vars
=============================================================================
