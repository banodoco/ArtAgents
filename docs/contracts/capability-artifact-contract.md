# Capability Artifact Contract

**Status:** Normative (v1) — S5 deliverable · **RFC:** [`docs/RFC-capability-artifact-waist.md`](../RFC-capability-artifact-waist.md)

> **One-line:** Every pluggable thing in Astrid (model, element, executor, orchestrator, theme, timeline) is one **capability** that composes through a **semantic artifact type** (the waist), with **scoped config** for ambient context. Three primitives. One composition rule.

---

## 1. The three primitives

### 1.1 Capability

The universal unit of composition. A capability is a named, typed, runnable thing.

```
Capability = { id, kind(tag), consumes[typed ports], produces[typed ports], params(json-schema), runtime(adapter+config) }
```

- **`id`** — globally-unique identifier (e.g. `rendering.cross-fade`, `fal.flux-dev`).
- **`kind`** — a user-facing tag (`model`, `element`, `effect`, `transition`, `executor`, `orchestrator`). The kernel does **not** branch on `kind` — it is metadata for discovery, not dispatch logic.
- **`consumes`** — typed input ports declaring what artifact types this capability accepts.
- **`produces`** — typed output ports declaring what artifact types this capability emits.
- **`params`** — JSON Schema describing the per-invocation parameters (distinct from dataflow ports).
- **`runtime`** — which adapter runs this capability (`fal`, `remotion`, `codex`, `shell`, etc.) plus adapter-specific config.

A model, an element, an executor, and an orchestrator differ only in their artifact types + runtime adapter. The capability contract is the same shape regardless of `kind`.

### 1.2 Artifact type

The semantic waist — what bytes *mean*, not how they arrive.

| Layer | Example | Scope |
|---|---|---|
| **Transport type** (existing `Port.type`) | `file`, `path`, `string`, `json`, `integer` | How data crosses the CLI boundary |
| **Artifact type** (new `artifact_type` field) | `clip/visual`, `image`, `text/prompt`, `audio`, `timeline` | What the data *is* — semantic identity |

```python
# In the canonical schema (astrid/core/contracts/schema.py):
@dataclass(frozen=True)
class Port:
    name: str
    type: PortType = "path"            # transport — unchanged
    artifact_type: str | None = None   # NEW: semantic waist type
    ...

@dataclass(frozen=True)
class Output:
    name: str
    type: PortType = "path"            # transport — unchanged
    artifact_type: str | None = None   # NEW
    ...
```

`artifact_type` is **used-if-present, never required-for-load**. Existing manifests without it keep working unchanged. Composition type-checks only where `artifact_type` is declared; elsewhere, current behavior (opaque pass-through) is preserved.

**Built-in artifact types** (seeded from types already flowing in the codebase):

| Canonical id | Aliases | Description |
|---|---|---|
| `clip/visual` | `video/clip`, `visual` | A visual clip (video or image) — the core rendering artifact |
| `image` | — | A still image |
| `audio` | — | An audio clip or stream |
| `mask` | — | An alpha / segmentation mask |
| `prompt` | — | A text prompt for generation |
| `transcript` | — | A timed transcript or caption track |
| `timeline` | — | An Astrid timeline document |
| `asset_registry` | — | A registry of assets |
| `lora` | — | A LoRA adapter weight file |
| `pool` | — | A pool / collection reference |
| `arrangement` | — | A timeline arrangement / composition |

**Registry singleton:** `astrid.core.contracts.artifact_types.ARTIFACT_TYPE_REGISTRY` — an `ArtifactTypeRegistry` instance with the built-in descriptors above plus any pack-registered extensions. It exposes `resolve(name) → str | None` for opaque fallthrough and `normalize(name) → str` for strict validation.

### 1.3 Scoped config

Ambient typed configuration resolved by the kernel per scope (project / user / env) and injected where declared. Distinct from both `params` (per-invocation) and artifacts (dataflow).

- **Why it exists:** Threading ambient context (theme, brand kit, render profile, locale, secrets) as explicit `consumes` ports on every capability recreates the M×N name-wiring problem. Scoped config is the carrier that avoids it.
- **How it works:** A capability declares `scoped_config: [theme, secrets]`; the kernel resolves these by scope and injects them before the runtime adapter runs.
- **Current implementation:** Themes are the first scoped-config consumer (S3). The pattern generalizes to any ambient configuration bundle.

Scoped config is **not** a capability itself — it is configuration *for* capabilities, resolved by the kernel.

---

## 2. Composition rule

**Composition = type-match (for validation) + id-reference (for selection).**

