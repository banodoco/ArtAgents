# Discovery for Agents

How a cold agent discovers what Astrid can do — no source grep required.

## The Contract

Agents discover capabilities through the SDK (`astrid.sdk.discover`,
`astrid.sdk.get_capability`), which reads pack manifests. Never inspect
`astrid/packs/` directory trees, guess ids from filenames, or import Python
modules directly. The pack system owns discovery; agents consume it.

Capability manifests describe executable sources only. Astrid has no local
schema-pack host or migration stream: durable product state and all DDL are
owned by the neutral workspace runtime. Do not add a schema manifest or a
local migration directory to a capability pack.

There is no session binding and no `next`/`status`/`attach` bootstrap: the
gateway CLI (`python3 -m astrid`) owns exactly the eight families (projects,
timelines, media, tasks, runs, serve, doctor, backup), and capability
discovery is an SDK call. `--json` on the product families is the machine
surface for kernel data (projects, timelines, media, tasks, runs); capability
metadata comes from `astrid.sdk.discover()`.

```python
import astrid.sdk as sdk

inventory = sdk.discover()  # manifest-ledger packs, pack by pack
cap = sdk.get_capability(
    "rendering.render", kind="executor"
)  # typed lookup of one capability
```

Discovery is read-only and manifest-ledger based.  It includes in-tree packs
and only explicitly configured external roots (`extra_pack_roots` or
`ASTRID_PACKS_PATH`); there is no user-local installed-pack overlay or install
mutation path.

Every discoverable capability (executor, orchestrator, element) belongs to a
pack and is exposed through a consistent discovery surface.

See the formal vocabulary in
[docs/packs/contract.md](../packs/contract.md).

For the taxonomy fields that classify packs for discovery and filtering
(`origin`, `install_tier`, `pack_type`, `domain`, `stability`, `support`),
see [docs/packs/pack-taxonomy.md](../packs/pack-taxonomy.md).

## Three Capability Kinds

| Kind | SDK surface | Purpose | Example |
|---|---|---|---|
| Executor | `sdk.get_capability` / `sdk.invoke` | Single-step tool (render, transcribe, generate) | `rendering.render` |
| Orchestrator | `sdk.get_capability` / `sdk.invoke` | Multi-step pipeline | `video_editing.hype` |
| Element | `sdk.get_capability` / `sdk.invoke` | Reusable render building block (effect, animation) | `effects/text-card` |

## Step-by-Step Discovery Flow

### 1. Get the full catalog

```python
import astrid.sdk as sdk
inventory = sdk.discover()
```

`discover()` returns a `DiscoveryResult`: the discovered pack inventory, each
pack's capabilities (executors, orchestrators, elements), and per-capability
metadata. There is no separate "skills list" step — pack skills are the
`SKILL.md` files the pack ships (see the core skill at
`astrid/packs/_core/skill/SKILL.md`).

### 2. Look up one capability

```python
cap = sdk.get_capability(
    "generation.generate_image", kind="executor"
)
```
`get_capability` resolves the qualified id (aliases included) and raises the
typed `CapabilityNotFoundError` / `CapabilityAmbiguousError` on failure.

### 3. Inspect the capability definition

The resolved capability carries the `_capability` identity block plus the full
definition (inputs, outputs, isolation, graph, metadata) — see below.

### 4. Run it

```python
result = sdk.invoke(
    "iteration.experiment_review",
    kind="executor",
    inputs={"review": "experiments/prompt-brevity/review.json"},
    project="my-project",
)
```

`invoke` returns an `InvocationResult` with the produced outputs and
provenance. `kind` is required, and every executor run belongs to exactly
one project: pass `project=<slug>` and omit `out` — project-scoped runs
write inside the project's own `runs/<run-id>/` tree. Input names map to
the executor's declared inputs and flags (`--input name=value` style).

## The `_capability` Identity Block

Every inspect response includes a `_capability` section with:

- `canonical_id` — the fully-qualified id (e.g., `"generation.generate_image"`)
- `local_id` — the id without pack prefix (e.g., `"generate_image"`)
- `kind` — `"executor"`, `"orchestrator"`, or the element kind
- `pack_id` — owning pack (e.g., `"generation"`)
- `aliases` — list of public alias names
- `deprecated` / `deprecation_message` / `deprecated_alternatives`
- `provenance` — `source` (pack or active_theme), `version`, `content_root`
- `safety` — `network` flag (bool)

## Picking the Right Capability Kind

- **Need a single, concrete operation?** Use an executor. They take inputs,
  produce outputs, and run in one shot.
- **Need a multi-step workflow with decisions?** Use an orchestrator. They
  compose child executors and orchestrators.
- **Need a render building block?** Use an element. They're reusable visual
  components (effects, animations, transitions) assembled by render pipelines.

## Recoverable CLI Choices

Astrid CLI parsers use structured enum helpers so that invalid values produce
machine-readable errors instead of raw argparse stderr with `SystemExit(2)`.
Agents can read these errors to discover valid values without consulting
`--help` or source code.

### How It Works

Every CLI argument that accepts a constrained set of values is wired through
`add_kind_arg()` (for registry-backed timeline kinds) or `add_choice_arg()`
(for static enum choices).  These helpers attach `RegistryChoices` or
`StaticChoices` objects to the argparse action, and the parser itself is an
instance of `RecoverableArgumentParser`.

When an invalid value is passed:

