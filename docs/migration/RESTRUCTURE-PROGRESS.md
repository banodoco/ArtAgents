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
| W0 | free/near-free: facades→__init__, 🟢-zero breaks, dedups, event_hash, ULID, small prefix-drops | DeepSeek | ⬜ todo | — |
| W1 | foundation/ + _shared/ keystone (project/paths 88, jsonio 52, result_manifest 51) | DeepSeek + Opus review | ⬜ todo | — |
| W2 | medium leaf moves (taxonomy 45, edits 26, cli_choices 41, …) | DeepSeek | ⬜ todo | — |
| W3 | invert hacks (_pipeline_module, pack/validate, resolvers, 2 Protocols) | Opus | ⬜ todo | — |
| W4 | task/ + orchestrate→task/dsl (53); accept adapter↔task, session↔task seams | Opus | ⬜ todo | — |
| W5 | lift CLI tier + packs/tests reorg | DeepSeek | ⬜ todo | — |
| W6 | integration: full suite, re-measure, push | main | ⬜ todo | — |
| W7 | umbrellas: execution/ (executor 65, orchestrator 60), core/registry/ | Opus | ⬜ todo | — |

## Log (newest first)
- 2026-06-09: Scaffold landed — `scripts/reshape/import_cycles.py` (checker), baseline JSON (24 cycles),
  this ledger. Verified live workers are on arnold repo, not Astrid. Starting W0.
