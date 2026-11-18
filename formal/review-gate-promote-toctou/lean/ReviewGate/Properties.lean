import ReviewGate.System
/-
Frozen property P3 (formal/review-gate-promote-toctou/tla/Properties.tla) and its proof for
every number of drafts, every content and every trace length.
-/
namespace ReviewGate

variable {Note : Type} [DecidableEq Note]

/-- P3 — what is verified is exactly what the human had read when clicking Promote. -/
def VerifiedIsWhatWasRead (s : State Note) : Prop :=
  ∀ n v, s.verified n = some v → s.approved n = some v

theorem upd_same (f : Note → Option Nat) (n : Note) (v : Option Nat) : upd f n v n = v := by
  simp [upd]

theorem upd_other (f : Note → Option Nat) (n m : Note) (v : Option Nat) (h : m ≠ n) :
    upd f n v m = f m := by
  simp [upd, h]

omit [DecidableEq Note] in
/-- P3 holds initially. -/
theorem init_inv (s : State Note) (h : Init s) : VerifiedIsWhatWasRead s := by
  intro n v hv
  have := h.2.2.1 n
  rw [this] at hv
  cases hv

/-- P3 is inductive for the patched Hub: every step preserves it. -/
theorem step_inv (s t : State Note) (h : Step true s t) (inv : VerifiedIsWhatWasRead s) :
    VerifiedIsWhatWasRead t := by
  cases h with
  | rewrite n v w _ => exact inv
  | read n v _ => exact inv
  | click n v _ _ => exact inv
  | refuse n d p _ _ _ _ => exact inv
  | gone n _ => exact inv
  | promote n d p _ _ hchk =>
    intro m v hv
    have hdp : d = p := hchk rfl
    by_cases hm : m = n
    · subst hm
      simp only [upd_same] at hv ⊢
      rw [← hdp]
      exact hv
    · simp only [upd_other _ _ _ _ hm] at hv ⊢
      exact inv m v hv

/-- **Main theorem (P3, unbounded).** In every reachable state of the patched Hub — any set of
drafts, any contents, any interleaving of writers, readers, clicks and promotes — a verified
note has exactly the content the human had read. -/
theorem verified_is_what_was_read (s : State Note) (h : Reachable true s) :
    VerifiedIsWhatWasRead s := by
  induction h with
  | init s hi => exact init_inv s hi
  | step s t _ hst ih => exact step_inv s t hst ih

/-- While the draft differs from what the pending click carried, no step of the patched Hub
changes what is verified for that note (the only possible outcome of the request is 409). -/
theorem no_verify_on_refuse (s t : State Note) (n : Note) (d p : Nat)
    (hd : s.draft n = some d) (hp : s.pending n = some p) (hne : d ≠ p)
    (h : Step true s t) (ht : t.verified n ≠ s.verified n) : False := by
  cases h with
  | rewrite _ _ _ _ => exact ht rfl
  | read _ _ _ => exact ht rfl
  | click _ _ _ _ => exact ht rfl
  | refuse _ _ _ _ _ _ _ => exact ht rfl
  | gone _ _ => exact ht rfl
  | promote m d' p' hd' hp' hchk =>
    by_cases hm : n = m
    · subst hm
      rw [hd] at hd'; rw [hp] at hp'
      cases hd'; cases hp'
      exact hne (hchk rfl)
    · exact ht (upd_other _ _ _ _ hm)

/-! ### The model can fail (sanity): without the check P3 is violated. -/

/-- One draft with content 0. -/
def s0 : State Unit :=
  { draft := fun _ => some 0, shown := fun _ => none, pending := fun _ => none,
    verified := fun _ => none, approved := fun _ => none }

/-- **Bug witness.** Before the patch a reachable state violates P3:
read (0) → writer rewrites (1) → click → promote verifies 1 although 0 was read. -/
theorem unpatched_violates : ∃ s : State Unit, Reachable false s ∧ ¬ VerifiedIsWhatWasRead s := by
  let s1 : State Unit := { s0 with shown := upd s0.shown () (some 0) }
  let s2 : State Unit := { s1 with draft := upd s1.draft () (some 1) }
  let s3 : State Unit := { s2 with pending := upd s2.pending () (some 0) }
  let s4 : State Unit :=
    { draft := upd s3.draft () none, shown := upd s3.shown () none,
      pending := upd s3.pending () none,
      verified := upd s3.verified () (some 1), approved := upd s3.approved () (some 0) }
  have r0 : Reachable false s0 :=
    Reachable.init s0 ⟨fun _ => rfl, fun _ => rfl, fun _ => rfl, fun _ => rfl⟩
  have r1 : Reachable false s1 := Reachable.step s0 s1 r0 (Step.read s0 () 0 rfl)
  have r2 : Reachable false s2 := Reachable.step s1 s2 r1 (Step.rewrite s1 () 0 1 rfl)
  have r3 : Reachable false s3 := Reachable.step s2 s3 r2 (Step.click s2 () 0 rfl rfl)
  have r4 : Reachable false s4 :=
    Reachable.step s3 s4 r3 (Step.promote s3 () 1 0 rfl rfl (fun h => by cases h))
  refine ⟨s4, r4, ?_⟩
  intro h
  have h1 := h () 1 rfl
  have h2 : s4.approved () = some 0 := rfl
  rw [h2] at h1
  cases h1

/-- **Liveness-flavoured sanity.** The patched Hub can still promote: P3 is not satisfied
vacuously by a Hub that never verifies anything. -/
theorem patched_can_promote : ∃ s : State Unit, Reachable true s ∧ s.verified () = some 0 := by
  let s1 : State Unit := { s0 with shown := upd s0.shown () (some 0) }
  let s2 : State Unit := { s1 with pending := upd s1.pending () (some 0) }
  let s3 : State Unit :=
    { draft := upd s2.draft () none, shown := upd s2.shown () none,
      pending := upd s2.pending () none,
      verified := upd s2.verified () (some 0), approved := upd s2.approved () (some 0) }
  have r0 : Reachable true s0 :=
    Reachable.init s0 ⟨fun _ => rfl, fun _ => rfl, fun _ => rfl, fun _ => rfl⟩
  have r1 : Reachable true s1 := Reachable.step s0 s1 r0 (Step.read s0 () 0 rfl)
  have r2 : Reachable true s2 := Reachable.step s1 s2 r1 (Step.click s1 () 0 rfl rfl)
  have r3 : Reachable true s3 :=
    Reachable.step s2 s3 r2 (Step.promote s2 () 0 0 rfl rfl (fun _ => rfl))
  exact ⟨s3, r3, rfl⟩

end ReviewGate
