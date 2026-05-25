# Discovery for Agents

How a cold agent discovers what Astrid can do — no source grep required.

## The Contract

Agents discover capabilities exclusively through CLI surfaces that read pack
manifests. Never inspect `astrid/packs/` directory trees, guess ids from
filenames, or import Python modules directly. The pack system owns discovery;
agents consume it.

Capability discovery is session-gated. From a cold shell, run
`python3 -m astrid next` for exactly one legal action, or `python3 -m astrid
status` for the read-side breadcrumb. Attach before running `skills list`,
capability `list`, `search`, or `inspect` commands. The unbound CLI surface is
intentionally narrow: help/version, `status`, `next`, `attach`, `packs ...`,
`projects ls`, `projects create`, `projects default`, `sessions ls`, and
`sessions takeover`.

Every discoverable capability (executor, orchestrator, element) belongs to a
pack and is exposed through a consistent list/search/inspect surface with a
`--json` flag for machine consumption.

See the formal vocabulary in
[docs/megaplan/epics/pack-system/pack-contract.md](megaplan/epics/pack-system/pack-contract.md).

## Three Capability Kinds

| Kind | CLI path | Purpose | Example |
|---|---|---|---|
| Executor | `executors` | Single-step tool (render, transcribe, generate) | `builtin.render` |
| Orchestrator | `orchestrators` | Multi-step pipeline (plan → execute → verify) | `builtin.hype` |
| Element | `elements` | Reusable render building block (effect, animation) | `effects/text-card` |

## Step-by-Step Discovery Flow

If the session is not already bound, bootstrap first:

```bash
python3 -m astrid next
python3 -m astrid status
python3 -m astrid attach <project>
```

### 1. List available skills (optional bootstrap)

```bash
python3 -m astrid skills list --json
```

Returns packs with installable skill descriptors and harness support. This is
the entry point for agents that need to install new capability packs.

### 2. Search for capabilities

```bash
# Find executors matching a term
python3 -m astrid executors search image --json

# Find orchestrators matching a term
python3 -m astrid orchestrators search hype --json
```

Each search returns `{"hits": [{"id": "...", "kind": "...", "score": N, "short_description": "..."}]}`.
Scores are BM25-ranked; higher is better.

Filter by pack with `--pack <pack_id>`. Limit results with `--limit N`.

### 3. List all capabilities (when you need the full catalog)

```bash
python3 -m astrid executors list --json
python3 -m astrid orchestrators list --json
python3 -m astrid elements list --json [--kind effects|animations|transitions]
```

The `--json` flag emits structured output. Without it, output is human-readable
tables.

### 4. Inspect a capability

```bash
# The inspect shape reveals the _capability identity block + full definition
python3 -m astrid executors inspect builtin.generate_image --json
python3 -m astrid orchestrators inspect builtin.hype --json
python3 -m astrid elements inspect effects text-card --json
```

The JSON output merges `_capability` (identity, provenance, deprecation,
aliases, edit state) with the full capability definition (inputs, outputs,
isolation, graph, metadata).

Use `--show-overrides` to see if an override is active for this capability.
Use `--pack <pack_id>` to require the resolved capability to belong to a
specific pack.

## The `_capability` Identity Block

Every inspect response includes a `_capability` section with:

- `canonical_id` — the fully-qualified id (e.g., `"builtin.generate_image"`)
- `local_id` — the id without pack prefix (e.g., `"generate_image"`)
- `kind` — `"executor"`, `"orchestrator"`, or the element kind
- `pack_id` — owning pack (e.g., `"builtin"`)
- `aliases` — list of public alias names
- `deprecated` / `deprecation_message` / `deprecated_alternatives`
- `provenance` — `source` (pack or active_theme), `version`, `content_root`
- `local_edit_state` — `"clean"` (no local edits), `"dirty"` (modified), or `"conflict"`
- `safety` — `network` flag (bool)

## Picking the Right Capability Kind

- **Need a single, concrete operation?** Use an executor. They take inputs,
  produce outputs, and run in one shot.
- **Need a multi-step workflow with decisions?** Use an orchestrator. They
  compose child executors and orchestrators.
- **Need a render building block?** Use an element. They're reusable visual
  components (effects, animations, transitions) assembled by render pipelines.

## Why Source Grep Is Wrong

- Executor ids live in YAML/JSON manifests, not Python filenames.
- Aliases mean the same capability may appear under multiple names.
- Overrides mean the active implementation for an id may not match the source
  file at the default path.
- Packs can be hidden, optional, or installed externally — `grep` won't find
  them.
- The pack system validates manifests at load time; raw file scraping has no
  equivalent safety.

Always use the CLI surfaces described above. They are the contract.
