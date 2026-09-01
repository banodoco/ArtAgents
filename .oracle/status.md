# Status — canonical pack beta

- Clarity/reconciliation: **COMPLETE**
- Execution contract: **FROZEN**
- Huge-run policy: **active — 4–6 engineer-weeks**
- Existing Astrid package/product foundation: **substantial and mostly built**
- Canonical-v2 implementation batches: **B1 GATE PASS; checkpoint commit
  pending — 0/5 committed**
- Frozen final criteria: **0/15 end to end; B1 isolated evidence accepted**
- Product candidate: **30 frozen source/test/fixture paths**
- Base/current HEAD: `7ac50c12e8e4d90988fee603ffdb9896e5628792`
- Branch: `megado/canonical-pack-beta`
- Worktree:
  `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
- Remaining estimate: **4–6 engineer-weeks** for one senior engineer
- Local execution preflight: **PASS but superseded by cloud venue** — approved
  VibeComfy cache removed; 3.5 GiB free; temp-file and isolated-venv probes
  pass. No further laptop cache deletion is needed for this project.
- Cloud execution preflight: **PASS** — exact checkout/overlay and zero product
  diff proved; 233 GiB free, 16 CPUs, 26 GiB available RAM; Python/git/OMP and
  dependencies green; exact Luna/Sol wrapper routes green; authorized push
  dry-run green; inherited focused baseline `179 passed`.
- Goal state: **ACTIVE**
- Current Megado phase: **Phase 5 — B1 checkpoint preparation**
- Active batch: **candidate 46 bounded delta PASS; B1 accepted under user
  control from two unaffected candidate-45 Luna passes plus the sole
  erased-metadata delta verification; no finite blockers**
- Model routing: **Sol owns the Megado run and gate decisions; Luna performs
  normal bounded work and independent reviews; later batches retain separate
  Sol oracle dispositions. B1's user-directed finite delta closure is recorded
  above; no `[XHARD]` task currently exists.**
- Fresh pre-execution review: **PASS after bounded path correction**
- Review cadence: **B1 closed by the recorded user intervention; B2–B5 retain
  three Luna passes plus one Sol disposition, with cumulative gates after B3
  and B4**

## What “mostly done” means

Most underlying functionality was already implemented before this run:

- 18 of the 22 target product directories already have v1 capability-pack
  manifests;
- all 64 executors, 12 orchestrators, and 10 elements are already discovered
  from domain packs;
- 17 of 22 product packs already have direct skills (`_core` has its separate
  guidance skill); and
- timeline, shots, references, and Runaway already have real SQLite migrations,
  repositories, product behavior, and operational support. The migration
  engine, writer/UoW, SDK wiring, doctor, and backup/restore also exist.

What is not done is the new canonical-authority cutover: there is no active v2
catalog, the four database slices still use separate `schema-pack.yaml`, three
fixed default-composition authorities remain, eight builder/reader consumers
have not converged, five direct product-pack skills are missing, and wheel
closure has not been proved. Therefore the existing foundation is mostly built
while the specifically requested v2 cutover remains 0/5 and 0/15.

## Execution authority

1. `.oracle/agent_goal.md` — frozen scope and 15 exact done criteria.
2. `.oracle/northstar.md` — durable end state.
3. `.oracle/implementation-ledger.md` — verified current state and history.
4. `.oracle/tasklist.md` — exact executable items and gates.
5. `.oracle/plan.md` — concise five-batch sequence.

The former 2,317-line plan is archived at
`.oracle/prior-runs/canonical-pack-overgrown-plan.md` and is non-executable.
The storyboard `evidence/final-matrix.md`, top-level batch check-ins,
`briefs/pre-exec-review.md`, and `execution.log` are also historical residue,
not evidence that this canonical-pack product cutover ran.

## Correct next action

Commit the reviewed B1 checkpoint, record its SHA and receipts in repo/ledger,
then begin B2. No candidate 47 or additional B1 review/oracle dispatch.

Cloud preflight has `build` 1.6.0 installed. B5 still requires its own recorded
isolated validation/build environment and clean-wheel proof.

The separately requested pack-aware `astrid update` command has not started.
It follows this cutover and must preserve user edits and pack-applied database
migrations, using Luna for normal execution and Sol for planning/oracle or
exceptional work.
