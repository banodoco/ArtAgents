# Restructure — execution ledger

Durable progress record for executing `RESTRUCTURE-PLAN.md`. Survives context compaction.
**After every move/wave: update this file, then commit.** This is the source of truth for "where am I".

## Mandate (from the user, 2026-06-09)
1. Execute `RESTRUCTURE-PLAN.md` end-to-end **directly** (DeepSeek fans for churn, Opus for coupling,
   main thread gates/commits). **NOT** wrapped in a megaplan.
2. THEN run the **capability-waist** megaplan epic (`docs/migration/capability-waist/chain.yaml`) on top.
3. THEN set up an hourly `/loop` to babysit the epic and unblock anything (incl. fixing the megaplan repo).

## Branch / venue
- Working branch: **`astrid-capability-waist`** (= `main` + 12 commits; it is the epic's `base_branch`).
- Restructure commits land here; the capability-waist chain bases from here, so it builds "on top".
- Live megaplan workers exist but on `/private/tmp/arnold-target` (the **arnold** repo) — they do NOT
  touch this Astrid tree. Still: commit **explicit paths only, never `git add -A`**.

## Gate (every move, before commit) — see RESTRUCTURE-PLAN §4
1. `ast.parse` touched files.
2. symbol-completeness (symcheck) — no silent drops.
3. **cycle re-check**: `python3 -m scripts.reshape.import_cycles --baseline scripts/reshape/baselines/import_cycles.json` → exit 0 (no NEW cycle). After a wave that *fixes* cycles, re-snapshot the baseline.
4. import-smoke: `import astrid…` resolves tree-wide.
5. area suite green (exclude the 37 known pre-existing FAILs: docs-fixture / media/pack.yaml / inventory).
6. 🔴 HIGH moves: adversarial Opus review (moved-not-rewritten).

## Measurement
- Cross-package cycles **baseline: 24** (top granularity) → target floor **~2** (adapter↔task, session↔task accepted).
- Tests collected baseline: **5451**.
- Update the cycle number after each wave.

## Wave status
| Wave | What | Model | Status | Cycles after |
|---|---|---|---|---|
| Scaffold | cycle checker + baseline + ledger | main | ✅ done | 24 |
| W0a | break contracts↔{gateway,project,timeline} (env-var swaps + event_hash repatriation) | Claude(Opus) sub | ✅ done | 21 |
| W0b | break element↔pack (local _common dedup) | main | ✅ done | 20 |
| W0c | facade→__init__ conversions + env_vars/subprocess_env/atomic_io→foundation (PURE TIDY, no cycle impact) | Claude sub | ⬜ DEFERRED to late cleanup pass | — |
| W1a | foundation/ + paths keystone: extract executor-argv from core/paths→executor (broke executor↔paths), core/paths→foundation/paths (57), project/paths→foundation/project_paths (88), sha256_file→foundation/hash (173 files) | Claude(Opus) sub | ✅ done | 19 |
| W1b | _shared/ (jsonio, result_manifest, capability_common) + atomic_io→foundation + banodoco relocation. **contracts is now a PRISTINE TRUE LEAF.** Broke contracts↔executor + contracts↔util. SCC 18→12 nodes. | Claude(Opus) sub | ✅ done | 17 |

> **Tiers 0/1/2 are now clean.** foundation/ (stdlib-pure), contracts/ (true leaf — imports only itself+stdlib),
> _shared/ (tier-2, needs contracts). The remaining **17 cycles all live in the domain/execution tiers** (3/4):
> adapter, cli_choices, element, executor, integrations, orchestrator, pack, project, runtime, session, task, timeline.
> That's the W2–W7 surface. Of those: ~6 are inversions (W3), project-web is domain-edge (W4/W5), session/timeline CLI (W5),
> 2 accepted seams (adapter↔task, session↔task, W4).

> **PLAN-CORRECTING FINDING (W1a):** The plan claimed `project/paths → foundation` "dissolves 5 cycles."
> FALSE. Moving paths broke only `executor↔paths`. `project↔{task,session,timeline}` persist because they
> ride **non-paths domain edges**: `project/run.py` + `project/cli.py` import task/session/timeline, while many
> task/session/timeline modules import project. Likewise `contracts↔util` persists (`result_manifest→util.atomic_io`
> + `util.{http,secrets,llm_clients}→contracts.errors`). The keystone's real win = removing 88 couplings to the
> `project` *surface* + a clean tier-0 `foundation/`. Breaking the project-web is now **domain-edge work** (the
> `project/cli.py` edges → W5 CLI-lift; `project/run.py`↔task → W4 seam, likely accept-and-document). `contracts↔util`
> → move `write_json_atomic` to foundation too (fold into W1b).
| W2 | medium leaf moves (taxonomy 45, edits 26, cli_choices 41, …) | DeepSeek | ⬜ todo | — |
| W3 | invert hacks (_pipeline_module, pack/validate, resolvers, 2 Protocols) | Opus | ⬜ todo | — |
| W4 | task/ + orchestrate→task/dsl (53); accept adapter↔task, session↔task seams | Opus | ⬜ todo | — |
| W5 | lift CLI tier + packs/tests reorg | DeepSeek | ⬜ todo | — |
| W6 | integration: full suite, re-measure, push | main | ⬜ todo | — |
| W7 | umbrellas: execution/ (executor 65, orchestrator 60), core/registry/ | Opus | ⬜ todo | — |

## Log (newest first)
- 2026-06-09: Scaffold landed — `scripts/reshape/import_cycles.py` (checker), baseline JSON (24 cycles),
  this ledger. Verified live workers are on arnold repo, not Astrid. Starting W0.
