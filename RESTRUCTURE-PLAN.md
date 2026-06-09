# Astrid — The Elegant Architecture

*A restructure where both the plan and the result are clean. Every claim is verified against the
real import graph (`/tmp/cycle-results/CY1–CY5`, re-checked against source on 2026-06-09), never
asserted. No shims, no back-compat — every importer, test, and patch-target is rewritten.*

## The one idea

Today the package tree is a lie: **23 cross-package import cycles** exist, and `contracts/` — which
should import *nothing* — reaches up into `timeline`, `executor`, `gateway`, and `project`. But the 23
cycles are not 23 problems. They sort into **four tendencies** — not a clean partition (several cycles
are genuinely mixed, e.g. `project↔task` and `project↔executor` are *both* trapped-leaf and inversion),
but four moves cover every one:

1. **Pure leaf infrastructure trapped inside a domain package** — `project/paths.py` (88 importers,
   imports only stdlib), `project/jsonio.py`, `event_hash`, `sha256_file`, the gateway/run env-var
   constants, the generation taxonomy, a duplicated `ELEMENT_MANIFEST_NAMES`. ~15 of the 23. **Push it down.**
2. **CLI / application orchestration trapped inside a domain package** — `project/cli*.py`,
   `timeline/cli_*.py`, `session/cli_*.py` reaching sideways into each other. ~5 of the 23. **Lift it up.**
3. **A genuine inversion hack** — `executor→orchestrator` (the `video_editing.hype` pipeline pull),
   `task→orchestrator` resolver, `pack→executor/orchestrator` deep-validation. 3 of the 23. **Invert it.**
4. **Genuinely bidirectional domain coupling** — `adapter↔task` (plugin pattern), `session.WriterContext
   ↔ task.append_event` (the shared write path). 2 of the 23. **Accept and document it.**

Push the leaves down, lift the app layer up, invert three hacks, accept two truths — and the tiers
below become true *as a consequence*. That is the whole plan.

## The shape: eight tiers, each importing only downward

```
8  packs/            userland executors & orchestrators
7  sdk/              the one public contract we keep stable
6  cli/  · gateway · integrations        interface / wiring (absorbs the stranded *_cli modules)
5  task/  (+ task/dsl, was orchestrate)  run kernel: gate · plan · run · lifecycle
4  execution/        executor + orchestrator + runtime   (orchestrator ▸ executor, now intra-package)
3  domain/           timeline · session · project · pack · element · generation · theme · audit · adapter
2  _shared/          needs contracts: jsonio · result_manifest · capability_common
1  contracts/        errors · schema · run_status · capability        (a TRUE leaf)
0  foundation/       paths · project_paths · ids(ulid) · env_vars · subprocess_env · atomic_io · hash   (imports nothing)
```

The two-tier base is load-bearing and verified: `foundation/` is stdlib-pure (`paths`, `env_vars`
import nothing from astrid), but `jsonio`/`result_manifest` import `contracts.errors` — so they
**cannot** be tier-0; they sit at tier-2 `_shared/`, above `contracts/`. A single flat "shared"
bucket would re-introduce the cycle. The split is the correctness.

## 1 · The cycle ledger (every cross-package cycle, verified cause → break → real churn)

### Root cause 1 — leaf infrastructure trapped in a domain (push down)

