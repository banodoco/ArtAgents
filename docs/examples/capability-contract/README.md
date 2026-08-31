# Capability Contract — Worked Example

Two concrete manifests in **conceptual form** plus a validation script that
confirms every `artifact_type` resolves against the real
`ArtifactTypeRegistry`.

- **Contract guide:** [`docs/contracts/capability-artifact-contract.md`](../../contracts/capability-artifact-contract.md)
- **Element template:** [`docs/templates/element/`](../../templates/element/)

---

## The two manifests

| | `flux-dev.model.yaml` | `cross-fade.element.yaml` |
|---|---|---|
| **Kind** | `model` | `transition` |
| **Consumes** | `prompt` (artifact_type: `prompt`) | `outgoing` + `incoming` (artifact_type: `clip/visual`) |
| **Produces** | `image` (artifact_type: `image`) | `out` (artifact_type: `clip/visual`) |
| **Runtime** | `fal` (cloud API) | `remotion` (component.tsx by convention) |
| **Params** | `seed`, `steps` (default 28) | `durationFrames` (default 8) |

### flux-dev — a cloud image model

```yaml
# Conceptual form
id: flux-dev
kind: model
consumes: [{ port: prompt, type: file, artifact_type: prompt }]
produces: [{ port: image,  type: file, artifact_type: image }]
params:  { seed: {type: integer}, steps: {type: integer, default: 28} }
runtime: { adapter: fal, endpoint: "fal-ai/flux/dev" }
```

### cross-fade — a Remotion transition element

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

### Composition in one paragraph

A timeline places `cross-fade` between two clips. The kernel **resolves** `cross-fade`
by id (from the pack registry), **type-checks** that the transition's `consumes` entries
(`clip/visual`, `clip/visual`) match the adjacent clips and that the output
(`clip/visual`) fits the timeline slot, **injects** user params (`durationFrames: 12`)
and scoped config (theme), then **dispatches** to the `remotion` adapter.
A third-party pack adding `wipe-left` with the same artifact-type signature
composes identically — the kernel resolves it by id and validates types;
zero core changes.

---

## Conceptual ↔ canonical mapping

The manifests above use the **conceptual** form (`consumes`/`produces`/`port`)
for human readability. The canonical schema uses `inputs`/`outputs`/`name`.
The mapping is mechanical:

| Conceptual | Canonical (`CapabilityHandle`) | Notes |
|---|---|---|
| `consumes` | `inputs: tuple[Port, ...]` | Each `Port` carries `name`, `artifact_type`, `type`, `required`, `default` |
| `produces` | `outputs: tuple[Output, ...]` | Each `Output` carries `name`, `artifact_type`, `type`, `mode` |
| `port` | `name` (on `Port` / `Output`) | The logical name of the I/O slot |
| `params` | `schema` + `defaults` | JSON Schema object describing per-invocation parameters |

See the [contract guide](../../contracts/capability-artifact-contract.md#3-conceptual--canonical-mapping)
for side-by-side YAML snippets of both forms.

---

## Validation

Run the validation script:

```bash
python3 docs/examples/capability-contract/validate.py
```

This performs two checks:

1. **Conceptual resolution** — parses the conceptual-form YAMLs with
   `yaml.safe_load`, extracts every `artifact_type` value from `consumes`
   and `produces`, and confirms each resolves against the real
   `ArtifactTypeRegistry`.

2. **Canonical smoke test** — loads the real `cross-fade` element manifest
   at `astrid/packs/rendering/elements/transitions/cross-fade/` via
   `load_element_definition()` and verifies its `inputs`/`outputs` artifact
   types are known.

All artifact types used (`prompt`, `image`, `clip/visual`) are built-in
canonical ids seeded in the registry.

---

## Open-string fallback

Unknown artifact types never fail validation — the registry's `resolve()`
returns `None` for unknowns, and callers treat that as "opaque, pass through."
This is the external-boundary leniency rule (see
[contract guide §4](../../contracts/capability-artifact-contract.md#4-open-string-fallback-external-boundary-leniency)).
The example manifests deliberately use only canonical ids to demonstrate
the type-checked path, but the system never rejects unrecognized types.

---

## File listing

```
docs/examples/capability-contract/
├── README.md                  ← this file
├── flux-dev.model.yaml        ← conceptual form: cloud image model
├── cross-fade.element.yaml    ← conceptual form: Remotion transition
└── validate.py                ← validation script (run to verify)
```
