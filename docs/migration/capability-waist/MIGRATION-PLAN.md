# Migration Plan: The Capability Artifact Waist

**Status:** Planned & committed — NOT started. **HOLDS** until RESTRUCTURE lands W1+W7 and its `beauty-v2` worker stops, then runs **fully autonomously to completion** — no human-in-the-loop, no review steps, no decision points; every gate is an objective test/oracle.
**Branch:** `capability-waist-epic` (worktree) · **RFC:** [`docs/RFC-capability-artifact-waist.md`](../../RFC-capability-artifact-waist.md)
**Shape:** 6-sprint epic chain — **S0 de-risk spike + S1–S5** — organized by **seam** (the work's real fault lines), not by step-order. Dials per the megaplan-prep skill. Mirrors the arnold methodology: carrier-first, parity-gated strangler, move mechanisms not engines. Full end-to-end build (decision: do it all), with the hard bets proven first.

> **Goal:** make every pluggable kind (models, elements, executors, orchestrators, themes, timelines) one **capability** that composes through a **semantic artifact type** (the waist), with **scoped config** for ambient context. Migrate everything; purge the per-kind lifecycle machinery; ship a worked example.
>
> **North star (the acceptance criterion):** ~**100 independently-authored packs can compose without chaos** — the Nth pack with a novel capability interoperates with existing packs with **zero core changes**, *and* the externally-shared timeline format (Reigh) still round-trips unchanged. This scale is why the waist earns itself; at a dozen packs it would be overkill.

---

## 0. Two rules carried from arnold + megaplan-prep

1. **Carrier first, parity-gated strangler.** The type carrier lands before any consumer is rewired; every behavioral seam ships a **parity oracle** (new path accepts/rejects the same inputs as the old) before the old path is deleted. No big-bang.
2. **Dial on decision DIFFICULTY, not stakes.** Behavior-preserving work behind an objective gate defaults to a cheap driver (`solo`). The exceptions that earn a premium *planner* are (a) genuinely novel cross-cutting decisions and (b) **import-topology / package-boundary work** (registry collapse, `__init__`/re-export rewiring) — which fails non-locally in a way a gate doesn't catch.

---

## 1. The three axes (why the seams fall where they do)

| Axis | What it is | Sprints |
|---|---|---|
| **The waist** | semantic artifact types + type-checked composition (carrier → annotate → consumers) | S1 (proof slice), S2 (rollout) |
| **Scoped config** | ambient context as a first-class primitive (themes today) | S3 |
| **Structural collapse** | make the kinds one thing: registries → kernel, `kind`→tag, elements restructured, dead machinery purged | S4 |
| (docs threaded) | worked example + guide once the contract is real | S5 |

A sprint never spans two axes. The element work is deliberately split *across* axes: typed-I/O **annotation** is part of the waist (S1); structural **restructure + purge** is part of the collapse (S4).

---

## 2. Blast radius (verified by inventory; file:line in briefs)

| Area | Sites | Notes |
|---|---|---|
| `Port`/`Output` dataclass | `contracts/schema.py:26-43` | the field lands here |
| Port/Output construction | `executor/schema.py:312-338`, `orchestrator/schema.py:211-237` | **only 2 parsers** — surgical |
| `.type` reads | `executor/runner.py:747`, `contracts/_capability_common.py:131-133`, 2 CLI prints | small |
| Identity already unified | `CapabilityHandle` + `to_capability_handle` (`contracts/schema.py:119-260`) across exec/orch/element | collapse builds on this |
| Registries consumed | element 9, model 3, executor 4, orch 4 | S4 |
| Elements on disk | **12** (9 rendering, 3 local; text-card duplicated) | §3 dispositions |
| Element lifecycle machinery | fork `registry.py:148-159`, `install.py` (93L), cli `fork/install/override/dirty/update` | CLI/test-only → purge in S4 |
| Theme ambient-context seams | **32+** (`_ACTIVE_THEME_DIR`, `HYPE_ACTIVE_THEME`, subprocess_env propagation, project binding) | S3 |
| Timeline name-wiring | `validators/timeline.py:247-257`, `validators/registry.py:10-22` | S1 (the proof) |
| Artifact types already flowing | 13: video/clip, image, audio, mask, prompt, transcript, timeline, asset_registry, lora, pool, arrangement, … | seeds the registry |

---

## 3. Element disposition (your "purge or rename", decided)

**Decision: migrate all live elements to capability form (S1 annotates their I/O; S4 restructures + dedups); purge the dead machinery (S4); keep "element" as a user-facing kind-family tag (no churny word-rename).** The 12 are load-bearing for the timeline — the *machinery* is the dead weight, not the elements.

| Element(s) | Pack | Disposition |
|---|---|---|
| `fade-up`,`fade`,`scale-in`,`slide-left`,`slide-up`,`type-on` (animations) | rendering | MIGRATE → `clip/visual → clip/visual`, `runtime: remotion` |
| `text-card` (effect) | rendering | MIGRATE → `clip/visual (+style) → clip/visual` |
| `cross-fade`,`fade` (transitions) | rendering | MIGRATE → `clip/visual, clip/visual → clip/visual` |
| `text-card` (effect) | local | KEEP as kernel `OverrideStore` override (dedup) — not an element-special fork |
| `neon-orbit-card`,`model-trends` (effects) | local | MIGRATE → `clip/visual → clip/visual`, `runtime: remotion` (DOM-in-canvas) |

**PURGE (delete, not deprecate)** in S4: element `fork`, `install.py`, cli `fork/install/override/dirty/update`, and their tests (removed, not skipped). If a fork/version lifecycle is ever needed it lives **once** in the kernel — models prove it's unnecessary.
**Locked:** the word "element" stays as the kind-family tag — renaming is churn for no functional gain. No decision pending.

---

## 4. The sprints + dials (per megaplan-prep)

Each sprint tiered on its own decision difficulty. Vendor `codex` (house default); robustness `full` throughout (none warrant `thorough` — this is pre-launch internal refactor behind parity oracles, not production-data/public-API). Depth `low` unless the planner faces a real decision.

| Sprint | Outcome (one sentence) | profile | robust. | depth | Why these dials |
|---|---|---|---|---|---|
| **S0 — de-risk spike** | Prove the scoped-config primitive on **one** theme seam (subprocess parity preserved) and capture the Reigh round-trip baseline. (Import-graph leg dropped — RESTRUCTURE/CY1–CY5 covers it.) | `partnered` | light | high | The real risk is S3's scoped-config — prove it first. Premium planner for the novel primitive; spike → light robustness. **Gate is objective** (seam works + baseline green); a milestone that can't meet its gate fails the chain — no human halt. |
| **S1 — waist + timeline proof** | The rendering path composes by artifact type, not by name (carrier + element/clip annotation + timeline validator rewrite behind a parity oracle). | `directed` | full | medium | Vertical slice; the carrier is additive but the **type-resolution design** is a real planner decision → premium plan, DeepSeek execute, gate backstops. |
| **S2 — waist rollout** | Every remaining name-wired seam is type-checked (other exec/orch/model I/O, orchestrator `child_*`, model `param_map`→adapters). | `solo` | full | low | Mechanical replication of the S1 pattern; behavior-preserving + per-seam parity → cheapest driver; finalize still premium-adjudicates. |
| **S3 — scoped-config + themes** | A scoped-config primitive replaces ambient theme globals; `_ACTIVE_THEME_DIR`/`HYPE_ACTIVE_THEME` threading gone; secrets folded in. | `partnered` | full | high | Novel **cross-cutting** primitive across 32+ sites → premium reasoning throughout, high planner depth for the blast radius. |
| **S4 — collapse + restructure + purge** | Four registries collapse onto one `CapabilityHandle` kernel; `kind`→tag; elements get runtime adapters (`component.tsx` non-required); dedup; dead machinery deleted. | `partnered` | full | high | **Import-topology trigger** (`__init__`/re-export rewiring, gateway dispatch) → premium planner mandatory (the circular-import trap); high depth for the import graph. |
| **S5 — example + docs** | Worked example (a fal model + a Remotion element, same contract) in `docs/examples/`, guide in `docs/contracts/`, updated `docs/templates/element/`. | `solo` | light | low | Docs + a validated example; lowest stakes. |

**Dependency graph:** `S0 → S1 → S2; S1 → S3 → S4; S2 → S4; S4 → S5`. S0 gates the whole epic and its findings feed S3 (scoped-config) and S4 (collapse). S2 and S3 run in parallel after S1.

**Sizing check:** each sprint ≈ 1–2 weeks. S4 is the heaviest — if it bloats during planning, split element-restructure+purge off from the registry-collapse into its own sprint (noted in the S4 brief).

---

## 5. Execution plan (full build, de-risked order)

Decision: **do it all end-to-end** to reach the 100-pack north star. Sequenced so the irreversible bets are proven first.

- **Fully autonomous — zero human-in-the-loop.** Every gate is an objective test/oracle; no review steps, no decision points, no `awaiting_human_verify` halts. Run config: `--no-prep-clarify` (prep never blocks on questions), auto merge-policy (no manual merges), no `--with-feedback`. A milestone either meets its objective gate or fails the chain; `/babysit` unblocks stalls autonomously.
- **Order:** S0 (de-risk) → S1 (waist proof) → {S2 rollout ∥ S3 scoped-config} → S4 (capabilities-on-kernel + purge) → S5 docs.
- **Hold + serialize (load-bearing):** this epic LAYERS ON RESTRUCTURE. It does **not** start until RESTRUCTURE has landed W1 + W7 **and its `beauty-v2` worker has stopped** — running alongside it would collide on shared files (contracts/executor/timeline). One wave at a time.
- **Reigh protection (automated, no sign-off):** the Reigh round-trip parity gate (baseline from S0) stays green in CI through every sprint; unknown/foreign types pass through opaque. The gate *is* the protection — no human sign-off.
- **Mechanics:** once RESTRUCTURE lands, rebase the base onto it, then `megaplan chain start --spec docs/migration/capability-waist/chain.yaml --in-worktree capability-waist --no-prep-clarify` inside a subagent; `/babysit` to completion; land via PR.
- **Standing rule, effective now:** *no new bespoke per-kind subsystem* — the next pluggable kind goes through the capability/artifact path or it doesn't ship.

---

## 6. Worked example (inline draft — the S5 deliverable, made tangible now)

A fal **model** and a Remotion **element** are the *same shape* — differ only in artifact types + runtime adapter.

```yaml
id: flux-dev          # a cloud image model, in contract form
kind: model
consumes: [{ port: prompt, type: file, artifact_type: text/prompt }]
produces: [{ port: image,  type: file, artifact_type: image }]
params:  { seed: {type: integer}, steps: {type: integer, default: 28} }
runtime: { adapter: fal, endpoint: "fal-ai/flux/dev" }
```
```yaml
id: cross-fade        # a Remotion transition element, in contract form
kind: transition
consumes: [{ port: outgoing, type: file, artifact_type: clip/visual },
           { port: incoming, type: file, artifact_type: clip/visual }]
produces: [{ port: out,      type: file, artifact_type: clip/visual }]
params:  { durationFrames: {type: integer, default: 8} }
runtime: { adapter: remotion }     # component.tsx resolved by convention, not required
```
Composition is identical: a consumer references by **id**; the kernel **validates** `artifact_type` matches. The timeline says `transition: {id: cross-fade, params: {...}}`; the kernel checks `cross-fade` consumes/produces `clip/visual` — no `_effect_ids()` enumeration.

---

## 7. Non-goals (anti-over-abstraction — explicit)

Not in this epic: streaming/realtime QoS; training-as-stateful-session; declarative orchestrator workflow graphs (imperative `run.py` calling typed capabilities stays); a `document` primitive (a timeline is a structured artifact); operational-metadata schema (cost/latency stay on results); generalizing per-model adapter hardcodes beyond moving them out of shared code.

---

## 8. Cross-cutting requirements (what makes 100 packs coherent, not chaotic)

These apply to **every** sprint — they are how the full build stays trustworthy.

1. **Open & extensible registry; types are additive opinions, not a closed gate.** Packs declare their own artifact types via `pack.extensions["artifact_types"]`. Composition type-checks where types are *declared*; unknown types stay **opaque, never rejected**. This is the "open `clipType`" philosophy generalized — it's what lets 100 packs evolve vocabularies independently without a central enum becoming a chokepoint. (Resolves both the chaos risk *and* the rigidity risk: too-strict typing on an open ecosystem is its own kind of chaos via constant breakage.)
2. **Lenient at the external boundary.** The timeline format is shared with Reigh via the external `banodoco_timeline_schema` package. Astrid's artifact types are an **internal** opinion; at the Reigh boundary, unknown/foreign types pass through opaque. Astrid never tightens a format it doesn't solely own.
3. **No flag day / data migration.** `artifact_type` is **used-if-present, never required-for-load**. Existing on-disk timelines/manifests and Reigh-authored ones must keep loading unchanged through every sprint, including after S4.
4. **Concurrency-safe.** Worktree-isolated; never edit `main` while the `beauty-v2` worker runs; land via PR. (See §5.)
5. **Success metrics beyond "tests pass":** (a) a synthetic "Nth pack" with a novel capability composes with existing packs with **zero core changes**; (b) **Reigh round-trips** Astrid timelines unchanged; (c) a third-party pack author can read the S5 guide and ship a typed capability without touching core.
6. **Named ownership (doc deliverable, not a run gate).** The S5 `docs/contracts/` guide records the spec + owner for the artifact-type registry + kernel. No run-time human step.

## 9. Decision record — Opus high-altitude sense-check (folded in)

A high-altitude review flagged: (a) S1 gates on the *easy* claim while S3/S4 hold the real risk; (b) the narrow-waist frame leans on the arnold migration (same author/method = weak independent evidence); (c) typing a Reigh-shared open format risks ossifying what Astrid doesn't own; (d) opportunity cost vs. the security launch blocker; (e) live-worker concurrency + no data-migration/metrics/owner.

**Disposition:** its "premature, don't build" verdict is **overridden** by the explicit goal — a coherent system for ~100 packs, which is precisely the scale that justifies the waist. Its *operational* findings are **adopted**: (a) → the S0 de-risk spike proves S3/S4 first; (c) → §8.1–8.2 (open/lenient typing); (e) → §8.3–8.6 + §5 guards. Note the diagnosis (no semantic types → name-wiring) is code-verified and stands; the over-reach that was trimmed is *timing of the proof*, not scope. `CapabilityHandle` unifies *identity* only — it does **not** solve composition, so the type waist is necessary, not gold-plating.

---

## 10. Reconciliation with RESTRUCTURE-PLAN (this epic LAYERS ON it)

Discovered after planning: `RESTRUCTURE-PLAN.md` (in repo root; executing as the `beauty-v2` commits) is a live, code-verified restructure of Astrid's import graph — 23 cross-package cycles → 8 clean tiers, `contracts/` as a true leaf, new `foundation/`/`_shared/` tiers, **a `core/registry/` base + an `execution/{executor,orchestrator}` umbrella (its W7)**. It fixes *where code lives*; this epic adds *how things compose*. RESTRUCTURE is the **prerequisite substrate**, not a competitor.

**What this changes here (decision: layer on top):**
- **S0** drops its import-graph leg — RESTRUCTURE's CY1–CY5 analysis already satisfies it. S0 shrinks to the scoped-config feasibility spike + the Reigh round-trip baseline.
- **S4** no longer *builds* the kernel/collapses registries — RESTRUCTURE's W7 does. S4 (renamed *capabilities-on-kernel-and-purge*) now **consumes** RESTRUCTURE's `core/registry/` + `execution/` and does only the element-specific restructure + the lifecycle purge. **S4 requires RESTRUCTURE W7 to have landed.**
- **Sequencing:** the whole epic starts after RESTRUCTURE's W1 (foundation/contracts tiers) + W7 (registry/execution) land; rebase the base branch onto that first.
- **Philosophy seam:** RESTRUCTURE is "no shims, no back-compat" — correct, because it only touches *internal* package structure. This epic stays *additive / no-flag-day* at the **Reigh-shared** boundary (§8.2–8.3). Different layers, compatible rules.

**Canonical runnable epic:** `docs/migration/capability-waist/{chain.yaml, briefs/s0–s5}` (tracked here because Astrid gitignores `.megaplan/`; run via `--spec`). This doc is the design narrative. A snapshot of `RESTRUCTURE-PLAN.md` is committed on this branch as the base we build on.