- **Id-reference is irreducible.** When a consumer wants to apply `cross-fade`, it references `id: cross-fade`. You cannot replace this with pure type-matching — the user is choosing *which* of N `clip/visual → clip/visual` transitions. The id selects; type-matching validates.
- **Type-match validates the waist.** The kernel checks that the referenced capability's `consumes` / `produces` artifact types are compatible with the calling context. If `cross-fade` declares `consumes: [clip/visual, clip/visual]` and `produces: [clip/visual]`, then a timeline placing `cross-fade` between two `clip/visual` clips passes validation.
- **No enumeration.** The kernel resolves by id + checks types. It never enumerates "every effect" to membership-test a clipType string. A third-party pack's capability is resolved and type-checked through the same path — zero core changes.

Concrete example — the timeline validator (the canonical M×N → M+N proof site):

```python
# BEFORE (name-wired, enumerates every effect):
clip_type = clip.get("clipType", "media")
effect_ids = set(element_catalog.list_effect_ids(theme=active_theme))  # historical catalog scan
if clip_type in effect_ids:                      # membership-test
    _validate_effect_params(...)

# AFTER (id-reference + type-match):
clip_type = clip.get("clipType", "media")
cap = kernel.resolve(clip_type, scope=active_theme)   # id-reference
if cap is not None:                                    # known capability
    kernel.check_consumes(cap, artifact_type="clip/visual")  # type-match
    _validate_effect_params(...)
# else: unknown clipType stays opaque — forward compatibility preserved
```

---

## 3. Conceptual ↔ canonical mapping

The **conceptual contract** uses human-facing names. The **canonical schema** uses internal field names. They are the same contract; the mapping is mechanical.

| Conceptual | Canonical (`CapabilityHandle`) | Notes |
|---|---|---|
| `consumes` | `inputs: tuple[Port, ...]` | Each `Port` carries `name`, `artifact_type`, `type` (transport), `required`, `default` |
| `produces` | `outputs: tuple[Output, ...]` | Each `Output` carries `name`, `artifact_type`, `type`, `mode` |
| `port` | `name` (on `Port` / `Output`) | The logical name of the I/O slot |
| `params` | `schema` + `defaults` | JSON Schema object describing per-invocation parameters |

### Side-by-side snippet

```yaml
# CONCEPTUAL (used across the docs and this guide)
id: flux-dev
kind: model
consumes: [{ port: prompt, type: file, artifact_type: text/prompt }]
produces: [{ port: image,  type: file, artifact_type: image }]
params:  { seed: {type: integer}, steps: {type: integer, default: 28} }
runtime: { adapter: fal, endpoint: "fal-ai/flux/dev" }
```

```yaml
# CANONICAL (what the kernel + CapabilityHandle carry)
id: fal.flux-dev
kind: model
inputs:
  - name: prompt
    type: file
    artifact_type: prompt
    required: true
outputs:
  - name: image
    type: file
    artifact_type: image
    mode: create_or_replace
params:
  schema:
    type: object
    properties:
      seed: { type: integer }
      steps: { type: integer, default: 28 }
    required: []
  defaults: { steps: 28 }
runtime:
  adapter: fal
  endpoint: "fal-ai/flux/dev"
```

**Key difference:** The conceptual form uses `consumes`/`produces` with the `port` sub-key for readability. The canonical form uses `inputs`/`outputs` with `name`. The kernel's `to_capability_handle()` always produces the canonical form; element manifests on disk are parsed into the canonical form by `load_element_definition()`.

---

## 4. Open-string fallback (external-boundary leniency)

The timeline format is shared with the external schema via the external `banodoco_timeline_schema` package. Astrid's artifact types are an **internal** opinion; at the external schema boundary, unknown/foreign types pass through opaque.

**Rules:**

1. **Artifact types are open and extensible.** Packs declare their own types. The registry seeds from built-ins + pack extensions. Unknown types are never rejected — `ArtifactTypeRegistry.resolve(name)` returns `None` for unknowns, and callers treat `None` as "opaque, pass through."
2. **Lenient at the external boundary.** Astrid never tightens a format it doesn't solely own. external-authored timelines with `clipType` values Astrid doesn't recognize remain valid and loadable.
3. **`artifact_type` is never required for load.** Existing on-disk timelines/manifests (and external-authored ones) keep loading unchanged. The field is used-if-present.

This is the "open `clipType`" philosophy generalized — it's what lets 100 packs evolve independent vocabularies without a central enum becoming a chokepoint, and without Astrid breaking a format shared with an external system.

---

## 5. Pack extension

