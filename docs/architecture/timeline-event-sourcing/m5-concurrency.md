# Milestone 5 — Concurrency + locking

> **DRAFT** — flesh out before this milestone inits. This sprint turns the m1 `expected_version` field into a real protocol contract; LocalFs enforces it immediately and Supabase enforces it when m6 replaces the stub.

## Outcome

Enable optimistic concurrency through the same `--expected-version` argument and `EventLogBackend.append_event(timeline_id, kind, payload, *, actor, expected_version=None, txn_id=None) -> TimelineEvent` contract. LocalFs gets file-version CAS guarded by `fcntl`. `SupabaseBackend` keeps the same public signature and typed stale/not-implemented surface while remaining a stub until m6, where the real RPC enforces the contract server-side.

This is smaller than the original plan because reigh-app already has CAS vocabulary and versioned writes. The goal is not to invent a second mechanism; it is to make event appends use the same expected-version semantics everywhere.

## Scope (IN)

- Add `--expected-version <N>` to m2/m3 CLI mutation verbs.
- Ensure every Python mutation API passes `expected_version` through to `EventLogBackend`.
- Define version semantics: expected version should mean current event-log version/event count. Any temporary mapping to existing Supabase `config_version` is documented for m6's migration window, not implemented as a real Supabase write path in m5.
- `LocalFsBackend` enforces CAS while holding the file lock. If `expected_version` is present and does not match head version, append fails with a typed stale-version error.
- Add a local head/version file field if m1 did not already include one, and verify it against the log when needed.
- Add optional soft locks as events: `timeline.locked` and `timeline.unlocked`, including actor, TTL, and reason.
- Add transaction shape for compound operations: shared `txn_id` on multiple events, with an API such as `begin_txn(...)` if the planner confirms the need before m6. Atomicity requirements must be explicit for LocalFs JSONL.
- Improve conflict reporting enough for tests and future m7 commands: stale head, current version, expected version, and last event summary.

## Anti-scope

- Reigh-app database migrations or RPC implementation; m6 owns them.
- Automatic conflict resolution or CRDT merge.
- Local/Supabase sync.
- Heavy observability UI; m7 owns user-facing history/diff/audit.
- Cross-host locking for LocalFs beyond filesystem semantics available on the current machine.

## Locked Decisions

- The public concurrency knob is `expected_version` across CLI, Python API, LocalFs, and the SupabaseBackend interface.
- Omitted `expected_version` remains allowed for compatibility and single-agent flows unless the planner finds an existing command where strict CAS is already expected.
- A stale write must fail cleanly and leave the log/hash chain unchanged.
- LocalFs physical safety uses `fcntl`/file locks; semantic safety uses version comparison.
- Soft locks are advisory events, not a replacement for CAS.
- Supabase will enforce version/hash chain server-side in m6; m5 adapts interfaces/stubs and tests around the contract without making SupabaseBackend real.

## Open Questions

- Does version mean event count exactly, or a separately stored monotonically incremented integer?
- Should CLI mutations default to current HEAD when `--expected-version` is omitted, or append without CAS? Backcompat leans toward append without CAS plus a warning in docs.
- What is the lock TTL default and should it be configurable per project?
- How should a process recover from a partial LocalFs transaction if it crashes after writing one event in a multi-event txn?
- Are transactions required before m6, or can semantic batched events avoid most multi-event atomicity needs?
- How should `timeline.locked` interact with Supabase auth/user presence later?

## Constraints

- CAS checks must happen inside the same critical section as append for LocalFs.
- Stale-version errors must be typed and testable, not string-matched generic exceptions.
- Soft lock checks cannot make local-only commands require network or Supabase.
- Transaction metadata must preserve the m1 event envelope and not introduce backend-specific fields.
- Stress tests should be bounded and reliable on developer laptops.

## Done Criteria

- CLI mutation verbs accept `--expected-version` and pass it through.
- Python edit APIs accept/pass `expected_version`.
- `LocalFsBackend` rejects stale writes without changing `assembly.jsonl` or head cache.
- Concurrent LocalFs stress tests produce an unbroken hash chain.
- Soft lock events can be emitted, read, and respected by local mutation commands.
- Supabase stub exposes the same expected-version argument and typed stale/not-implemented surface.
- Existing tests from m1-m4 still pass.

## Touchpoints

**Likely new/modified files:**

- `astrid/core/timeline/eventlog/protocol.py` — expected-version error contract.
- `astrid/core/timeline/eventlog/types.py` — stale error/head/lock event types.
- `astrid/core/timeline/eventlog/local_fs.py` — CAS, local lock, transaction handling.
- `astrid/core/timeline/eventlog/supabase.py` — keep interface aligned for m6.
- Edit API modules from m2/m3 — accept/pass `expected_version`.
- Current `astrid timelines` CLI command module — add flags and errors.
- Timeline eventlog concurrency tests.

**Reference reads:**

- Existing lock/session code if Astrid has local lock helpers.
- Reigh-app investigation notes in the m6 brief for `config_version` and `update_timeline_versioned(...)`.
