# Astrid `core` import tiers

The `astrid.core` package is layered. **Each tier imports only downward.** This is enforced by
`scripts/reshape/import_cycles.py` (run in CI / pre-commit): it builds the static import graph and fails
on any *new* cross-package cycle. The restructure that established this drove cross-package import cycles
from **24 → 6** (the 6 are documented & accepted below).

```
6  cli/                 top-level CLI aggregation — may import any domain downward
5  task/  (run kernel)  gate · plan · lifecycle · operator · run · events
4  executor · orchestrator · runtime · generation · model_catalog    (execution / capability layer)
3  domain/              timeline · session · project · pack · element · theme · audit · adapter · integrations
2  _shared/             jsonio · result_manifest · capability_common   (leaves that legitimately need contracts)
1  contracts/           errors · schema · run_status · capability      (a TRUE leaf — imports only itself + stdlib)
0  foundation/          paths · project_paths · env_vars · subprocess_env · atomic_io · hash   (stdlib-pure)
```

- **tier 0 `foundation/`** imports nothing from `astrid` — pure stdlib leaves. The keystone of the layering.
- **tier 1 `contracts/`** is a verified true leaf: it imports only `astrid.core.contracts` (itself) + stdlib.
- **tier 2 `_shared/`** holds leaves that need `contracts` (e.g. `jsonio`, `result_manifest`) — so they sit
  *above* contracts, not in foundation. A single flat "shared" tier would re-introduce the contracts cycle;
  the foundation/_shared split is the correctness.
- **tier 6 `cli/`** is an aggregator: it may import many domains downward. CLI orchestration was lifted here so
  domains stop importing each other through their CLI layers.

## Accepted cycles (6) — genuine bidirectional domain coupling

Elegance includes knowing what to leave. These six 2-cycles are **intentional** — two concepts that legitimately
know about each other, where breaking the cycle would require an artificial registry/Protocol threaded through
many call sites for negligible architectural gain. The cycle checker's baseline encodes them; only *new* cycles fail.

| Cycle | Why it's genuine (not a hack) |
|---|---|
| `adapter ↔ task` | Plugin/strategy pattern: adapters depend on `task.Step`/`CostEntry`; `task.gate_dispatch` instantiates adapters by name. |
| `session ↔ task` | The shared event-write path: `session.WriterContext` ↔ `task.append_event`. (Has a known cold-import-order sensitivity — real entry points load `task` first.) |
| `project ↔ task` | A project run may be *hosted by* a task step (`project.run` uses `task.env`/`step_dir_for`); a task step *produces* project runs (task consumes project's `current_run`/`schema`/`run`). |
| `project ↔ timeline` | A run and its timeline co-own the contributing-run binding: `project.run` resolves/creates/records into its timeline; `timeline.defaults`/`crud` load/validate the parent project. |
| `orchestrator ↔ task` | `task` resolves orchestrator ids and loads orchestrator-defined plan builders; `orchestrator` consumes task run-state. The id-listing helper's consumers span both `session` and `task`, and `orchestrator` already imports `session.config` — relocating it would create a worse `session↔orchestrator` cycle. |
| `element ↔ project` | Active-theme resolution: `element.catalog.resolve_active_theme` reads project config; `project.run` resolves the active theme for the run env. Both lazily mediate the `theme` concept; the resolver needs *both* project (config) and theme (dirs), so it can't sit below either, and `project` already imports `theme`. |

## Optional, deferred (post-launch polish, no cycle/correctness impact)

- **`execution/` fold** — co-locating `executor` + `orchestrator` under one `execution/` package (aesthetic;
  the `executor↔orchestrator` cycle is already broken — the pipeline runtime module is now a declarative
  `metadata.pipeline_module` manifest field).
- **`task/` internal nesting** — `gate/ plan/ lifecycle/ operator/ run/ events/` subpackages (intra-package only).
- **Cosmetic tidy** — `env_vars`/`subprocess_env` already behave as tier-0; facade→`__init__` conversions.
