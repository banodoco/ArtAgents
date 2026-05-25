# Epic: Harness Polish — get the non-pack core to :chefskiss:

## Vision
A 10-agent adversarial audit (2026-05-25) of the Astrid repo surfaced a consistent set of
gremlins in the **non-pack** code: silent failure-swallowing, dead/zombie code from
incomplete migrations, a `core/ → packs/` dependency inversion, tests that pass while
testing nothing, leaked credentials, and taxonomy/doc drift. This epic cleans the harness
core so that green means green, the layering is enforceable, and every directory name means
what it says.

**Packs are explicitly OUT of scope for the entire epic.** All `astrid/packs/**` findings
(structural drift, triplicate text packs, ghost dirs, manifest field-order, etc.) are
handled separately and must not be touched here except where a pack is an unavoidable
*consumer* of a core interface being changed (and even then, only the minimal call-site
update, never a pack refactor).

## Why an epic (not one sprint)
~5 weeks of work with hard sequential dependencies: you cannot safely refactor `core/`
(m4) or fix subtle runtime bugs (m3) until the tests stop lying (m2), and m2's value
depends on a clean, honest tree (m1). The ordering is the whole point — resist
reordering for "quick wins."

## Milestones
| # | Label | Theme | Tier | Depends on |
|---|---|---|---|---|
| m1 | `hygiene-and-safety` | Secrets out of tree, repo hygiene, lint/type-check turned ON over `astrid/`, stale submodule + npm paths fixed | `solo/light` | — |
| m2 | `test-integrity` | Make green mean green: kill double-execution test, denylist, zombie skips, sleep races | `partnered/full` | m1 |
| m3 | `runtime-correctness` | Fix the real runtime bugs: vanishing events, cursor stalls, swallowed gate errors, the silent-exception sweep, one error model | `premium/thorough/high +prep` | m2 |
| m4 | `dependency-inversion` | Break `core/ → packs/ + orchestrate/`; registry/entry-point lookup; de-dup helpers; break `core↔verify` cycle | `partnered/full/high +prep` | m3 |
| m5 | `taxonomy-cli-docs` | Kill zombie modules, reconcile taxonomy names, split god modules, unify CLI dispatch, docs truth pass | `partnered/full/medium` | m4 |

## Handoff artifacts between milestones
- **m1 → m2:** clean `git status`, no secrets in tree, `ruff`/`mypy` running over `astrid/`
  with a recorded baseline (failures allowed — baseline is the artifact).
- **m2 → m3:** a default test run where every test asserts something; CI green is trustworthy.
  This is the safety net m3/m4/m5 refactor on top of.
- **m3 → m4:** consistent error model documented; every step terminates with an explicit
  event. Refactors in m4 can now rely on failures being visible.
- **m4 → m5:** `core/` has zero imports of `packs/`/`orchestrate/`; an import-linter rule
  (or equivalent test) enforces it. m5's renames/splits happen against enforced layering.

## Non-negotiable constraints
- **No git history rewrites, no force-pushes.** Credential history-scrub and key rotation
  are flagged as **human follow-ups**, not automated (destructive, irreversible).
- **No pack refactors.** See scope note above.
- Each milestone is its own PR; the chain handles branch/PR lifecycle.

## Profile rationale (per megaplan-decision, default-lower-then-audit)
- m1 mechanical → `solo`; `light` because blast radius is low.
- m2 is the **load-bearing exception** to default-lower: its output is the safety net every
  later sprint relies on, so critique+review must be premium → `partnered`.
- m3 carries production-incident stakes (silent run stalls / corrupted event log) → the one
  `premium/thorough` sprint; `+prep` to map the `gate.py` event flow first.
- m4 is architectural but mechanical once mapped (registry pattern is well-known) →
  `partnered//high +prep` rather than `premium`.
- m5 is cross-cutting renames + god-module splits → `partnered`, `medium` depth for the splits.
