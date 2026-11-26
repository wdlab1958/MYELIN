/-!
# mcp-config-revocation-stale — transition system (mirror of `tla/Spec.tla`)

`Call` is an arbitrary type with decidable equality: the number of tool calls
(actors) is unbounded. `fix` mirrors the TLA+ constant `FIX`.
-/
namespace McpConfigRevocation

inductive Cap where
  | write
  | expose
  deriving DecidableEq, Repr

inductive PC where
  | idle | check | prepare | release | released | denied | done
  deriving DecidableEq, Repr

/-- Point update of a function (avoids a Mathlib dependency). -/
def upd {α β : Type} [DecidableEq α] (f : α → β) (a : α) (b : β) : α → β :=
  fun x => if x = a then b else f x

@[simp] theorem upd_same {α β : Type} [DecidableEq α] (f : α → β) (a : α) (b : β) :
    upd f a b a = b := by simp [upd]

@[simp] theorem upd_ne {α β : Type} [DecidableEq α] (f : α → β) {a x : α} (b : β)
    (h : x ≠ a) : upd f a b x = f x := by simp [upd, h]

structure State (Call : Type) where
  file           : Cap → Bool     -- permission bits on disk (myelin.yaml)
  cache          : Cap → Bool     -- MCP process copy
  registered     : Bool           -- write_draft registered at startup
  opened         : Bool
  lock           : Option Call    -- `none` = NoCall
  pc             : Call → PC
  kind           : Call → Cap
  revokedAtBegin : Call → Bool    -- ghost
  released       : Nat            -- ghost
  leakedW        : Nat            -- ghost
  leakedX        : Nat            -- ghost

variable {Call : Type} [DecidableEq Call]

def init : State Call where
  file := fun _ => true
  cache := fun _ => true
  registered := false
  opened := false
  lock := none
  pc := fun _ => .idle
  kind := fun _ => .expose
  revokedAtBegin := fun _ => false
  released := 0
  leakedW := 0
  leakedX := 0

/-- `Next` of `Spec.tla`, parametrised by `FIX`. -/
inductive Step (fix : Bool) : State Call → State Call → Prop where
  /-- `Open` -/
  | open_ (s : State Call) :
      s.lock = none →
      Step fix s { s with cache := s.file, registered := s.file .write, opened := true }
  /-- `Revoke(c)` -/
  | revoke (s : State Call) (c : Cap) :
      s.file c = true →
      Step fix s { s with file := upd s.file c false }
  /-- `Begin(r)` with chosen tool kind `k` -/
  | begin (s : State Call) (r : Call) (k : Cap) :
      s.opened = true → s.lock = none → s.pc r = .idle →
      (k = .write → s.registered = true) →
      Step fix s { s with kind := upd s.kind r k,
                          revokedAtBegin := upd s.revokedAtBegin r (!(s.file k)),
                          lock := some r,
                          pc := upd s.pc r .check }
  /-- `Check(r)` -/
  | check (s : State Call) (r : Call) :
      s.pc r = .check →
      Step fix s
        { s with pc := upd s.pc r
                   (if (if fix then s.file (s.kind r) else s.cache (s.kind r))
                    then .prepare else .denied),
                 cache := if fix then s.file else s.cache }
  /-- `Prepare(r)` -/
  | prepare (s : State Call) (r : Call) :
      s.pc r = .prepare →
      Step fix s { s with pc := upd s.pc r .release }
  /-- `Release(r)` -/
  | release (s : State Call) (r : Call) :
      s.pc r = .release →
      Step fix s
        { s with pc := upd s.pc r .released,
                 released := s.released + 1,
                 leakedW := if s.kind r = .write ∧ s.revokedAtBegin r = true
                            then s.leakedW + 1 else s.leakedW,
                 leakedX := if s.kind r = .expose ∧ s.revokedAtBegin r = true
                            then s.leakedX + 1 else s.leakedX }
  /-- `End(r)` -/
  | end_ (s : State Call) (r : Call) :
      (s.pc r = .released ∨ s.pc r = .denied) → s.lock = some r →
      Step fix s { s with pc := upd s.pc r .done, lock := none }

/-- States reachable from `init` in any finite number of steps. -/
inductive Reachable (fix : Bool) : State Call → Prop where
  | init : Reachable fix init
  | step {s t : State Call} : Reachable fix s → Step fix s t → Reachable fix t

/-- P1 `Inv_NoDraftAfterRevoke`. -/
def InvNoDraftAfterRevoke (s : State Call) : Prop := s.leakedW = 0

/-- P2 `Inv_NoConfidentialAfterRevoke`. -/
def InvNoConfidentialAfterRevoke (s : State Call) : Prop := s.leakedX = 0

end McpConfigRevocation