| Cycle | Verified cause | Break | Churn |
|---|---|---|---|
| `project ↔ {task,timeline,session,executor,integrations}` (**5 cycles**) | all route through `project/paths.py` — pure stdlib, **88 importers** | move `project/paths.py` → `foundation/`. **This one move dissolves 5 cycles.** | 🔴 **88** (single highest) |
| `project ↔ {task,timeline,session}` residual | `project/jsonio.py` (imports `contracts.errors`) | → `_shared/` (tier 2, above contracts) | 52 |
| `contracts ↔ gateway` | `_capability_common:58` lazy-imports `gateway.ASTRID_GATEWAY_RESOLVED_PROJECT_ENV` | use `env_vars.ASTRID_GATEWAY_RESOLVED_PROJECT` (already tier-0, **identical value**) | 🟢 **0** |
| `contracts ↔ project` (env) | `_capability_common:24` imports `project.run.project_run_env` | inline `env_vars.ASTRID_PROJECT_RUN` (already tier-0) | 🟢 **0** |
| `util ↔ contracts` | `result_manifest:13` imports `util.hash.sha256_file` | move `sha256_file` → `foundation/hash.py` | low (6) |
| `contracts ↔ timeline` | `contracts/event_hash.py` defines both hashers but reaches back into timeline | **repatriate**: `hash_embedded`→`timeline/…/serialize`, `hash_prepended`→`task/events`; delete `contracts/event_hash.py`; rewrite 1 conformance-test import | 🟢 **3** (not 42 — only 2 call sites + 1 test) |
| `element ↔ pack` | `pack/agent_index:82` imports `element.schema.ELEMENT_MANIFEST_NAMES` — **already duplicated** at `pack/_common:19` and re-exported by `pack/__init__:22` | delete the cross-import, use the local copy | 🟢 **0** (one-line) |
| `model_catalog ↔ generation` | `generation/features.py` hosts taxonomy classes/constants used only by `model_catalog` | move taxonomy → `model_catalog/taxonomy.py`; `features.py` becomes the pack-scanning factory; backends keep `→ model_catalog` (correct) | 45 |
| `contracts ↔ executor` | `_capability_common:74` lazy-imports `executor.BanodocoCatalogConfig` | `BanodocoCatalogConfig` → `Protocol` in contracts (structural typing) | low (2) |
| `result_manifest` → `_shared` (carries the above) | 51 importers, needs `foundation.hash` + `_shared.jsonio` | move with jsonio | 🔴 51 |

### Root cause 2 — app/CLI orchestration trapped in a domain (lift up)

| Cycle | Verified cause | Break | Churn |
|---|---|---|---|
| `timeline ↔ session` | both sides are `cli_*` modules cross-reaching (`timeline/cli_crud` ↔ `session/cli_status/attach/sessions`); domain modules don't participate | lift all `*_cli` modules into a top-level **`cli/`** aggregation tier (6) | MED (~8 files) |
| `project ↔ session/integrations` (CLI half) | `project/cli.py`, `project/cli_handlers.py` reach into `session`, `reigh` | same — `project/cli*` → `cli/` | MED |
| `task ↔ timeline` | `timeline/cli_output` imports `task.run_audit._cost_by_source/_run_status` + `task.events.read_events` | promote the audit helpers to public; timeline CLI calls task (task ▸ timeline) | MED (~3) |

### Root cause 3 — inversion hack (invert)

| Cycle | Verified cause | Break | Churn |
|---|---|---|---|
| `executor ↔ orchestrator` | `executor/runner:75` lazy-pulls `orchestrator.registry` for `video_editing.hype` `runtime_module` (orchestrator→executor is *legitimate*) | thread `pipeline_module` into the request; **orchestrator ▸ executor**. Folding both under `execution/` makes the legit edge intra-package | MED (3 files) |
| `task ↔ orchestrator` | `task/orchestrator_resolver` + `plan_builder` lazy-import `orchestrator.registry` | move `_list_orchestrator_ids` → orchestrator; pass orchestrator-id as a param | MED (~3) |
| `pack ↔ executor` & `pack ↔ orchestrator` | `pack/validate:597,611` lazy-imports executor/orchestrator schema for deep validation | delete it — executor/orchestrator already deep-validate at load time; **execution ▸ pack** | 🟢 1 file (both) |
| `project ↔ executor` | `executor/runner:27` imports `project.run.resolve_required_project_timeline` | move the resolver to the orchestration layer (only 2 callers) | MED (~3) |
| `integrations ↔ timeline` | `timeline/migration:266` lazy-imports `reigh.timeline_io` | `RemoteTimelineLister` Protocol in contracts, inject | MED (~2) |

### Root cause 4 — inherent coupling (accept, document — elegance includes knowing what to leave)

- **`adapter ↔ task`** — textbook plugin/strategy: adapters depend on `task.Step/CostEntry`; `task.gate_dispatch`
  instantiates adapters by name (lazy). Breaking it needs an entry-point registry for negligible gain. **Accept.**
