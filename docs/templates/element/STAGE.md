# Element Template — Post-S4 Canonical Form

Commands below use example/placeholder ids — after scaffolding, substitute your
own capability id.

## Quick start

```bash
# List all effects (or transitions, animations) — the kind you registered
python3 -m astrid.core.element.cli list --kind effects

# Inspect your new element manifest
python3 -m astrid.core.element.cli inspect effects example-card --json
```

---

## Manifest shape (canonical)

The canonical element manifest uses `inputs`/`outputs` with `artifact_type`
and declares a `runtime` adapter. This is the form that
`load_element_definition()` parses.

```json
{
  "schema_version": 1,
  "id": "example-card",
  "kind": "effect",
  "pack_id": "example_pack",
  "inputs": [
    {
      "name": "clip",
      "type": "clip",
      "required": true,
      "artifact_type": "clip/visual",
      "description": "The input clip."
    }
  ],
  "outputs": [
    {
      "name": "clip",
      "type": "clip",
      "artifact_type": "clip/visual",
      "description": "The transformed output clip."
    }
  ],
  "schema": {
    "type": "object",
    "required": ["content"],
    "properties": {
      "content": { "type": "string" }
    }
  },
  "defaults": {
    "content": ""
  },
  "dependencies": {
    "js_packages": [],
    "python_requirements": []
  },
  "runtime": {
    "adapter": "remotion"
  }
}
```

### Key fields

| Field | Required? | Purpose |
|---|---|---|
| `id` | yes | Globally-unique capability identifier (e.g. `example-card`). |
| `kind` | yes | Element kind (`effect`, `transition`, `animation`). Must match the folder name. |
| `inputs` | no | Typed input ports. Each carries `name`, `type`, `artifact_type`, `required`, `description`. |
| `outputs` | no | Typed output ports. Each carries `name`, `type`, `artifact_type`, `description`. |
| `schema` | no | JSON Schema describing per-invocation parameters. |
| `defaults` | no | Default values for schema properties. |
| `dependencies` | no | JS packages and Python requirements for this element. |
| `runtime` | no | Which adapter runs this element (`remotion`, `shell`, etc.) plus adapter-specific config. |
| `metadata` | no | Display label, usage guidance, pack assignment. |

### `artifact_type` — the semantic waist

Every input/output port declares an `artifact_type` (e.g. `clip/visual`,
`image`, `prompt`). This is the semantic type that the kernel uses for
composition type-checking. Values must be canonical ids or registered aliases
from the `ArtifactTypeRegistry`.

See the [contract guide](../../contracts/capability-artifact-contract.md)
for the full artifact type vocabulary and composition rules.

---

## Conceptual form (mental model)

For human reasoning, the same contract is often expressed in a **conceptual**
form that uses `consumes`/`produces`/`port` instead of `inputs`/`outputs`/`name`:

```yaml
# Conceptual form — human-readable, NOT loadable by load_element_definition()
id: example-card
kind: effect
consumes:
  - port: clip
    type: file
    artifact_type: clip/visual
produces:
  - port: clip
    type: file
    artifact_type: clip/visual
params:
  content: { type: string }
runtime:
  adapter: remotion
```

The mapping is mechanical: `consumes` ↔ `inputs`, `produces` ↔ `outputs`,
`port` ↔ `name`, `params` ↔ `schema`+`defaults`. See the
[contract guide §3](../../contracts/capability-artifact-contract.md#3-conceptual--canonical-mapping)
for side-by-side snippets.

---

## `component.tsx` — Remotion adapter convention

When `runtime.adapter` is `remotion`, the element's `component.tsx` is
**resolved by convention** — the kernel looks for `component.tsx` in the
element directory. It is not declared in the manifest.

- If `runtime.adapter` is present and set to `remotion`, `component.tsx`
  is optional (the adapter resolves it by path convention).
- If no runtime adapter is declared, `component.tsx` is **required** and
  the kernel defaults to the remotion adapter.

The manifest declares the **contract** (what artifact types this element
consumes and produces, what params it accepts). The `component.tsx`
implements the **render behavior** for that contract.

```tsx
// component.tsx — resolved by the remotion adapter convention.
// The manifest (element.yaml) declares the capability contract:
// inputs/outputs with artifact_type, params schema, and defaults.
export default function ExampleCard() {
  return null;
}
```
