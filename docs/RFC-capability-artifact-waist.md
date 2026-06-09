# RFC: The Capability Artifact Waist

**Status:** Draft for decision · **Date:** 2026-06-09 · **Author:** analysis synthesized by Claude, grounded in first-hand code reads + 6 independent DeepSeek category audits

> One-line: Astrid's six "pluggable kinds" are one pattern implemented six times. The fundamental missing piece is a **semantic artifact type system** — the narrow waist through which capabilities compose. Everything is currently typed `file`, so composition is name-wired (M×N). This RFC adds the waist *additively*, proves it on one seam, and defers the structural collapse to post-launch.

---

## 1. The finding (verified against code, not just audits)

Astrid has six pluggable-capability subsystems — **models, elements, executors, orchestrators, themes, timelines** — each with its own registry, manifest, and consumer wiring. They are the *same* pattern (manifest-as-data + registry + runtime) built independently. The model catalog already proved the cleanest version: a data manifest (`models.yaml`) + a swappable backend adapter (`FalBackend`/`VibecomfyBackend`/`CodexBackend`).

But the unifying mechanism that would make them *one* thing does not exist:

**There is no semantic type system.** `core/contracts/schema.py:9-11`:
```python
PortType = Literal["string","path","file","directory","json","boolean","number","integer","html"]
```
These are **transport** types (how bytes arrive at a CLI boundary), not **artifact** types (what the bytes *mean*). `Port.type` and `Output.type` both default to `"path"` (schema.py:28,38). So a `video/clip`, an `image`, and an `audio` are all just `file`.

**Consequence — composition is name-wired everywhere (the M×N problem).** The canonical site, `timeline/validators/timeline.py:247-257`:
```python
clip_type = clip.get("clipType", "media")
...
active_theme = theme if isinstance(theme, str) else None
from astrid.core.timeline.banodoco_schema import _effect_ids
effect_ids = _effect_ids(active_theme)          # pull the ENTIRE set of effect ids
if clip_type in effect_ids:                      # ...to membership-test one clipType
    _validate_effect_params(clip_type, clip.get("params"), ..., theme=active_theme)
```
`_effect_ids` (`validators/registry.py:10-12`) calls `effects_catalog.list_effect_ids()`. The timeline must enumerate *every* effect to know which `clipType` strings are effects. Add a pack with a new effect and every consumer must re-enumerate. That is M×N, and it is the *only* thing possible while everything is typed `file`.

**The substrate is further along than the audits claimed.** `core/contracts/schema.py:119-149` already defines `CapabilityHandle` — a shared identity carried by *every* executor, orchestrator, and element, complete with `inputs: tuple[Port,...]`, `outputs: tuple[Output,...]`, and a `Provenance` block. `to_capability_handle` (schema.py:193) adapts the native definitions into it. The comment at line 80 even reads "M1 Capability Identity." So the **identity** layer is unified; only the **type** on its ports is missing. We are adding the waist to a structure built to receive it — not green-fielding a kernel.

---

## 2. Two corrections the audits got wrong (found by reading the code)

The six DeepSeek agents converged at "HIGH confidence" and each wanted to bolt on a new primitive. Two of those are over-reach; the code disproves them:

1. **"Composition must become a declarative typed dataflow graph" (orchestrators agent).** No. Orchestrators are imperative `run.py` scripts today, and that is *fine*. The right model: an orchestrator is a capability whose runtime is "a script" that calls other capabilities through the kernel. The waist lives at the capability boundary (typed I/O); composition above it stays imperative. Building a workflow language is the over-abstraction trap.

2. **"Timelines need a `document` first-class primitive (peer to artifact/capability)" (timelines agent).** No — a timeline is just a structured *artifact* (type `timeline`). And the code already proves the real composition mode: timeline animation refs are `{"id","durationFrames","easing","params"}` (timeline.py:26-35) and transition refs are `{"id","type","duration","params"}` (timeline.py:108). That is **id-reference + inline params** — already the de-facto pattern. So the correct claim is narrower and stronger:

