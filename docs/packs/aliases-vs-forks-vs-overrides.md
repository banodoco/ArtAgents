# Aliases vs Forks vs Overrides

Three mechanisms for redirecting or customizing capability resolution. This
guide builds on the vocabulary in
[contract.md](contract.md).

## Quick Decision Table

| You want to... | Use | Persistence | Scope |
|---|---|---|---|
| Give a capability a second public name | Alias | In pack manifest | All consumers |
| Make a local copy you can edit freely | Fork | On disk in local pack | Your project |
| Redirect a capability id to a replacement | Override | `.overrides.json` in local pack | Your project |
| Shadow a builtin with a local replacement | Override | `.overrides.json` in local pack | Your project |
| Maintain backward-compat after renaming | Alias | In pack manifest | All consumers |
| Keep an old renderer/planner/finalizer id working | Alias with the matching rendering `kind` | In pack manifest | All render-service callers |
| Redirect one rendering implementation to another | Typed override | `.overrides.json` in local pack | Facade and direct-service calls in your project |

---

## Aliases

**What:** A one-way mapping from a public alias id to a fully-qualified
canonical id, declared in the owning pack's manifest.

**Where they live:** Aliases are a top-level pack manifest field — they live in
`pack.yaml` on the canonical pack that owns the target capability, not in the
capability's own manifest. This keeps alias ownership explicit: the pack that
provides the canonical capability declares the legacy ids that route to it.

**Schema (pack.json v1):**

Each alias entry is an object with:

| Field | Required | Type | Description |
|---|---|---|---|
| `kind` | Yes | `"executor"`, `"orchestrator"`, `"renderer"`, `"planner"`, or `"finalizer"` | The capability kind the alias routes to |
| `alias` | Yes | Qualified id (`pack.slug`) | The old or alternate public id |
| `canonical_id` | Yes | Qualified id (`pack.slug`) | The canonical id this alias points to |
| `deprecated` | No | `boolean` (default `false`) | Whether the alias is deprecated |
| `deprecation_message` | No | `string` (default `""`) | Human-readable deprecation note shown in inspect/search |

Both `alias` and `canonical_id` must be qualified ids (e.g. `rendering.render`,
not bare `render`). Element aliases are still deferred; renderer, planner, and
finalizer aliases are independent rendering-registry namespaces.

**Example** in `pack.yaml`:

```yaml
# In astrid/packs/rendering/pack.yaml
aliases:
  - kind: executor
    alias: builtin.render
    canonical_id: rendering.render
    deprecated: true
    deprecation_message: "Moved to rendering.render — update your references"
  - kind: renderer
    alias: rendering.old-remotion
    canonical_id: rendering.remotion
    deprecated: true
    deprecation_message: "Use rendering.remotion"
```

Multiple aliases can point to the same canonical id, and aliases are resolved
transitively — chains of aliases are flattened to the ultimate canonical target.
Cycle detection runs at registration time and rejects invalid alias graphs.

**How it works:** The `AliasResolver` (in `astrid/core/pack/alias_resolver.py`)
maintains a registry of `alias → canonical_id` mappings. Aliases are loaded from
`PackDefinition.aliases` during registry construction, filtered by `kind`, and
registered with their deprecation metadata and source pack id preserved. Both
the executor and orchestrator registries wire aliases from discovered packs
automatically — no separate registration step is needed.

**Backward compatibility:** Old ids like `builtin.*`, `external.*`, and
declared one-off aliases such as `upload.youtube` remain functional when
declared as aliases. Registry lookup,
`inspect --json`, and search all resolve the old id to the canonical definition
and surface deprecation metadata. The old ids do not need their own capability
definitions — they are pure alias entries.

**Deprecation metadata is non-fatal.** A deprecated alias still resolves; the
deprecation flag and message are informational, shown in `inspect` output and
search records. Consumers can use the message to plan migration without being
blocked.

**What aliases are NOT:**

- **Element aliases** — element kinds are not accepted. Element aliasing is
  deferred to a future milestone.
- **Component-level `metadata.aliases`** — The `metadata.aliases` field on
  individual executor/orchestrator manifests (e.g. `executor.yaml`) is legacy
  validation-only coverage. It is checked during static validation but is not
  loaded into the alias resolver. Do not use it for new alias declarations;
  use the pack-level `aliases` field instead.

**When to use:** You renamed a capability but old consumers still reference the
old id. Instead of breaking them, add a pack-level alias.

**When NOT to use:** You want to change behavior. Aliases are identity-only;
they don't alter execution. Use a fork or override for behavioral changes.

---

## Forks

**What:** A complete local copy of a capability that you own and can modify.

**How it works:** The fork command copies the capability's manifest, entrypoint,
and supporting files into your local pack. The forked copy gets a new qualified
id under the `local` pack namespace. Provenance metadata tracks the original
source.

### Fork Commands

```bash
# Shallow fork — copy just this capability
python3 -m astrid executors fork rendering.render
python3 -m astrid orchestrators fork video_editing.hype
python3 -m astrid elements fork effects text-card

# Deep fork — recursively fork all child executors/orchestrators too
python3 -m astrid executors fork generation.generate_image --deep
python3 -m astrid orchestrators fork video_editing.hype --deep

# Overwrite an existing fork
python3 -m astrid executors fork rendering.render --overwrite
```

### Fork Provenance

Each forked capability records:
- `forked_from` — the original canonical id
- `upstream_version` — the version at fork time
- `file_hashes` — SHA-256 hashes of all files at fork time (stored in
  `.astrid_fork_state.json`)

