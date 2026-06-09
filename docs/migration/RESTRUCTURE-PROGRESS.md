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
- Cross-package cycles: **24 → 6** (floor reached). The 6 are genuine domain couplings, accepted & documented
  in `docs/architecture/import-tiers.md`: adapter↔task, session↔task, project↔task, project↔timeline,
  orchestrator↔task, element↔project.
- Tiers 0/1/2 clean (foundation stdlib-pure; contracts a true leaf; _shared above contracts). CLI lifted to tier-6.
- Tests collected baseline: **5451**.
- DEFERRED optional cosmetic (no cycle/correctness impact): execution/ fold, task/ internal nesting, env_vars→foundation tidy, facade→__init__.

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
| W2 | generation↔model_catalog: move taxonomy → model_catalog/taxonomy.py (broke the cycle; load_default keeps a runtime-only assembly seam via importlib, import-graph acyclic). element↔project: **DEFERRED** — can't host resolver in theme (project→theme is a pre-existing hard edge → would make theme↔project, worse). | Claude(Opus) sub | ✅ done (1 of 2) | 16 |

> **element↔project deferred:** the slug→theme-dir resolver needs BOTH project (config read+validate) and theme
> (dir resolve), so it must sit ABOVE both — `theme` can't host it (project already imports theme). Either ACCEPT-and-document
> (like adapter↔task) or relocate the resolver to an execution-tier assembler. Revisit in W4 (seam triage) / W7.
> **model_catalog assembly seam:** load_default reaches up to generation's pack-scanners at call time (importlib);
> proper home is the W7 registry-collapse layer.
> Pure-tidy W2 relocations (_utc_now, env, media, *_edits, cli_contract, plan_verbs) → folded into the W0c cleanup pass (no cycle impact).
| W3 | invert hacks: deleted pack/validate deep-validation (broke pack↔executor + pack↔orchestrator), moved requires_timeline resolution into executor.runner (broke executor↔project), RemoteTimelineLister Protocol (broke integrations↔timeline). **task↔orchestrator BLOCKED.** executor↔orchestrator deferred to W7. | Claude(Opus) sub | ✅ done (4 cycles) | 12 |

> **task↔orchestrator BLOCKED (genuine):** `_list_orchestrator_ids` consumers span session AND task; orchestrator
> already imports session.config → moving the helper to orchestrator makes session↔orchestrator (worse). Injection
> would ripple ~50 gateway-dispatch call sites + change session's discovery_hints API. → accept-and-document, or
> resolve via the W7 execution-tier assembler. Joins {element↔project, adapter↔task, session↔task} as accept-candidates.
> **Remaining 12 cycles** = W4 (accept adapter↔task + session↔task; project↔task domain), W5 (CLI lift: cli_choices↔pack,
> session↔timeline, task↔timeline, integrations↔project, project↔session/timeline CLI halves), W7 (executor↔orchestrator fold).
| W4 | task/ + orchestrate→task/dsl (53); accept adapter↔task, session↔task seams | Opus | ⬜ todo | — |
| W5 | lift CLI tier + packs/tests reorg | DeepSeek | ⬜ todo | — |
| project-web | diagnose+break project↔{session,task,timeline}: project↔session BROKEN (lease-blender fns → session/current_run_state.py); project↔task + project↔timeline ACCEPT (genuine host/plugin + co-owned-binding coupling) | Claude(Opus) sub | ✅ done | 7 |
| W6 | integration: full suite, re-measure, push | main | ⬜ todo | — |

> **Accepted floor forming (genuine bidirectional domain coupling — documented, not failures):**
> `adapter↔task` (plugin), `session↔task` (shared write path; has a known cold-import-order sensitivity — pre-existing,
> avoided because real entry loads task first; the W4 shallow-bridge cut would reduce it), `project↔task` (a run is
> hosted-by / produces task steps), `project↔timeline` (a run and its timeline co-own the contributing-run binding).
> Still potentially breakable: `executor↔orchestrator` (W7 fold → intra-package), `orchestrator↔task` (W3-blocked),
> `element↔project` (W2-deferred). Realistic floor ≈ 6 (5 accepted + executor↔orchestrator pending W7).
| W7 | umbrellas: execution/ (executor 65, orchestrator 60), core/registry/ | Opus | ⬜ todo | — |

## Log (newest first)
- 2026-06-09: Scaffold landed — `scripts/reshape/import_cycles.py` (checker), baseline JSON (24 cycles),
  this ledger. Verified live workers are on arnold repo, not Astrid. Starting W0.