- **`session.WriterContext ↔ task.append_event`** — the session-bound write path *is* one conceptual domain.
  Extract only the shallow bridge (`EVENTS_FILENAME`/`LEASE_FILENAME` + CAS exception types → `contracts/`,
  ~15 importers); leave the `WriterContext` coupling as a documented seam. **Accept the deep half.**

Twenty-three cycles: **18 broken** (8 of them at 🟢 zero/near-zero churn), **2 accepted with a shallow
bridge cut**, **3 dissolved for free** when `project/paths.py` lands in `foundation/`.

## 2 · The new spine (tier 0 + tier 2)

```
core/foundation/  paths  project_paths  ids(ulid — kills the threads/timeline dup)  env_vars  subprocess_env  atomic_io  hash
core/_shared/     jsonio  result_manifest  capability_common        (these legitimately need contracts)
```
`contracts/` then keeps only what it owns (`errors` ⊕ `die` ⊕ `event_log_error`, `schema` ⊕
`schema_validators`, `run_status`, `capability/{runner,schema}`, the two new `Protocol`s) and is a
**verified leaf**.

## 3 · The nesting (verified cohesion, cycle-free; mostly path-preserving)

`gate/ plan/ lifecycle/ operator/ run/ events/` in **task/** · `cli/ edits/ schema/(absorbs validators)`
in **timeline/** · `install/ cli/ validate/ definition/` in **pack/** · `errors/ schema/ capability/` in
**contracts/** · `execution/{executor,orchestrator,runtime}` (tier 4) · `generation/{models,backends,
features}` · drain the 12-module `core/` junk-drawer · `orchestrate/` → **`task/dsl/`** · the stranded
`*_cli` modules → top-level **`cli/`** · `packs/_core`→`system`, `packs/` builtin/external structural ·
**`tests/` mirror the source tree.**

> **A facade module becoming its package `__init__` keeps its dotted path identical — zero churn.** The
> cost lives only in prefix-drops, ejections, and renames (every one sized in §1 and §4).

## 4 · Execution — ordered by *real* churn, not by area

**Who does what — churn is DeepSeek's job, coupling is Opus's.** High-volume mechanical work (facades,
prefix-drops, importer rewrites — *including* the 88-importer `project/paths` move) goes to **DeepSeek**
fans, parallel by package; churn is volume, not difficulty. The four jobs that need judgment — dependency
*inversion* (W3), the densely-coupled `task/` (W4), the umbrellas (W7), and the adversarial review of every
🔴 HIGH move — go to **Opus**. The main thread implements nothing: it briefs, runs the gate below, commits,
sequences — staying lean. (~80% DeepSeek, ~20% Opus.)

**The sense-check gate — every move, before commit:**
1. `ast.parse` all touched files.
2. **symbol-completeness** — every name importable from each affected module/package *before* is still importable *after* (the `symcheck` script; no silent drops).
3. **cycle re-check** — the graph checker confirms **no new** sub-/cross-package cycle. *This is the whole point — a move that re-introduces a cycle is reverted.*
4. **import-smoke** — `import astrid…` resolves tree-wide (catches the one missed importer — the #1 no-shims failure mode).
5. **area suite green**, with pre-existing failures (the 37 docs-fixture / `media/pack.yaml` / inventory FAILs) explicitly excluded.
6. 🔴 HIGH moves additionally get an **adversarial Opus review** (moved-not-rewritten, zero behavior drift) before commit.

Commit explicit paths, never `-A`. **Per-wave gate:** full import-smoke + the union of affected suites.
**End gate (W6):** full suite + re-run the 10-agent beauty audit (does the number finally move?).

- **W0 — Free + near-free.** All path-preserving facade→`__init__` conversions (zero churn). The two 🟢-zero
  cycle breaks (gateway + project-run-env env-var swaps). The element↔pack one-line dedup. `event_hash`
  repatriation (3). ULID dedup. `_cost_by_source`/`_run_status` promotion. Every ≤10-importer prefix-drop/
  rename/merge (`die`/`event_log_error`/`schema_validators` merges, `_common`→`_shared`, `packs/_core`→
  `system`, small core-junk moves). *DeepSeek, parallel by package.*
- **W1 — The foundation (the keystone).** Create `foundation/` + `_shared/`. Move `project/paths`(**88**)
  + `core/paths`(57) + `env_vars` + `subprocess_env` + `atomic_io` + `sha256_file` → `foundation/`; move
  `jsonio`(52) + `result_manifest`(51) + `capability_common` → `_shared/`. **This breaks the entire
  contracts/project cycle web — 8+ cycles at once.** Strictly sequential, re-smoke after each. *DeepSeek; Opus reviews each.*
- **W2 — Medium leaf moves.** `model_catalog↔generation` taxonomy(45), `_utc_now`→`utc_now_seconds`(12),
  `env`→`task/_shared`(21), `cli_contract`(13), `plan_verbs`(15), `run_state/store`(13), `media`→util(15),
  `*_edits`→`edits/`(26), `cli_choices`→`core/cli`(41). One at a time.
- **W3 — Invert the hacks.** `_pipeline_module` inversion, `pack/validate` deep-validation deletion,
  `task→orchestrator` resolver, `project→executor` resolver, the two contracts `Protocol`s. *Opus — judgment.*
- **W4 — `task/` + `orchestrate→task/dsl`(53).** The densest area; accept the `adapter↔task` and
  `session↔task` seams with the shallow bridge cut. *Opus, alone.*
- **W5 — Lift the CLI tier + packs/tests reorg.** Stranded `*_cli` modules → `cli/` (breaks timeline↔session,
  project↔session/integrations CLI cycles); mirror-source test tree; structural builtin/external. *DeepSeek.*
- **W6 — Integration.** Full suite, cross-area fix-pass, re-measure (10-agent audit), **push**.
- **W7 — The umbrellas.** `execution/` (executor 65+30patch, orchestrator 60+15patch — makes the legit
  orchestrator→executor edge intra-package) + `core/registry/` base. Highest blast radius; only after
  W0–6 green; re-validate the internal DAG first. *Opus, step-by-step.*

## 5 · Out of scope (stated once, honestly)

Forward-looking *design*, not structure-cleanup — a separate effort: `sdk/capabilities` + `sdk/verbs`, an
`extension_points`/`hooks` system, `core/logging`/`serialization` consolidation, `@pack_entrypoint`. And
rejected after verification: a `core/asset/` package for the 45-LOC `cas` (→ `task/_shared/`); a flat
single-`shared` tier (re-introduces the contracts cycle — the two-tier split is the fix).

## 6 · How far the confidence actually reaches

The tier model is no longer asserted — it is *constructed* by §1's ledger. But confidence is **staged**,
not uniform, and the plan is honest about where verification stops:

- **The spine (W0–W1) is verified at file:line.** `project/paths.py → foundation` dissolving 5 cycles;
  the two-tier `foundation`/`_shared` split (forced by `jsonio`/`result_manifest` needing `contracts.errors`);
  the 🟢-zero env-var and `ELEMENT_MANIFEST_NAMES` breaks; `event_hash` = 3 files; the executor↔orchestrator
  hack. Checked against source, with two first-draft numbers corrected (`event_hash` 42→3, `paths` 60→88).
  This is trustworthy enough to execute now.
- **The tail (W2–W7) is diagnosed, not yet independently walked.** The `model_catalog`/`generation` taxonomy
  move, the CLI-aggregation cycle breaks, the `execution/` umbrella — these rest on the CY1–CY5 diagnosis plus
  spot-checks, not a file:line trace of every importer. Each is sized and ordered, but its certainty is earned
  *when it lands*, by §4's sense-check gate (symcheck + cycle re-check + import-smoke, every move).

That staging *is* the design: I don't need supreme confidence in W7 today — the per-move gate manufactures it
move by move, and a move that re-introduces a cycle is reverted. The headline holds (23 cycles, four moves,
one keystone) without pretending the long tail is already proven. The plan is one shape you can hold in your
head; the outcome is a tree that teaches its own architecture — and the verification reaches exactly as far as
it claims to, no further. That clears the bar — plan and result both.