> **Composition = type-match (for validation) + id-reference (for selection). The id-reference is irreducible.** You cannot replace "apply `cross-fade`" with pure type-matching — the user is choosing *which* of N `clip→clip` transitions. Type-matching validates; the id selects. This holds for timelines and orchestrators alike.

**One real constraint the audits missed:** `clipType` is *deliberately an open string* "for Reigh compatibility… unknown clip types stay valid and classify as opaque at runtime" (timeline.py:194, 251-252). **The migration must preserve open-string fallback** — artifact types validate what we know and leave unknowns opaque. No closed enum.

---

## 3. The one genuinely missing second primitive: scoped config

A pure capability/artifact waist has **no home for ambient context**. Themes are exactly this need, implemented in the worst way: a module-global mutable `_ACTIVE_THEME_DIR` plus an `HYPE_ACTIVE_THEME` env var threaded into subprocess environments (`core/element/catalog.py`, `project/run.py:97`). A theme is a bundle of `{visual config + assets + element-overrides}`; the override part is just the kernel's `OverrideStore` relabeled.

At thousands of packs this generalizes to brand kits, render profiles, locale, safety policy, secrets — all **scoped configuration consumed by many capabilities, none of them a capability themselves**. Threading them as explicit `consumes` ports on every capability *recreates M×N*. So the contract needs exactly **one** more primitive beyond artifacts: **scoped config**, resolved by the kernel per scope (project/user/env) and injected where declared.

Cross-confirmation: the megaplan/arnold harness, mid its own "generalized-pipeline-migration" chain, is adding precisely an *optional `RunContext` protocol field to the generic `StepContext`* in its m6-runtime-foundation milestone. Two independent systems converged on "the typed-IO substrate needs a context carrier." That is signal, not coincidence.

---

## 4. The contract (final shape)

Three primitives + a kernel:

- **Artifact** — a typed value passed between capabilities: `{type, schema}`. Types are pack-extensible and open (unknown → opaque). *This is the waist.*
- **Capability** — the universal unit: `{id, kind(tag), consumes[typed ports], produces[typed ports], params(json-schema), runtime(adapter+config), metadata}`. Model/element/executor/orchestrator differ only in artifact types + runtime adapter.
- **Scoped config** — ambient typed configuration resolved by kernel scope; distinct from `params` (per-call) and artifacts (dataflow).
- **Kernel** — discovers capabilities from packs; indexes by produced/consumed artifact type; resolves by id+alias+override (the existing `CapabilityHandle`/`OverrideStore`); dispatches to the runtime adapter. Knows nothing about video/Remotion/fal.

**Composition rule:** a consumer references a producer by **id**; the kernel **validates** the referenced capability's artifact types are compatible. Imperative orchestration and structured-document artifacts (timelines) both compose by id-reference + kernel type-check — never by name-enumeration.

---

## 5. The build — additive first (exact changes)

### A1. Artifact type field (purely additive, zero breakage)
`core/contracts/schema.py` — add an optional field beside the existing transport `type`:
```python
@dataclass(frozen=True)
class Port:
    name: str
    type: PortType = "path"           # transport — unchanged
    artifact_type: str | None = None  # NEW: semantic waist type, e.g. "video/clip"
    required: bool = True
    ...

@dataclass(frozen=True)
class Output:
    name: str
    type: PortType = "path"           # transport — unchanged
    artifact_type: str | None = None  # NEW
    ...
```
Optional → every existing manifest keeps working. Composition is type-checked only where `artifact_type` is declared; elsewhere, current behavior (opaque) is preserved.

### A2. Artifact type registry (mirror the proven pack-extensible pattern)
`ElementKindRegistry` (`timeline/.../kinds.py`, populated from `pack.extensions.timeline.kinds`) is already an embryonic, pack-extensible type registry. Build `ArtifactTypeRegistry` the same way. Seed it from types that **already flow** (verified in code):

