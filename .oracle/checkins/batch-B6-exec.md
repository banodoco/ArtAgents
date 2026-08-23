# Batch B6 execution record — orchestrator family port (T6.1)

Branch `phase-b`. Date 2026-08-22. Executor stealth/ox-alpha.

## T6.1 Port travel/join/edit onto the coordinator

- **One new module:** `astrid/core/integrations/reigh/orchestrator_runner.py`
  (the batch's only new module, per the sync point). Families are DATA:
  `_FAMILY_CHILDREN` maps each family's planned roles to executor-child
  capabilities; slot plans derive purely from
  `orchestrator_transitions.derive_children` via `plan_children`; child
  input is one rule for all families (`child_input`: parent params +
  `{orch_role, orch_index}` marker) so no per-family builders can drift.
- **Gated admission only:** children exist exclusively through the
  executor-only R1 route with the `orch_child_key` deterministic key and
  the server-validated `child_admission` envelope; replay-safe by the
  transition table (receipted key ⇒ same row). The coordinator performs
  zero arbitration of its own.
- **Parent lifecycle per the checked table:** claim / heartbeat /
  explicit complete (`settle_success`, settlement artifact = canonical
  child-key→task manifest) / budget-driven fail (`settle_failure`
  re-claims across kernel SD1 requeues until terminal `failed`). Crash
  replay: `resume()` rebuilds fence AND spec from persisted state alone.
  Supporting change: `_task_summary` now carries the admitted `spec` on
  the polling read (doc 27 §4.1) — without it a restarted executor could
  not re-derive its plan; additive field, existing route tests green.
- **Edit family = single-attempt orchestrator** with explicit parent
  terminal; `plan_children("edit_video_orchestrator") == ()`.

## Per-family conformance journeys (`tests/v10/test_family_journeys.py`, 11 tests)

- join_clips: end-to-end through gated admission (+settlement-replay),
  lost-ack replay same-row, child-failure ⇒ explicit failed parent,
  crash-mid-fan-out replay from persisted state, restart-with-live-lease
  resume (heartbeat-advanced status_version).
- travel_between_images: end-to-end (non-turbo parent derives
  `reigh.travel_orchestrator`), browser request for `travel_segment` ⇒
  403 `child_admission_forbidden` with zero writes, lost-lease mid-fan-out
  replays identical children under attempt 2.
- edit_video_orchestrator: childless plan settles explicitly with zero
  gate traffic; settlement replay stays exactly-one-terminal;
  `edit_video_segment`/`edit_travel_flux` rejected by
  `resolve_child_capability` (allowlist exhaustive).
- Every journey asserts the DC-3 invariants against persisted state:
  child set == planned set, zero duplicate rows, exactly-one parent
  terminal.

## Review-1 deferred items

None touch orchestrators: the B3 record defers nothing in this area
(fixture shape frozen at Review 1 is consumed here unchanged).

## → CUMULATIVE REVIEW 2 — recorded decisions

1. **Edit-family-childless reading CONFIRMED against the goal text.**
   Doc 27 §3.1 worker-child allowlist is exhaustive and names exactly
   five local child types, none `edit_*`; §9:345 lists "join/travel/edit"
   among families to enable, and the goal text ports "edit" as a family —
   consistent only with edit as a single-attempt orchestrator whose
   parent completes explicitly without child admission (the T4.2
   reading). Decision: `_EDIT_PLAN ⇒ ()` stands; any future edit child
   is a public-contract change requiring a new allowlist entry.
2. **Distributed-systems seam holds on product code:** the interleaving
   invariants proven by the B5 harness now hold through the real
   coordinator over real HTTP on all three ported families (journeys
   above), including cross-attempt deterministic-key replay after
   sweeper requeue.

