# Status — canonical pack beta

- Clarity/reconciliation: **COMPLETE**
- Execution contract: **FROZEN**
- Huge-run policy: **active — 4–6 engineer-weeks**
- Existing Astrid package/product foundation: **substantial and mostly built**
- Canonical-v2 implementation batches: **B1 COMMITTED; B2 GATE PASS —
  1/5 checkpoints committed**
- Frozen final criteria: **0/15 end to end; B1–B2 evidence accepted**
- Product candidate: **B2 frozen 35-path delta over B1 control HEAD**
- Product base: `7ac50c12e8e4d90988fee603ffdb9896e5628792`
- B1 checkpoint: `14f1f7d5f77cb6bd384749941cff6e522b696590`
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
- Current Megado phase: **Phase 6 — B2 checkpoint preparation**
- Active batch: **independent Luna certification PASS: 22 strict v2 packs,
  64/12/10 census, four database declarations, 22 skills, confined resources,
  zero-unclassified coverage, production legacy-active**
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

Commit the reviewed B2 checkpoint, record its SHA and receipt set, then begin
B3 database projection without activating production authority.

Cloud preflight has `build` 1.6.0 installed. B5 still requires its own recorded
isolated validation/build environment and clean-wheel proof.

The separately requested pack-aware `astrid update` command has not started.
It follows this cutover and must preserve user edits and pack-applied database
migrations, using Luna for normal execution and Sol for planning/oracle or
exceptional work.
