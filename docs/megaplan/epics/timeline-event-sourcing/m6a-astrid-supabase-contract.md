# Milestone 6a — Astrid Supabase contract slice

## Outcome

Recover M6 into a scope that can actually run in the current cloud workspace.
The worker only has the Astrid checkout; it does not have the canonical
`reigh-app/` tree or top-level `supabase/migrations/`. This milestone therefore
lands the Astrid-side contract, client/backend scaffolding, documentation, and
tests needed for Supabase event-log support without claiming the SQL/RPC or
web-app migration is complete.

The full Supabase SQL/RPC and canonical `reigh-app/` write-path migration must
run later in a workspace that includes those companion trees, or in separate
repo-specific milestones.

## Scope (IN)

1. **Explicit companion-tree blocker.** Add a durable note or doc section that
   records why the previous M6 plan stalled: this checkout lacks
   `reigh-app/` and top-level `supabase/migrations/`, so end-to-end M6 cannot
   be proven here. The doc must name the blocked companion deliverables.
2. **SupabaseBackend contract shape.** Replace pure "inert stub" semantics with
   a real, opt-in client contract for `SupabaseBackend` that can call a future
   `append_timeline_event(...)` RPC when configured. It may use mocked
   transport tests in this repo; do not claim real SQL parity without the SQL
   tree.
3. **Transport/auth carrier.** Define how Supabase URL/auth/actor context flows
   into backend construction. Local timeline edit call sites must continue to
   work without Supabase credentials.
4. **Actor bridge guardrail.** Do not silently forge `actor.id` for human
   writes. If the current PAT/service-role flow cannot prove `auth.uid()`,
   surface a typed unsupported/needs-auth error or documented provisional path
   rather than weakening the server-side actor-validation contract.
5. **Semantic event descriptor seam.** Where Astrid currently shells out to
   `ops_helper.mjs` and receives only a rewritten config blob, add or document
   the event-descriptor contract needed before Python can call an event RPC for
   those edits. If implementation is feasible in this repo, add tests for that
   descriptor shape.
6. **Docs/tests alignment.** Update docs/spec/test expectations that still say
   `preferred_backend="supabase"` means only an inert stub. If behavior remains
   provisional, say exactly what is implemented and what requires companion
   SQL/app work.
7. **Legacy blob-RPC inventory.** Identify Astrid-side callers/tests that still
   assert `update_timeline_config_versioned` as the canonical write path and
   either update them for the new event-first contract or fence them as legacy
   compatibility.

## Anti-scope

- Do not edit `reigh-app/`; it is not mounted in this worker.
- Do not edit top-level `supabase/migrations/`; it is not mounted in this
  worker.
- Do not deploy, rebuild, or restart the Railway service to add extra repos.
- Do not claim `append_timeline_event(...)` SQL/RPC parity has been proven by
  mocked Astrid tests.
- Do not build local-to-Supabase sync/reconcile; m9 owns cross-backend ops.

## Done Criteria

1. Astrid docs clearly distinguish implemented Astrid-side Supabase event-log
   support from blocked companion SQL/RPC and `reigh-app` work.
2. Local-only tests still pass without Supabase credentials.
3. `SupabaseBackend` has an opt-in construction path and typed behavior for
   missing config/auth/RPC support.
4. Tests cover mocked append/read/head/verify behavior or explicitly gated
   unsupported paths, without requiring live Supabase credentials.
5. Docs/spec/tests no longer describe the Supabase backend as only an inert
   stub unless they also explain the new provisional contract.
6. The implementation leaves M7 read-only observability able to run against
   LocalFs and any configured/mocked Supabase backend.

## Follow-Up Companion Work

The original M6 requirements remain real, but they need a workspace with the
right repositories:

- Add `public.timeline_events` and `append_timeline_event(...)` under the
  owning Supabase migration tree.
- Migrate canonical `reigh-app/` write paths, realtime subscriptions, and UI
  history to event-first behavior.
- Prove server-side canonical hashing, idempotency, rate limiting, RLS, and
  actor validation against the actual database/RPC implementation.

