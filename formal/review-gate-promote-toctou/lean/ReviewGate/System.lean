/-
MYELIN Hub — Review Gate (read -> click Promote) vs. a writer of the draft.
Lean 4 promotion (W7) of formal/review-gate-promote-toctou/tla/Spec.tla.

What is more general here than in the TLC run:
  * `Note` is an arbitrary type (any number of drafts, also infinitely many),
  * contents are arbitrary natural numbers (any number of rewrites, a rewrite may bring an
    earlier text back),
  * the initial drafts are arbitrary,
  * traces have any length.
Two contents are "the same digest" exactly when they are equal (collision-freeness of the
digest is an assumption, see SCOPE.md).
-/
namespace ReviewGate

/-- Hub + browser + ai-drafts state. `none` = absent. -/
structure State (Note : Type) where
  /-- content of `00_Inbox/ai-drafts/<n>.md` -/
  draft    : Note → Option Nat
  /-- body the Review page shows for `n` -/
  shown    : Note → Option Nat
  /-- Promote request in flight: the content the human had read when clicking -/
  pending  : Note → Option Nat
  /-- content written to `10_Domains/<D>/<n>.md` with status verified -/
  verified : Note → Option Nat
  /-- history: what the human had read for the click that promoted `n` -/
  approved : Note → Option Nat

variable {Note : Type} [DecidableEq Note]

/-- Point update of a per-note map. -/
def upd (f : Note → Option Nat) (n : Note) (v : Option Nat) : Note → Option Nat :=
  fun m => if m = n then v else f m

/-- The Hub starts with some drafts waiting and nothing shown, clicked or verified. -/
def Init (s : State Note) : Prop :=
  (∀ n, s.shown n = none) ∧ (∀ n, s.pending n = none) ∧
  (∀ n, s.verified n = none) ∧ (∀ n, s.approved n = none)

/-- One step. `check = true` is the patched Hub (the click echoes the digest of what was read
and `promote` refuses a draft whose content differs); `check = false` is the Hub before the
patch. Constructors correspond one-to-one to the TLA+ actions. -/
inductive Step (check : Bool) : State Note → State Note → Prop
  /-- WriterRewrite: a skill / MCP write_draft / the editor replaces the waiting draft. -/
  | rewrite (s : State Note) (n : Note) (v w : Nat) :
      s.draft n = some v →
      Step check s { s with draft := upd s.draft n (some w) }
  /-- BrowserRead: "내용 읽기" — GET /api/notes/<path>. -/
  | read (s : State Note) (n : Note) (v : Nat) :
      s.draft n = some v →
      Step check s { s with shown := upd s.shown n (some v) }
  /-- HumanClick: Promote, enabled only after the body was opened. -/
  | click (s : State Note) (n : Note) (v : Nat) :
      s.shown n = some v → s.pending n = none →
      Step check s { s with pending := upd s.pending n (some v) }
  /-- HubPromote, accepted: the draft as it is *now* becomes verified. -/
  | promote (s : State Note) (n : Note) (d p : Nat) :
      s.draft n = some d → s.pending n = some p → (check = true → d = p) →
      Step check s
        { draft := upd s.draft n none, shown := upd s.shown n none,
          pending := upd s.pending n none,
          verified := upd s.verified n (some d), approved := upd s.approved n (some p) }
  /-- HubPromote, refused with 409 (digest mismatch): nothing is verified. -/
  | refuse (s : State Note) (n : Note) (d p : Nat) :
      check = true → s.draft n = some d → s.pending n = some p → d ≠ p →
      Step check s { s with pending := upd s.pending n none, shown := upd s.shown n none }
  /-- HubPromote on a draft that is gone: 404. -/
  | gone (s : State Note) (n : Note) :
      s.draft n = none →
      Step check s { s with pending := upd s.pending n none }

/-- States reachable from an initial state by any finite number of steps. -/
inductive Reachable (check : Bool) : State Note → Prop
  | init (s : State Note) : Init s → Reachable check s
  | step (s t : State Note) : Reachable check s → Step check s t → Reachable check t

end ReviewGate
