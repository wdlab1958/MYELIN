import McpConfigRevocation.Spec

/-!
# Inductive invariant and frozen safety theorems (FIX = TRUE)
-/
namespace McpConfigRevocation

variable {Call : Type} [DecidableEq Call]

/-- Inductive invariant strengthening P1 ∧ P2. -/
structure Inv (s : State Call) : Prop where
  noLeakW  : s.leakedW = 0
  noLeakX  : s.leakedX = 0
  /-- A call revoked at `Begin` still sees the revocation on disk at `Check`
      (revocation is monotone). -/
  checkRev : ∀ r, s.pc r = .check → s.revokedAtBegin r = true → s.file (s.kind r) = false
  /-- A call that passed `Check` was not revoked at `Begin`. -/
  passed   : ∀ r, (s.pc r = .prepare ∨ s.pc r = .release) → s.revokedAtBegin r = false

theorem inv_init : Inv (init : State Call) := by
  refine ⟨rfl, rfl, ?_, ?_⟩
  · intro r h; simp [init] at h
  · intro r h; simp [init] at h

theorem inv_step {s t : State Call} (hI : Inv s) (hs : Step true s t) : Inv t := by
  cases hs with
  | open_ _ => exact ⟨hI.noLeakW, hI.noLeakX, hI.checkRev, hI.passed⟩
  | revoke c _ =>
    refine ⟨hI.noLeakW, hI.noLeakX, ?_, hI.passed⟩
    intro r hpc hrev
    have h := hI.checkRev r hpc hrev
    simp only
    by_cases hc : s.kind r = c
    · subst hc; simp
    · rw [upd_ne _ _ (Ne.symm (Ne.symm hc))]; exact h
  | begin r k _ _ hidle _ =>
    refine ⟨hI.noLeakW, hI.noLeakX, ?_, ?_⟩
    · intro r' hpc hrev
      simp only at hpc hrev ⊢
      by_cases hr : r' = r
      · subst hr; simp at hrev ⊢; exact hrev
      · rw [upd_ne _ _ hr] at hpc hrev ⊢; exact hI.checkRev r' hpc hrev
    · intro r' hpc
      simp only at hpc ⊢
      by_cases hr : r' = r
      · subst hr; simp at hpc
      · rw [upd_ne _ _ hr] at hpc ⊢; exact hI.passed r' hpc
  | check r hchk =>
    refine ⟨hI.noLeakW, hI.noLeakX, ?_, ?_⟩
    · intro r' hpc hrev
      simp only at hpc hrev ⊢
      by_cases hr : r' = r
      · subst hr; simp at hpc; split at hpc <;> simp at hpc
      · rw [upd_ne _ _ hr] at hpc; exact hI.checkRev r' hpc hrev
    · intro r' hpc
      simp only at hpc ⊢
      by_cases hr : r' = r
      · subst hr
        simp only [upd_same, ite_true] at hpc
        cases hf : s.file (s.kind r') with
        | false => simp [hf] at hpc
        | true =>
          cases hb : s.revokedAtBegin r' with
          | false => rfl
          | true => have := hI.checkRev r' hchk hb; rw [hf] at this; cases this
      · rw [upd_ne _ _ hr] at hpc; exact hI.passed r' hpc
  | prepare r _ =>
    refine ⟨hI.noLeakW, hI.noLeakX, ?_, ?_⟩
    · intro r' hpc hrev
      simp only at hpc ⊢
      by_cases hr : r' = r
      · subst hr; simp at hpc
      · rw [upd_ne _ _ hr] at hpc; exact hI.checkRev r' hpc hrev
    · intro r' hpc
      simp only at hpc ⊢
      by_cases hr : r' = r
      · subst hr; rename_i h; exact hI.passed r' (Or.inl h)
      · rw [upd_ne _ _ hr] at hpc; exact hI.passed r' hpc
  | release r hrel =>
    have hb : s.revokedAtBegin r = false := hI.passed r (Or.inr hrel)
    refine ⟨?_, ?_, ?_, ?_⟩
    · simp [hb, hI.noLeakW]
    · simp [hb, hI.noLeakX]
    · intro r' hpc hrev
      simp only at hpc ⊢
      by_cases hr : r' = r
      · subst hr; simp at hpc
      · rw [upd_ne _ _ hr] at hpc; exact hI.checkRev r' hpc hrev
    · intro r' hpc
      simp only at hpc ⊢
      by_cases hr : r' = r
      · subst hr; simp at hpc
      · rw [upd_ne _ _ hr] at hpc; exact hI.passed r' hpc
  | end_ r _ _ =>
    refine ⟨hI.noLeakW, hI.noLeakX, ?_, ?_⟩
    · intro r' hpc hrev
      simp only at hpc ⊢
      by_cases hr : r' = r
      · subst hr; simp at hpc
      · rw [upd_ne _ _ hr] at hpc; exact hI.checkRev r' hpc hrev
    · intro r' hpc
      simp only at hpc ⊢
      by_cases hr : r' = r
      · subst hr; simp at hpc
      · rw [upd_ne _ _ hr] at hpc; exact hI.passed r' hpc

/-- The invariant holds in every reachable state (any number of calls, any
    number of steps) when the fix is ON. -/
theorem inv_reachable {s : State Call} (h : Reachable true s) : Inv s := by
  induction h with
  | init => exact inv_init
  | step _ hs ih => exact inv_step ih hs

/-- **P1** `Inv_NoDraftAfterRevoke` (fix ON, unbounded). -/
theorem P1_noDraftAfterRevoke {s : State Call} (h : Reachable true s) :
    InvNoDraftAfterRevoke s := (inv_reachable h).noLeakW

/-- **P2** `Inv_NoConfidentialAfterRevoke` (fix ON, unbounded). -/
theorem P2_noConfidentialAfterRevoke {s : State Call} (h : Reachable true s) :
    InvNoConfidentialAfterRevoke s := (inv_reachable h).noLeakX

end McpConfigRevocation
