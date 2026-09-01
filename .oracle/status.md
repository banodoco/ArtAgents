# Status — canonical pack beta

- Clarity/reconciliation: **COMPLETE**
- Execution contract: **FROZEN**
- Huge-run policy: **active — 4–6 engineer-weeks**
- Existing Astrid package/product foundation: **substantial and mostly built**
- Canonical-v2 implementation batches: **B1–B3 COMPLETE —
  3/5 checkpoints committed**
- Frozen final criteria: **0/15 end to end; B1–B3 evidence accepted**
- Product state: **22 v2 manifests and canonical database projection prepared;
  production legacy-active**
- Product base: `7ac50c12e8e4d90988fee603ffdb9896e5628792`
- B1 checkpoint: `14f1f7d5f77cb6bd384749941cff6e522b696590`
- B2 checkpoint: `a293e4c416c0e716154c392c0dd43165344f870d`
- B3 checkpoint: `cd4dc91a31e4c7127b4023a87dabfdebea276ff1`
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
- Current Megado phase: **Phase 8 — cumulative gate 1**
- Active batch: **integrated B1–B3 contract/manifest/database-projection and
  cutover-readiness certification before B4**
- Model routing: **Sol owns Megado sequencing and gate decisions; Luna performs
  normal implementation, validation, and bounded independent certification.
  Segment Sol review requires a recorded high-risk reason; final independent
  Sol integrated review remains. No `[XHARD]` task currently exists.**
- Fresh pre-execution review: **PASS after bounded path correction**
- Review cadence: **B1 closed by its recorded intervention. B2–B5 use one
  independent Luna pass by default; blockers receive the smallest correction
  and one affected-criterion delta verification while unaffected passes remain
  valid. No equivalent whole-cycle resets. Cumulative activation/migration/
  integration gates remain.**

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

What is not done is the active canonical-authority cutover: production still
uses the four `schema-pack.yaml` manifests, three fixed default-composition
authorities, and eight unconverged builder/reader consumers. B4 must atomically
activate v2 and delete those alternates; B5 must prove inspection, doctor,
documentation, packaging, clean-wheel, focused/full-suite, and evidence
closure. The frozen goal therefore remains 0/15 end to end.

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

Run cumulative gate 1 over B1–B3 while production remains legacy-active.

Cloud preflight has `build` 1.6.0 installed. B5 still requires its own recorded
isolated validation/build environment and clean-wheel proof.

The separately requested pack-aware `astrid update` command has not started.
It follows this cutover and must preserve user edits and pack-applied database
migrations, using Luna for normal execution and Sol for planning/oracle or
exceptional work.
