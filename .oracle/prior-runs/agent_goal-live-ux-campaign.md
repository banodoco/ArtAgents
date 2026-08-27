# Agent Goal — unified execution (megado run)

[North Star](./northstar.md)

## Objective and end-state contribution

Make the kernel task system the **ONE execution path** for every Astrid capability,
retiring the filesystem `run.json` ledger as an authority. This run advances the
North Star by collapsing the two-ledger split into a single event-sourced execution
record: every invocation becomes a kernel run+task with events, receipts, attempts,
and managed outputs; `sdk.invoke` becomes the thin admission wrapper; the FS ledger
becomes a derived projection or disappears.

## North Star link

This run is the direct implementation of the "ONE store and ONE execution path"
pillar: it removes the second ledger and the "consistency by convention" fiction,
and makes every execution observable in the kernel event stream.

## Authoritative inputs and immutable source ref

- Source ref: `b4c70e0ac766c69de0298fa19f3d7fede796a97c` (main @ b4c70e0a), worktree
  `../Astrid-unified-oracle` (branch `oracle-unified-execution`).
- Custody baseline: `.oracle/custody.md`.
- The unified-execution design brief (from the host's earlier exploration) is an
  input artifact; the planner revises it, never treats it as authority.

## In-scope work

1. Completion-contract relaxation: `task.complete` must accept non-media outputs
   (evidence/attachments) without forcing every output into content-addressed media;
   `task_outputs` DDL reviewed and migrated if needed (kernel migration 0002).
2. One generic TaskHandler adapter that invokes the capability runner in-process,
   classifies outputs (media-like → managed media; files → evidence), and completes
   under the relaxed contract — no per-executor adapters.
3. `sdk.invoke` (executor and orchestrator) admits a kernel run+task and executes via
   the generic adapter; every call path that currently writes run.json is rewired.
4. The FS `run.json` ledger: becomes a derived projection of the kernel run or is
   retired; all tests and docs that assert run.json as an authority are migrated.
5. Docs: run-ledger-contract.md v2 (single ledger), SKILL.md, async-completion,
   creating-tools; task-execution claims become true, not "test-wired only."
6. Verification: full suite + empirical process runs (the 20/50-flow pattern) proving
   every invocation lands as a kernel run+task with correct events/receipts.

## Non-goals / open boundaries

- No per-executor TaskHandler adapters (the generic adapter replaces the need).
- No serve/GPU process-supervision infrastructure beyond what the kernel task system
  already provides (leases/attempts) — out of scope unless the design proves it
  blocks unified execution.
- No unrelated kernel changes; the existing verified kernel behavior is the substrate.
- The two existing bespoke adapters (generate_image, timeline_visualize) are kept if
  they add value; the generic adapter must at minimum make them unnecessary for new
  capabilities.

## Authorization boundaries

- **Mutation**: only inside the worktree `../Astrid-unified-oracle`.
- **Commits**: after each passed batch gate; stage only reviewed paths.
- **Sync/promotion**: push `oracle-unified-execution` to origin after the final gate
  passes; merge to main after the final overall review passes — this is recorded
  authorization from the user's standing directive this session ("push everything to
  main" after everything is verified). No other remotes/branches.
- The user's uncommitted in-flight files in the MAIN worktree are protected and must
  never be touched by this run (see custody).

## Model policy (user-declared)

- Normal tasks → `openrouter:stealth/ox-alpha`.
- `[XHARD]` tasks → `openrouter:stealth/ox-alpha` (user-selected for both classes).
- Oracle (planner, check-ins, final review) → `openrouter:stealth/ox-alpha`.
- No automatic switching; a pinned model change requires user approval.

## Done and stop criteria

Done: every capability invocation runs as a kernel run+task (verified by process
runs: events + receipts + terminal status); no code path writes run.json as an
authority; full suite green; docs honest (task execution is real, single-ledger
contract); kernel migration verified; oracle final review PASS.

Stop conditions classified explicitly: `blocked` (missing authority/prereq),
`failed` (reproducible unmet criterion), `undetermined` (insufficient evidence),
`retryable` (owned safe retry), `escalate` (risk/authority exceeds role).

## Final validation

- `pytest tests/` green (host runs the full suite once at the end).
- Empirical process run: invoke ≥6 representative capabilities (media, file-only,
  generation, timeline, orchestrator) → each is a kernel run+task with correct
  events/receipts/terminal state; zero run.json writes as authority.
- `python3 -m astrid --help` + docs-alignment test green.
