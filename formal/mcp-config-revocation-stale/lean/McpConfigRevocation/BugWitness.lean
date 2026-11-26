import McpConfigRevocation.Spec

/-!
# Fix OFF witness (mirror of `MC_bug.cfg`): the property can fail.
Trace: Open → Revoke(expose) → Begin(c, expose) → Check (stale cache) →
Prepare → Release ⇒ `leakedX = 1`.
-/
namespace McpConfigRevocation

theorem bug_P2_violated :
    ∃ s : State Unit, Reachable false s ∧ ¬ InvNoConfidentialAfterRevoke s := by
  have h0 : Reachable false (init : State Unit) := Reachable.init
  have h1 := Reachable.step h0 (Step.open_ _ rfl)
  have h2 := Reachable.step h1 (Step.revoke _ .expose rfl)
  have h3 := Reachable.step h2 (Step.begin _ () .expose rfl rfl rfl (by intro h; cases h))
  have h4 := Reachable.step h3 (Step.check _ () (by simp [upd]))
  have h5 := Reachable.step h4 (Step.prepare _ () (by simp [upd, init]))
  have h6 := Reachable.step h5 (Step.release _ () (by simp [upd]))
  exact ⟨_, h6, by simp [InvNoConfidentialAfterRevoke, upd, init]⟩

end McpConfigRevocation
