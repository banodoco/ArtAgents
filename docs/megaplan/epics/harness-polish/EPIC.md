# Epic: Harness Polish — get the non-pack core to :chefskiss:

## Vision
A 10-agent adversarial audit (2026-05-25) of the Astrid repo surfaced a consistent set of
gremlins in the **non-pack** code: silent failure-swallowing, dead/zombie code from
incomplete migrations, a `core/ → packs/` dependency inversion, tests that pass while
testing nothing, leaked credentials, and taxonomy/doc drift. A second 10-agent pass then
critiqued *this plan* (incompleteness, adjacent scope, duplicated conventions, missing
abstractions, cosmetic-vs-fundamental, sequencing, pack-boundary reality, verifiability,
right-sizing); its findings are folded into the briefs below.

This epic cleans the harness core so green means green, the layering is enforceable, and
every directory name means what it says.

**Packs are OUT of scope for the entire epic** — with two precisely-named exceptions
established by the plan critique:
1. **m1** removes the dead `seinfeld` submodule reference (a dangling ref, not a pack).
2. **m4** is allowed a *tightly-scoped pack-side seam* (see below) because the tool-discovery
   surface physically lives in `astrid/packs/` and the manifests lack the callable metadata
   core needs. This is the only place pack files are edited, and only for registration metadata
   + code-motion — never pack logic.
Everything else under `astrid/packs/**` is untouched.

## Why an epic (not one sprint)
~5–6 weeks of work with hard sequential dependencies: you cannot safely refactor `core/`
(m4) or fix subtle runtime bugs (m3) until the tests stop lying (m2), and m2's value
depends on a clean, honest tree (m1). The ordering is the whole point — resist
reordering for "quick wins."

## Milestones
| # | Label | Theme | Tier | Depends on |
|---|---|---|---|---|
| m1 | `hygiene-and-safety` | Secrets/artifacts out of tree, repo hygiene, lint advisory lane, stale submodule + npm paths — **plus the folded contributor-onboarding fixes** (declare `runpod_lifecycle` + dep-audit via `doctor`, `[project]` in pyproject, one env story, wire `doctor` into CI) **and the trivial user gremlins** (unknown-command→error guard, README invocation fixes) | `directed/light` | — |
| m2 | `test-integrity` | Make green mean green: kill double-execution test, denylist, zombie skips, sleep races; named guard tests | `directed/full` | m1 |
| m3 | `runtime-correctness` | Real runtime bugs via a single `_finalize_step` choke-point; full silent-except/assert inventory + one error model (designed in prep, derived from the existing pattern); threads/ liveness verdict | `premium/thorough/high +prep` | m2 |
| m4 | `dependency-inversion` | Break `core/ → packs/ + orchestrate/` by extending the existing registry + a sanctioned discovery seam; de-dup helpers; break `core↔verify` cycle; enforce layering | `directed/full/high +prep` | m3 |
| m5a | `deadcode-docs` | Kill zombie modules (non-CLI) + install HA3's migration-completion guard, docs truth pass + one canonical plan doc. **Taxonomy renames are HANDED to the pack-taxonomy epic — not done here.** | `directed/full/low` | m4 + pack-taxonomy m4 merged |
| m5b | `structure-split-cli` | Split god modules (timeline.py, lifecycle.py) along named seams; unify CLI dispatch; **absorb the deferred m4 lifecycle.py + pipeline.py de-inversion** | `partnered/full/high` | m5a |

## The m4 inversion design (decided — Protocol-in-core, dynamic resolution)
The goal is "`core/` resolves tools without a *static* `import astrid.packs.*`." The clean inversion:
- **Define a `PackResolver` Protocol in `core/`** (e.g. `resolve(orchestrator_id) -> OrchestratorFactory`).
  Core depends on this abstraction, never on concrete packs.
- **Resolve via manifest metadata + dynamic import.** Callers stop doing
  `import astrid.packs.builtin.orchestrators.hype.plan_template` and instead resolve by id and load via
  `importlib.import_module(manifest.runtime_module)` — dynamic/string-based, so the import-linter (which checks
  *static* imports) stays green. This requires adding `runtime.entrypoint`/`runtime.callable` (or a `plan_template`
  key) to the three orchestrator manifests (`hype`, `event_talks`, `thumbnail_maker`) and the youtube executor
  manifest — **the one sanctioned pack-side edit** (metadata only, no pack logic). The youtube manifest's
  `metadata.runtime_module` mismatch (points at `run.py`, callable is in `…src.social_publish`) is fixed by these fields.
