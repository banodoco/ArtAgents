# Revise the Phase-B plan against explorer evidence

You are the PLANNER-REVISER. Working dir: /workspace/reigh-phase-a-20260822/Astrid (branch phase-b). READ-ONLY — text output only.

## NORTH STAR (binding)
One authority (one SQLite file + SHA-256 media tree). Correctness by primitives (receipts, fences, leases, CAS, atomic transactions — each with a named test). Invisible failure default. Growth by declaration (declarative defs over generic executor seams). Honest latency (polling budgets). Anti-patterns: second authorities/mirrored state, cloud fallbacks/silent executor swaps, ceremony without consumer, speculative machinery, abstractions that can't name their preserved option.

## Read
`.oracle/agent_goal.md` (frozen contract), `.oracle/plan.md` (v1), ALL of `.oracle/findings/e1-vibecomfy-pinning.txt`, `e2-comfy-cpu.txt`, `e3-wgp-contract.txt`, `e4-child-envelope.txt`, `e5-setup-journal.txt`, `e6-boot-manifest.txt`, `e7-probe-honesty.txt`. Also docs-corpus/31-forward-map.md and 27-build-spec.md §3-§7 as needed.

## Task
Update the plan given these findings while staying inside the agent goal and advancing the North Star. Explicitly reject any named anti-pattern. Bias toward **elegance and simplicity** — cut scope that isn't pulling its weight. Specifically resolve: the digest-pinning mechanism (E1), CPU-mode viability verdict for DC-1 (E2), the five WGP gates concretely defined (E3), the child-key/envelope spec (E4), setup-journal placement decision with rationale (E5), boot-manifest ownership/digest scope (E6), probe predicates table (E7). Fold each into the affected tasks. List any new areas worth exploring and potential issues.

Output: FULL revised plan (same section structure as plan.md: tasklist covering B-1..B-6 with files/criteria/deps/acceptance, areas resolved, open questions closed or remaining, effort estimate update, North Star check). If truly nothing material changed, answer exactly `STABLE`.