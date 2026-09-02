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
| Select a rendering implementation | Qualified renderer/planner/finalizer id | Invocation or plan | Rendering callers |
| Redirect one rendering implementation to another | Typed override | `.overrides.json` in local pack | Facade and direct-service calls in your project |

---

## Aliases

**What:** A one-way mapping from a public alias id to a fully-qualified
canonical id, declared in the owning pack's strict-v2 manifest.

**Where they live:** Aliases are a top-level `pack.yaml` field on the canonical
pack that owns the target capability. This keeps alias ownership explicit.

**Schema:** The `aliases` array is defined by
`astrid/core/pack/schemas/v2/pack.json`. Each entry contains:


| Field | Required | Type | Description |
|---|---|---|---|
| `kind` | Yes | `"executor"`, `"orchestrator"`, `"planner"`, or `"finalizer"` | The capability kind the alias routes to |
| `alias` | Yes | Qualified id (`pack.slug`) | The old or alternate public id |
| `canonical_id` | Yes | Qualified id (`pack.slug`) | The canonical id this alias points to |

Both `alias` and `canonical_id` must be qualified ids (e.g. `rendering.render`,
not bare `render`). Renderer implementation selection is always by the
qualified id declared by its owning pack.

**Example** in `pack.yaml`:

```yaml
# In a pack manifest
aliases:
  - kind: executor
    alias: video_tool.old_executor
    canonical_id: video_tool.executor
```

Multiple aliases can point to the same canonical id, and aliases are resolved
transitively — chains of aliases are flattened to the ultimate canonical target.
Cycle detection runs at registration time and rejects invalid alias graphs.

**How it works:** The `AliasResolver` (in `astrid/core/pack/alias_resolver.py`)
maintains a registry of `alias → canonical_id` mappings. Aliases are loaded from
`PackDefinition.aliases` during registry construction, filtered by `kind`, and
registered with their source pack id preserved. Executor, orchestrator, planner,
and finalizer registries wire aliases from discovered packs automatically.

Aliases are optional identity metadata. A declared alias resolves to its
qualified canonical id and does not create a second capability definition.

Bundled product packs currently declare no aliases. In particular, do not add
aliases for `pack.yml`, `pack.json`, `schema-pack.yaml`, or removed bundled
capability namespaces; those are retired forms, not supported identities.

**What aliases are not:**

- element aliases;
- component-level `metadata.aliases` as a replacement for the pack-level field;
- a behavioral fork or a database composition mechanism.

Use a fork or typed override when behavior must change.

## Forks

**What:** A complete local copy of a capability that you own and can modify.

**How it works:** Forking a capability copies its manifest, entrypoint, and
supporting files into your local pack, giving the forked copy a new qualified
id under the `local` pack namespace. Provenance metadata tracks the original
source.

- **Shallow fork** — copy just the named capability. Its child references
  still point to the original shipped executors/orchestrators.
- **Deep fork** — recursively fork all child executors and orchestrators
  referenced by an orchestrator's graph. Elements only support shallow forks.
- **Overwrite** — re-fork over an existing fork, replacing it.

### Fork Provenance

Each forked capability records:
- `forked_from` — the original canonical id
- `upstream_version` — the version at fork time
- `file_hashes` — SHA-256 hashes of all files at fork time (stored in
  `.astrid_fork_state.json`)

This provenance powers dirty detection (see [fork-and-update.md](fork-and-update.md)).

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

**Canonical-id keying:** Override keys are the *canonical* capability id. A
caller selects the qualified id directly, and the registry checks the override
store for `("executor", "rendering.render")`. One override therefore targets
the canonical implementation without any alternate renderer spelling.
### Override Mechanisms

Overrides are managed by editing `astrid/packs/local/.overrides.json`, which
maps canonical ids to their replacement ids per capability kind:

- Route all requests for `rendering.render` to your local fork — add
  `{"executor": {"rendering.render": "local.render"}}`.
- Route an element to a replacement — add an entry under the element kind
  key, mapping the element id to its replacement (e.g.
  `{"effects": {"text-card": "my-text-card"}}`).
- List all active overrides — read the same file.
- Remove an override — delete its entry from the file.

### Common Override Pattern: Fork + Override

1. Fork the capability into the local pack (see Forks above).
2. Edit the local copy at `astrid/packs/local/executors/render/`.
3. Add the override to `astrid/packs/local/.overrides.json`:
   `{"executor": {"rendering.render": "local.render"}}`.

Now every consumer that references `rendering.render` gets your customized
version transparently.
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

Renderer, planner, and finalizer IDs are separate namespaces. Renderer
implementation selection is qualified-only: rendering packs declare no renderer
aliases, and the registry rejects every unqualified renderer selector. Planner
and finalizer aliases, when declared by their owning pack, follow the normal
alias/override ordering. These keys are distinct:

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

1. Require the requested renderer, planner, or finalizer id to be qualified.
2. Resolve only declared planner/finalizer aliases; renderer aliases are not
   accepted.
3. Apply an override keyed by that qualified id, when one is configured.
4. Select the highest-precedence execution-eligible candidate.
5. Record the requested id, override, source pack, manifest digest, and trust
   eligibility in resolution evidence and render provenance.

`rendering.render` is reserved for the executor facade. A renderer registration
or renderer override that resolves to it is rejected as facade recursion.
Renderer, planner, and finalizer implementations are selected by their
qualified ids; unqualified renderer selectors are rejected. Typed overrides
remain available when a project intentionally routes one qualified
implementation to another.
Renderer/planner/finalizer overrides are stored by the same project-local
`OverrideStore` in `astrid/packs/local/.overrides.json`. There is no separate
backend override file or backend-specific override format. Their extension
manifests are registered through
`extensions.rendering.renderers`, `.planners`, and `.finalizers` respectively.
Override management for executor, orchestrator, and element ids happens
through the project-local `OverrideStore` and its
`astrid/packs/local/.overrides.json` file; do not invent
astrid renderers override gateway commands. Rendering
hosts and tests set these typed mappings through `OverrideStore` until a public
rendering-registry CLI is added.

The `renderers` CLI surface today is `python3 -m astrid.core.rendering.cli
create|list|inspect|validate|smoke|replay`: `create <name> <dest>` scaffolds the
four-file renderer pack, `list` prints every discovered
renderer/planner/finalizer qualified id, `inspect <id>` shows one candidate's
manifest fields and trust eligibility, `validate <path>` statically validates
a pack directory, `smoke <id>` runs a deterministic direct-service render
against an execution-eligible candidate, and `replay <bundle-dir>` re-runs a
captured failure bundle with its pinned digests (refusing silent backend
substitution and bundle tampering unless `--acknowledge-drift` is passed). A
trusted install uses `python3 -m astrid.core.pack.cli install --trust --yes`,
and a failed invocation is debugged from its
retained replay bundle. See the golden path in
[render-backend-v1.md](../contracts/render-backend-v1.md#renderer-author-golden-path)
and the worked `replay` example in
[render-backend-v1.md](../contracts/render-backend-v1.md#the-replay-verb).
