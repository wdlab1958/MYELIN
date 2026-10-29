---------------------------- MODULE Properties ----------------------------
(* Frozen properties for concern hub-config-stale-cache (G2 — HITL: pending Brian review).  *)
(* Do not weaken. Any change here is a "model change" that the report must state.          *)
EXTENDS Spec

\* P1 (protocol, frozen) — Hub decisions are made on the Domain list currently in myelin.yaml:
\* a promote into a configured Domain is never rejected as "not configured", and a promote
\* into a Domain that is not configured is never accepted.
\* src: PHASE_STATE.md:136 (Backlog: Hub가 myelin.yaml 변경을 재시작 없이 반영하지 못함)
\*      docs/adr/0009-hub-write-policy.md:10 (§3 승격 전제: Domain 이 설정된 것)
\*      README.md:17 (Phase-gated Autonomy: myelin.yaml 이 단일 원천), service.py:554-555
P1_NoStaleDecision == ~badReject /\ ~badAccept

\* P2 (protocol, frozen) — a Settings save never removes a Domain from myelin.yaml:
\* the Hub Settings page cannot edit Domains (Settings.tsx:17-19 spreads `current`), and
\* `add-domain` is the only writer of `domains.extra` (ADR-0004 §2) — so any Domain that
\* disappears on save is a lost update of another process's write.
\* src: docs/adr/0004-myelin-yaml-schema.md:9, README.md:69 (add-domain: 기존 노트 불변),
\*      CLAUDE.md Engineering Rules (사용자 데이터 덮어쓰기 금지), service.py:676-700
P2_NoLostDomain == lost = {}

\* C1 (code-level) — variable domains stay in range.
C1_TypeOK == TypeOK

----------------------------------------------------------------------------
\* Sanity invariants — MUST FAIL (MC_sanity.cfg). They prove the interesting states are reachable:
\* a Domain added by the CLI is eventually accepted by a Hub promote, and a Settings save after
\* a CLI add really happens.
S_NeverAcceptedAdded == accepted = {}
S_NeverAllAdded == file # Doms
=============================================================================