This provenance powers dirty detection (see [fork-and-update.md](fork-and-update.md)).

### Shallow vs Deep

- **Shallow** (`--deep` not set): Copy only the named capability. Its child
  references still point to the original builtin executors/orchestrators.
- **Deep** (`--deep`): Recursively fork all child executors and orchestrators
  referenced by an orchestrator's graph. Elements only support shallow forks.

**When to use:** You want to customize a capability's behavior without affecting
the original. The fork becomes your copy — edit freely.

**When NOT to use:** You just want to use a different capability id. Use an
alias or override instead.

---

## Overrides

**What:** A redirection rule that says "when anything asks for capability X,
give it capability Y instead."

**How it works:** The `OverrideStore` (in `astrid/core/pack/override.py`) maintains
a thread-safe in-memory mapping of `(type, id) → target_id`, persisted to
`astrid/packs/local/.overrides.json`. Overrides are checked at resolution time
— whenever a registry looks up a capability by id, the override store is
consulted after alias resolution.

**Canonical-id keying:** Override keys are the *canonical* capability id, not
the alias. When a caller requests `builtin.render` (a legacy alias), the
registry first resolves it to `rendering.render` (the canonical id), then
checks the override store for `("executor", "rendering.render")`. This means
one override covers all aliases that point to the same canonical target — you
do not need to set separate overrides for each alias.

### Override Commands

```bash
# Route all requests for rendering.render to your local fork
python3 -m astrid executors override set rendering.render local.render

# Route an element to a replacement
python3 -m astrid elements override set effects text-card effects my-text-card

# List all active overrides
python3 -m astrid executors override list
python3 -m astrid orchestrators override list
python3 -m astrid elements override list

# Remove an override
python3 -m astrid executors override remove rendering.render
```

### Common Override Pattern: Fork + Override

1. Fork the capability: `python3 -m astrid executors fork rendering.render`
2. Edit the local copy at `astrid/packs/local/executors/render/`
3. Set the override: `python3 -m astrid executors override set rendering.render local.render`

Now every consumer that references `rendering.render` (or its legacy alias
`builtin.render`) gets your customized version transparently.

**When to use:** You have a fork (or another pack's capability) and want it to
be the default resolution for a given id.

**When NOT to use:** You want the original and your copy to coexist under
different ids. Just fork without setting an override.

---

## Interaction Between the Three

Resolution order when looking up a capability id:

1. **Alias resolution** — is the id an alias? If yes, resolve transitively to
   the canonical id.
2. **Override check** — is there an active override for the *canonical* id? If
   yes, return the override target's definition.
3. **Registry lookup** — find the capability by canonical id in the loaded
   registries and return its definition.

This means aliases resolve before overrides, and override keys are canonical ids
rather than alias ids. One override covers every alias that routes to the same
canonical target. Both alias resolution and override redirection are transparent
to the caller — the returned definition is the final canonical or override
definition, with alias metadata attached to the capability handle's provenance
for informational display.

## Rendering Implementations

Renderer, planner, and finalizer resolution uses the same ordering, but each is
its own namespace. These keys are distinct:

```json
{
  "executor": {"rendering.render": "local.render"},
  "renderer": {"rendering.remotion": "video_tool.renderer"},
  "planner": {"rendering.legacy_hybrid": "video_tool.planner"},
  "finalizer": {"rendering.ffmpeg-finalizer": "video_tool.finalizer"}
}
```

An `executor` override replaces the public `rendering.render` capability before
the facade runs. The other three override only implementation selection inside
`RenderService`; they apply to both facade calls and direct public-service
calls. Changing one kind never redirects another.

The rendering registries apply the following verified rules:

1. Resolve the requested alias transitively to its canonical id.
2. Apply an override keyed by that canonical id and implementation kind.
3. Select the highest-precedence execution-eligible candidate for the final id.
4. Record the requested id, alias chain, `{from,to}` override, source pack,
   manifest digest, and trust eligibility in resolution evidence and render
   provenance.

Only aliases from execution-eligible packs can redirect execution. Aliases from
environment-only or otherwise untrusted packs remain visible to inspection but
cannot shadow an executable implementation. When a higher-precedence alias
chain ends at a missing or ineligible target, resolution may use the next
eligible declaration for that alias. A trusted alias whose canonical target is
absent remains usable when an override explicitly routes that canonical id to
an eligible implementation. Alias cycles, missing override targets, and
ineligible override targets fail closed.

`rendering.render` is reserved for the executor facade. A renderer registration,
alias terminal, or renderer override that resolves to it is rejected as facade
recursion. The legacy short names `remotion` and `ffmpeg` are core compatibility
aliases for renderer lookup, while the facade's legacy selector
`engine=remotion` retains its characterized auto-route policy. To demand the
Remotion implementation strictly, select the qualified id
`backend=rendering.remotion`; qualified selectors have no implicit fallback.

Renderer/planner/finalizer overrides are stored by the same project-local
`OverrideStore` in `astrid/packs/local/.overrides.json`. There is no separate
backend override file or backend-specific override format. Pack manifests may
declare aliases of `kind: renderer`, `kind: planner`, and `kind: finalizer`;
their extension manifests are registered through
`extensions.rendering.renderers`, `.planners`, and `.finalizers` respectively.
The current CLI exposes override management for executors, orchestrators, and
elements only; do not invent `astrid renderers override ...` commands. Rendering
hosts and tests set these typed mappings through `OverrideStore` until a public
rendering-registry CLI is added.