| Artifact type | Seen in |
|---|---|
| `text/prompt` | model `prompt` inputs |
| `image` | image gen output, `image_ref`/`image_end_ref` inputs |
| `mask` | edit/inpaint inputs |
| `audio` | foley / lavasr / denoise |
| `video/clip` | video gen output, foley input, timeline clips |
| `timeline` | `TimelineConfig` → render input |
| `asset_registry` | `validate_registry` (assets `{file,url}`) |
| `lora` | fal LoRA resolution (registry id + scale + base-model match) |

Unknown types stay opaque (Reigh open-string rule, §2).

### A3. Prove M+N on ONE seam — the timeline validator
Replace the enumerate-and-membership-test (timeline.py:247-257) with id-resolution + type-check:
```python
clip_type = clip.get("clipType", "media")
cap = kernel.resolve(clip_type, scope=active_theme)   # id-reference (irreducible)
if cap is not None:                                    # known capability
    kernel.check_consumes(cap, artifact_type="video/clip")  # type-match (validation)
    _validate_effect_params(clip_type, clip.get("params"), ..., theme=active_theme)
# else: unknown clipType stays opaque — Reigh compatibility preserved
```
The validator no longer enumerates every effect. A third-party pack's effect is resolved + type-checked through the kernel, not discovered by re-listing. **This is the M×N→M+N proof in one file.** Highest-traffic name-wiring site; immediate, visible payoff; fully reversible.

### A4–A6 (defer to post-launch)
- **A4** Scoped-config primitive; reimplement themes on it (kill `_ACTIVE_THEME_DIR` global + env threading); absorb secrets.
- **A5** Strangler the remaining name-wired seams (orchestrator `child_executors`, model `param_map` → into adapters).
- **A6** Collapse the registries onto the existing `CapabilityHandle` kernel; `kind` becomes a tag; delete element's per-kind fork/version/override/install (use shared `OverrideStore`).

---

## 6. Migration methodology — mirror the proven arnold chain

The megaplan/arnold harness is mid an identical-shaped migration (`aggressive-generalized-pipeline-migration`, base branch `arnold-generalized-pipeline`). Its sequence is battle-tested; mirror it:

| arnold milestone | Astrid analogue |
|---|---|
| m0 boundary-lock (import/leak gates, inventory) | Inventory artifact types that flow; lock "no closed enums on open strings" |
| m1 neutral vocabulary extraction | Add `artifact_type` field + registry (A1, A2) — additive, re-export-safe |
| m2 contract registry (one authoritative map) | `ArtifactTypeRegistry` becomes the single source for type checks |
| m5 oracle-gated strangler | Each migrated seam gated by a parity oracle (old name-wiring vs new type-wiring agree) |
| m6 runtime-foundation (RunContext) | Scoped-config primitive (A4) |

Their hard-won lesson, verbatim worth heeding: *"extraction must move **mechanisms** not **engines**"* and *"make the cross-cutting carriers generic FIRST so the runtime extractions don't silently re-couple."* For us: ship the artifact-type carrier (A1/A2) before touching any consumer.

---

## 7. Explicit non-goals (anti-over-abstraction)

Note, do **not** build: streaming/realtime QoS, training-as-stateful-session, declarative orchestrator workflow graphs, a `document` primitive peer to artifact/capability, operational-metadata schema (cost/latency → keep on results), per-model behavior generalization (flux-schnell/ideogram hardcodes stay in the adapter for now).

---

## 8. Recommendation

The platform is launch-blocked on the security model, not on this. So:

1. **Now (additive, foundational, cheap):** A1 + A2 + A3. The type field breaks nothing; the timeline seam proves M+N for the cost of one file; together they de-risk the entire theory.
2. **Post-launch:** A4–A6 as a gated strangler chain mirroring §6.
3. **Immediately, free, today:** internalize the rule — **stop shipping bespoke per-kind subsystems.** The next new pluggable kind goes through the capability/artifact path or it doesn't ship. That alone stops the bleeding while the migration waits its turn.

The fundamental thing we were missing was never "elements is the wrong abstraction." It is that **the narrow waist — typed artifacts — does not exist yet.** Everything is `file`. Add the waist, and elements/models/executors stop being six subsystems and become one.