- **Discovery stays in packs implementing the Protocol; inject it at the entrypoint.** `agent_index`'s
  manifest-scanning is generic; it implements `PackResolver` and is wired in at the composition root
  (`__main__`/`pipeline`). No need to drag pack-aware code into `core/`. (Rejected the earlier "move discovery
  into core" option — HA1 correctly flagged it as the wrong direction.)
- For hype's module-level `build_pool_steps`/`STEP_ORDER` (`runner.py:39`): expose a `get_step_registry()` the
  manifest declares, **or** whitelist that single import. Decide in m4 prep.
- The **DI-threading** through `lifecycle.py` lands in **m5b** (where lifecycle.py is split) — m4 only sets up the
  Protocol, the dynamic-resolution for `runner.py`, and the entrypoint scaffolding; it exempts `lifecycle.py`/`pipeline.py`.

The import-linter contract permits exactly the dynamic-resolution pattern + the one sanctioned manifest seam.

## Cross-epic collision reality (verified 2026-05-25)
A portfolio audit + direct repo verification established:
- **timeline-event-sourcing epic is DORMANT** — never run as a chain (no `epic/timeline/*` branches, no
  chain state). Its event-sourcing *kernel* (`core/timeline/events/schema/`, `eventlog/`) already landed via
  the reshape sprint series (PR #32). So m3's `core/timeline/events/schema/types.py:1027` edit touches a
  **stable landed file**, not one being recreated — no collision. The top-level `astrid/timeline.py` kitchen
  sink (m5b's split target) is the *old, independent* model; splitting it is low-risk while the epic stays dormant.
- **pack-taxonomy epic is LIVE** — m1–m3 merged to `main` (#39/#40/#41); **m4 (physical pack migration) is
  in-flight right now**. This is the real collision surface. pack-taxonomy owns taxonomy + pack file locations.
- **Audit line numbers are partially STALE** — `pipeline.py` no longer statically imports concrete packs at the
  cited lines (pack-taxonomy has been moving them). **m4 and m5b prep MUST re-baseline against the post-migration tree.**

## Sequencing decisions (collision-aware)
- **m1 + m2 + m3 are safe to run now** — they touch `.gitignore`/`pyproject`/`package.json`/`tests/` and the
  task-run engine (`gate.py`/`pipeline.py` runtime bugs), none of which pack-taxonomy m4 is moving. m3's timeline
  touchpoint is moot (see above).
- **m4 waits for pack-taxonomy m4 to MERGE to `main`** — harness-polish m4 inverts `agent_index`/manifests/caller
  imports, the exact files pack-taxonomy m4 is migrating. Run m4 after that merge and re-baseline in prep.
- **m5a runs the dead-code + docs subset now; its taxonomy renames are HANDED to pack-taxonomy** (that epic owns
  taxonomy and is actively working it). Don't duplicate/fight it.
- **m5b waits** for pack-taxonomy m4 (pipeline.py/CLI) to settle; re-baseline. timeline.py split stays low-risk.

## Architectural ambition (decided)
This epic stays **scoped to de-gremlining** — it does NOT take on the north-star topology (harness/`core` vs
tools/`packs` vs a `cli/` layer) or defining an `astrid/__init__.py` public API surface. HA1's "symptom-chasing"
critique is acknowledged: those are real, but belong in a **dedicated future architecture epic**, not bolted onto
a cleanup (which would deepen the pack-taxonomy collision). m5b splits the two named god modules along real domain
seams without trying to re-layer all of `astrid/`.

## Sequencing decisions from the plan critique
- **m4 defers the `lifecycle.py` and `pipeline.py` de-inversion to m5b**, which splits/restructures
  those same files — doing the import rewrite *during* the split avoids a guaranteed merge conflict
  and lands the de-inverted imports in the correct sub-modules. m4 does the registry groundwork,
  the easy de-inversions (`executor/runner.py`), the dedup, and the contract — exempting
  `lifecycle.py`/`pipeline.py` with a tracked TODO that m5b completes.
- **m5 is split into m5a (cheap: taxonomy/dead-code/docs) and m5b (god-module splits + CLI).**
  All `pipeline.py`/`packs/cli.py` edits live in m5b so only one milestone touches those files.

## Handoff artifacts between milestones
- **m1 → m2:** clean `git status`, no secrets in tree, `ruff`/`mypy` running over `astrid/` **as an
  advisory CI lane (allow-failure or baseline-compare) so it does not turn m2–m5b red under
  `stop_chain`**, with a recorded baseline + a short note on *why* `astrid/` was excluded.
- **m2 → m3:** a default test run where every test asserts something; CI green is trustworthy.
  Real product bugs found in m2 are listed in EPIC handoff and handed to m3.
- **m3 → m4:** `docs/error-model.md` documenting the (now-enforced) convention; every step
  terminates with an explicit event via `_finalize_step`; **an explicit written verdict on
  `threads/` liveness** (dead → m5a removes it; keep-minimal → m5a keeps only the lineage surface).
- **m4 → m5a/m5b:** `core/` imports no `packs/` (except the named seam) or `orchestrate/`; the
  import-linter contract is green and exempts `lifecycle.py`/`pipeline.py` with a TODO for m5b.

## Non-negotiable constraints
- **No git history rewrites, no force-pushes.** Credential history-scrub and key rotation are
  flagged as **human follow-ups** (in the PR body + this EPIC), not automated.
- **No pack logic changes.** Only the m1 submodule ref and the m4 sanctioned seam touch pack paths.
- Each milestone is its own PR; the chain handles branch/PR lifecycle. `merge_policy: review`.
- **Done criteria must be mechanically checkable** (named test / grep-returns-empty / line-cap /
  command-exits-0) — an unattended `auto_approve` run must not be able to claim a deliverable it
  didn't land.

## Open security follow-ups

The following credential exposures were confirmed in tracked Git history during
the m1 hygiene audit. These are **human-action follow-ups** — no automated rewrite
of history is permitted per the non-negotiable constraint above.

### Tracked-history credential exposure

| Credential | Exposure | Rotation required |
|---|---|---|
| `FAL_KEY` | Tracked in Git history (committed in prior revisions) | Yes — rotate at [fal.ai dashboard](https://fal.ai/dashboard) |
| `FIREWORKS_API_KEY` | Tracked in Git history (committed in prior revisions) | Yes — rotate at [Fireworks AI dashboard](https://fireworks.ai/api-keys) |

### Required human actions

1. **Key rotation — fal.ai**: Log into the [fal.ai dashboard](https://fal.ai/dashboard) →
   API Keys → delete any keys whose values appear in Git history → create new keys
   with minimum required scope. Reference: [fal.ai authentication docs](https://fal.ai/docs/api-reference/platform-apis/authentication)
   (rotate keys regularly, scope to least privilege).

2. **Key rotation — Fireworks AI**: Log into the [Fireworks AI dashboard](https://fireworks.ai/api-keys) →
   API Keys → revoke any keys whose values appear in Git history → create new keys.
   Reference: [Fireworks AI key management](https://fireworks.ai/api-keys).

3. **Manual history-scrub review**: Conduct a targeted review of Git history for
   any remaining credential exposure beyond the two named keys, without rewriting
   history. The review must confirm that:
   - No additional secrets (AWS keys, RunPod tokens, Supabase keys, etc.) are
     embedded in historical commits.
   - The `.env.example` template remains the only env-file tracked (no real `.env`
     with live values).
   - Any findings are addressed by key rotation in the vendor dashboard (not by
     history rewrite).

4. **PR body inclusion**: The m1 PR description must include this security
   follow-ups section so reviewers are aware of the outstanding human actions
   before merge.

### Status

- [ ] `FAL_KEY` rotated in fal.ai dashboard
- [ ] `FIREWORKS_API_KEY` rotated in Fireworks AI dashboard
- [ ] Manual history-scrub review completed
- [ ] PR body includes security follow-ups

## Profile rationale (per megaplan-decision, default-lower-then-audit)
- m1 mechanical → `solo`; `light` (low blast radius).
- m2 → `directed`: the bugs are diagnosed to exact line numbers; it's test-harness execution, not
  novel reasoning. `full` robustness still catches handoff gaps. (Downgraded from `partnered` on
  right-sizing review.)
- m3 carries production-incident stakes (silent run stalls / corrupted event log) → the one
  `premium/thorough` sprint; `+prep` to map the `gate.py` event flow and design the error model first.
- m4 → `directed/full/high +prep`: once prep enumerates the imports, the work is mechanical
  find-replace + one design call (neutral home + the seam); `high` depth + `+prep` cover the design.
  (Downgraded from `partnered` on right-sizing review.)
- m5a → `directed`: renames, deletions, doc edits — low residual complexity.
- m5b → `partnered/full/high`: god-module splits along real domain seams + CLI unification + the
  deferred de-inversion is genuinely cross-cutting and benefits from premium critique/review.

## Cross-references

- [Root EPIC.md](../../../EPIC.md) — m3 handoff entries surfaced during m2 test-integrity work (denylist removals, strict xfails, deferred product bugs).