Packs declare their own artifact types via `extensions.artifact_types.types` in the pack manifest. The kernel's `pack_artifact_type_descriptors()` extracts these and feeds them to the registry.

```yaml
# In a pack's manifest (pack.yaml):
extensions:
  artifact_types:
    types:
      - id: depth_map
        aliases: [depth]
        description: "A monochrome depth map image."
      - id: camera_path
        description: "A 3D camera path definition."
```

**Rules:**

- Each entry has `id` (required), `aliases` (optional), and `description` (optional).
- Duplicate ids or conflicting aliases across packs raise `PackValidationError` — packs cannot silently shadow each other.
- Pack-registered types are additive to the built-in set. The registry is a flat namespace (no catalog concept).
- Pack extension is validated atomically: all descriptors in a pack's `types` block must be valid, or none are registered.

The same mechanism that populates `ElementKindRegistry` from `pack.extensions.timeline.kinds` drives `ArtifactTypeRegistry` from `pack.extensions.artifact_types.types` — one proven pattern, applied to two registries.

---

## 6. Running example: flux-dev + cross-fade

Two capabilities, same contract shape, different artifact types + runtime adapters.

### flux-dev (a cloud image model)

```yaml
# Conceptual form
id: flux-dev
kind: model
consumes: [{ port: prompt, type: file, artifact_type: text/prompt }]
produces: [{ port: image,  type: file, artifact_type: image }]
params:  { seed: {type: integer}, steps: {type: integer, default: 28} }
runtime: { adapter: fal, endpoint: "fal-ai/flux/dev" }
```

- **Consumes** a `text/prompt` artifact — the user's generation prompt.
- **Produces** an `image` artifact — the generated output.
- **Runtime** is `fal`, with the specific Flux Dev endpoint.
- **Params** include `seed` (for reproducibility) and `steps` (default 28).

### cross-fade (a Remotion transition element)

```yaml
# Conceptual form
id: cross-fade
kind: transition
consumes: [{ port: outgoing, type: file, artifact_type: clip/visual },
           { port: incoming, type: file, artifact_type: clip/visual }]
produces: [{ port: out,      type: file, artifact_type: clip/visual }]
params:  { durationFrames: {type: integer, default: 8} }
runtime: { adapter: remotion }
```

- **Consumes** two `clip/visual` artifacts — the outgoing and incoming clips.
- **Produces** one `clip/visual` artifact — the blended transition output.
- **Runtime** is `remotion` — `component.tsx` is resolved by convention, not required in the manifest.
- **Params** include `durationFrames` (default 8).

### How composition type-checks

A timeline places `cross-fade` between two clips. The kernel:

1. **Resolves** `cross-fade` by id (from the pack registry + overrides).
2. **Checks** that `cross-fade.consumes` matches the types of the adjacent clips (both `clip/visual` ✓) and that the transition's output type (`clip/visual`) is compatible with the timeline slot.
3. **Injects** the user's `params` (`durationFrames: 12`) and scoped config (theme, if declared).
4. **Dispatches** to the `remotion` adapter.

A third-party pack adding a `wipe-left` transition with `consumes: [clip/visual, clip/visual]` and `produces: [clip/visual]` composes identically — the kernel resolves it by id, checks the types, and dispatches. Zero core changes.

### Validation

See [`docs/examples/capability-contract/`](../examples/capability-contract/) for standalone example manifests and a validation script that confirms all artifact types resolve against the real `ArtifactTypeRegistry`.

---

## 7. Cross-references

- **RFC:** [`docs/RFC-capability-artifact-waist.md`](../RFC-capability-artifact-waist.md) — the original design rationale.
- **Worked example:** [`docs/examples/capability-contract/`](../examples/capability-contract/) — standalone manifests + validation script.
- **Element template:** [`docs/templates/element/`](../templates/element/) — post-S4 canonical element template.
- **Pack contract:** [`docs/packs/contract.md`](../packs/contract.md) — pack manifest schema and discovery.
- **Platform contract:** [`docs/contracts/platform-contract.md`](platform-contract.md) — normative v1 SDK boundary (wins on disagreement).

---

## 8. Non-goals (explicit anti-scope)

- **No streaming/realtime QoS** — artifact types describe data semantics, not transport SLAs.
- **No declarative orchestrator workflow graphs** — composition above the waist stays imperative (`run.py` scripts calling typed capabilities).
- **No `document` primitive** — a timeline is a structured artifact (type `timeline`), not a new primitive peer to artifact/capability.
- **No operational-metadata schema** — cost/latency stay on result objects, not on the capability contract.
- **No closed enum** — the artifact type space is open; packs extend it; unknown types stay opaque.
