# Migration Plan: The Capability Artifact Waist

**Status:** Planned — NOT started. Awaiting execution approval.
**Branch:** `astrid-capability-waist` · **RFC:** [`docs/RFC-capability-artifact-waist.md`](../../RFC-capability-artifact-waist.md)
**Shape:** 5-sprint epic chain (S1–S5), organized by **seam** (the work's real fault lines), not by step-order. Dials picked per the megaplan-prep skill. Mirrors the arnold methodology: carrier-first, parity-gated strangler, move mechanisms not engines.

> Goal: make every pluggable kind (models, elements, executors, orchestrators, themes, timelines) one **capability** that composes through a **semantic artifact type** (the waist), with **scoped config** for ambient context. Migrate everything to it; purge the speculative per-kind lifecycle machinery; ship a worked example.

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
**Override point:** if you want the *word* "element" gone entirely (→ "visual capability"), that's an S4 rename pass — say so and I fold it in.

---

## 4. The sprints + dials (per megaplan-prep)

Each sprint tiered on its own decision difficulty. Vendor `codex` (house default); robustness `full` throughout (none warrant `thorough` — this is pre-launch internal refactor behind parity oracles, not production-data/public-API). Depth `low` unless the planner faces a real decision.

| Sprint | Outcome (one sentence) | profile | robust. | depth | Why these dials |
|---|---|---|---|---|---|
| **S1 — waist + timeline proof** | The rendering path composes by artifact type, not by name (carrier + element/clip annotation + timeline validator rewrite behind a parity oracle). | `directed` | full | medium | Vertical slice; the carrier is additive but the **type-resolution design** is a real planner decision → premium plan, DeepSeek execute, gate backstops. |
| **S2 — waist rollout** | Every remaining name-wired seam is type-checked (other exec/orch/model I/O, orchestrator `child_*`, model `param_map`→adapters). | `solo` | full | low | Mechanical replication of the S1 pattern; behavior-preserving + per-seam parity → cheapest driver; finalize still premium-adjudicates. |
| **S3 — scoped-config + themes** | A scoped-config primitive replaces ambient theme globals; `_ACTIVE_THEME_DIR`/`HYPE_ACTIVE_THEME` threading gone; secrets folded in. | `partnered` | full | high | Novel **cross-cutting** primitive across 32+ sites → premium reasoning throughout, high planner depth for the blast radius. |
| **S4 — collapse + restructure + purge** | Four registries collapse onto one `CapabilityHandle` kernel; `kind`→tag; elements get runtime adapters (`component.tsx` non-required); dedup; dead machinery deleted. | `partnered` | full | high | **Import-topology trigger** (`__init__`/re-export rewiring, gateway dispatch) → premium planner mandatory (the circular-import trap); high depth for the import graph. |
| **S5 — example + docs** | Worked example (a fal model + a Remotion element, same contract) in `docs/examples/`, guide in `docs/contracts/`, updated `docs/templates/element/`. | `solo` | light | low | Docs + a validated example; lowest stakes. |

**Dependency graph:** `S1 → S2; S1 → S3 → S4; S2 → S4; S4 → S5`. (S3 depends on S1 because themes ride the timeline path; S2 and S3 can run in parallel after S1.)

**Sizing check:** each sprint ≈ 1–2 weeks. S4 is the heaviest — if it bloats during planning, split element-restructure+purge off from the registry-collapse into its own sprint (noted in the S4 brief).

---

## 5. Launch-aware recommendation

Platform is launch-blocked on the security model, not this.

- **Do now (the proof, launch-safe):** **S1 only.** Additive carrier + one parity-gated seam proves M×N→M+N end-to-end for ~1 sprint. If S1's oracle is green, the whole theory is validated.
- **Defer post-launch:** S2 (rollout), S3 (themes — biggest churn), S4 (collapse + purge). S5 docs whenever.
- **Free, today:** the rule — *no new bespoke per-kind subsystem.* Next pluggable kind goes through the capability/artifact path or it doesn't ship.

**Execution mechanics (when approved):** run via `megaplan chain start --spec docs/migration/capability-waist/chain.yaml` inside a subagent, then `/babysit` it to completion. Briefs move to `.megaplan/briefs/` at exec time (canonical input location).

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