1. `RecoverableArgumentParser._check_value()` detects the failure.
2. It raises `AstridArgumentError` (a `ValueError` subclass) instead of
   calling `sys.exit(2)`.
3. The `AstridArgumentError` carries:
   - `message` — the argparse-style error text
   - `argument_name` — the flag/dest name (e.g., `"--kind"`)
   - `invalid_value` — the value the user typed
   - `valid_options` — the tuple of allowed values
   - `catalog` — the registry catalog name for kind args (e.g., `"clip"`,
     `"track"`, `"transition"`), or `None` for static choices

### The Agent Recovery Pattern

When an agent invokes a command with an invalid enum value, the stderr output
will contain the structured envelope markers described in
[docs/error-model.md](../contracts/error-model.md).  Specifically:

```
valid options: cross-fade, cut, fade
recovery: retry the command with one of the listed valid options
```

The agent should:

1. Parse the `valid options:` line to discover the accepted values.
2. Retry the command with a value from that list.
3. If the error includes a `recovery:` line, prefer that exact command.

No `--help` scan or source grep is needed — the error itself carries the
recovery metadata.

### Authoring Rules for Pack Authors

When you add a new CLI argument to a pack `run.py`:

- **For registry-backed timeline kinds** (clip, track, transition catalogs):
  use `add_kind_arg()`.  Do not pass a bare `choices=` list — the helper
  derives choices from the live `ElementKindRegistry`.

  ```python
  from astrid.core.cli_choices import add_kind_arg, RecoverableArgumentParser

  parser = RecoverableArgumentParser(prog="my-pack")
  add_kind_arg(parser, "--kind", catalog="clip", default="video",
               help="Clip kind")
  ```

- **For static enum choices** (model names, modes, formats): use
  `add_choice_arg()`.

  ```python
  from astrid.core.cli_choices import add_choice_arg, RecoverableArgumentParser

  parser = RecoverableArgumentParser(prog="my-pack")
  add_choice_arg(parser, "--format", values=("mp4", "webm", "gif"),
                 default="mp4", help="Output format")
  ```

- **Always use `RecoverableArgumentParser`** instead of plain
  `argparse.ArgumentParser`.  It preserves normal argparse behavior for
  `--help` and non-choice parse errors while routing invalid enum values
  through `AstridArgumentError`.

- **At the pack entrypoint**, catch `AstridArgumentError` and convert it to
  an `AstridError` so the renderer produces the structured envelope:

  ```python
  from astrid.core.contracts.errors import AstridError

  try:
      args = parser.parse_args(argv)
  except AstridArgumentError as exc:
      raise AstridError(
          exc.message,
          valid_options=exc.valid_options,
          recovery_command=f"retry with --{exc.argument_name.replace('--', '')} "
                           f"<one of: {', '.join(exc.valid_options)}>",
      ) from exc
  ```

  (If the pack entrypoint is wrapped by `guard_canonical_entrypoint`, the
  `AstridArgumentError` will be caught and rendered automatically — the
  explicit conversion is only needed for custom entrypoints.)

## Extending Timeline Kinds via pack.yaml

Packs can extend the built-in timeline kind catalogs (`transition`, `clip`,
`track`) by declaring `extensions.timeline.kinds` in their `pack.yaml`
manifest.

### Schema

Each entry in `extensions.timeline.kinds` is an object with:

| Field | Required | Type | Description |
|---|---|---|---|
| `catalog` | yes | `"transition" \| "clip" \| "track"` | Which built-in catalog to extend. |
| `id` | yes | `str` | Canonical kind identifier (e.g., `"cross-fade"`, `"video"`, `"caption"`). |
| `aliases` | no | `list[str]` | Additional names accepted as input (canonicalized to `id`). |
| `default` | no | `bool` | When `true`, this kind becomes the default for its catalog.  Only one entry per catalog may set `default: true`. |

### Example

```yaml
# In a pack.yaml manifest
extensions:
  timeline:
    kinds:
      - catalog: transition
        id: cross-fade
        aliases: [crossfade, xfade, dissolve]
        default: true
      - catalog: transition
        id: fade
        aliases: [fade-out, fade-in]
      - catalog: clip
        id: video
        aliases: [visual, vid]
      - catalog: track
        id: caption
        aliases: [subtitle, subtitles]
```

This manifest declares:
- A `cross-fade` transition kind with three aliases (`crossfade`, `xfade`,
  `dissolve`) set as the default transition.
- A `fade` transition kind with two aliases.
- A `video` clip kind with two aliases.
- A `caption` track kind with two aliases.

### Validation

At pack load time, `astrid.core.pack._normalize_timeline_kinds()` validates:

- `catalog` must be one of `transition`, `clip`, or `track`.
- `id` must be a non-empty string.
- `aliases` (when present) must be a list of non-empty strings.
- `default` (when present) must be a boolean.
- No unknown fields are allowed.
- Duplicate ids or aliases (including cross-catalog conflicts) are caught
  with catalog-specific error messages.
- At most one entry per catalog may set `default: true`.

### Discovery

Agents do not need to parse `pack.yaml` directly.  The extended kinds are
loaded into the runtime `ElementKindRegistry` and are surfaced through the
same CLI error-recovery path described in the Recoverable CLI Choices section
above.  When an agent invokes a command with an invalid kind, the error
output will include both the built-in and extension kinds in the
`valid options:` line.

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
