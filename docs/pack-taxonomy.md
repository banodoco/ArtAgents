# Pack Taxonomy

Every Astrid pack carries six first-class taxonomy fields that classify what it
is, where it comes from, how it is shipped, and how stable it is. These fields
are defined in the pack manifest (`pack.yaml`) and exposed through every
discovery surface: `packs list`, `packs status`, and `packs inspect`.

## Why Taxonomy?

Before M1, packs were discovered as a flat list. Agents had no structured way
to answer "is this pack core or optional?", "is it stable enough to use in
production?", or "what domain does it belong to?" without reading free-text
descriptions. The taxonomy layer makes these answers machine-readable.

## The Six Fields

| Field | Purpose | Default | Example values |
|---|---|---|---|
| `origin` | Where the pack came from | `"unknown"` | `builtin`, `project`, `external`, `community` |
| `install_tier` | How the pack is installed | `"default"` | `core`, `default`, `optional`, `bundled` |
| `pack_type` | What kind of package this is | `"capability"` | `capability`, `bundle`, `adapter`, `product_surface` |
| `domain` | What problem area the pack serves | `"general"` | `system`, `media`, `integration`, `development`, `infrastructure` |
| `stability` | How stable the pack API is | derived from `status` | `stable`, `beta`, `experimental`, `deprecated` |
| `support` | Who supports this pack | `"project"` | `core`, `project`, `community`, `none` |

### `origin`

Describes the provenance of the pack. Ship with `builtin` for packs that are
part of the Astrid distribution. Use `project` for packs scaffolded inside a
user's project. External packs installed from Git or a registry should declare
`external`.

**This is metadata, not identity.** The pack id (e.g., `builtin`, `external`)
expresses the pack's *purpose* — what it does. The `origin` field tells you
*where it came from*. A pack with id `external` and origin `builtin` means
"the external-tools pack ships with Astrid."

### `install_tier`

Controls whether the pack is installed by default or must be opted into.

- `core` — Always present. Cannot be uninstalled. (Currently: `builtin`,
  `external`, `iteration`, `media`, `upload`.)
- `default` — Installed by default but can be removed. Most scaffolded packs.
- `optional` — Must be explicitly installed.
- `bundled` — Shipped with the distribution but selectively enabled.

### `pack_type`

Describes the pack's structural role:

- `capability` — A standard pack containing executors, orchestrators, and/or
  elements. This is the default for scaffolded packs.
- `bundle` — A meta-pack that groups other packs under a single install surface.
  Bundles do not contain their own capabilities; they declare dependencies.
- `adapter` — A pack whose primary purpose is connecting Astrid to an external
  service or tool (e.g., `external`).
- `product_surface` — A pack that exposes a complete product-level feature
  (e.g., the built-in render pipeline).

### `domain`

The functional area the pack operates in. This is the primary grouping axis in
CLI output and the most important field for agents to filter on.

Current shipped domains:

| Domain | Packs |
|---|---|
| `media` | `rendering`, `understanding`, `generation`, `editorial`, `video_editing`, `foley` — media creation and editing |
| `integration` | `reigh`, `youtube`, `fal`, `vibecomfy`, `moirae` — connections to external services |
| `development` | `iteration`, `training` — author-test-iterate tooling and model training |
| `infrastructure` | `runpod` — GPU provisioning and execution |
| `system` | `builtin` (shell, hidden), `external` (shell, hidden), `upload` (shell, hidden) — legacy namespace shells |
| `general` | scaffolded packs, local scratch pack |

**`hype` is not a domain.** The `video_editing.hype` orchestrator lives inside the
`video_editing` pack (domain `media`). An orchestrator id like `video_editing.hype`
identifies a *capability*, not a pack taxonomy category. If you find yourself
wanting a `hype` domain, stop — what you really want is a capability filter
(`executors search hype` or `orchestrators search hype`). The legacy id
`builtin.hype` is preserved as a deprecated pack-level alias.

### `stability`

Indicates the API stability of the pack. This defaults from the pack's `status`
field using a deterministic mapping:

| `status` | `stability` default |
|---|---|
| `active` | `stable` |
| `stub` | `stable` |
| `experimental` | `experimental` |
| `deprecated` | `deprecated` |

If the manifest explicitly sets `stability`, that value is used regardless of
`status`. This allows a pack to be `status: active` while still declaring
`stability: beta` during a transitional period.

### `support`

Who is responsible for maintaining the pack:

- `core` — Maintained by the Astrid project. Covered by the same compatibility
  guarantees as the core runtime.
- `project` — Maintained by the project that scaffolded it. No upstream
  guarantee.
- `community` — Community-maintained. Best-effort support.
- `none` — Explicitly unsupported. Use at your own risk.

## Pack, Capability, Bundle, Category — Clearing Up the Vocabulary

These terms are easy to confuse. Here is the definitive distinction:

**Pack** — A directory with a `pack.yaml` manifest. Contains capabilities
(executors, orchestrators, elements). The pack is the *container*.

**Capability** — Something a pack can *do*. An executor, orchestrator, or
element. Identified by a qualified id like `video_editing.hype` or
`media.clip_extract`. The legacy id `builtin.hype` is preserved as a
deprecated alias.

**Bundle** — A pack whose `pack_type` is `bundle`. Bundles group other packs
but do not contain their own executors or orchestrators. Installing a bundle
installs all its member packs.

**Category** — Free-form text in `metadata.category`. Not a taxonomy axis.
The `--category` CLI flag filters on `metadata.category` only. If you want
structured filtering, use the taxonomy flags (`--domain`, `--origin`, etc.).

**Metadata** — Arbitrary key-value data in `pack.metadata`. Taxonomy fields
live at the top level of the manifest, not inside `metadata`. This keeps the
taxonomy contract explicit and validated.

## How Taxonomy Appears in CLI Output

### JSON Output

Every pack payload includes both top-level taxonomy fields and a nested
`taxonomy` object:

```json
{
  "id": "builtin",
  "domain": "system",
  "origin": "builtin",
  "install_tier": "core",
  "pack_type": "capability",
  "stability": "stable",
  "support": "core",
  "taxonomy": {
    "origin": "builtin",
    "install_tier": "core",
    "pack_type": "capability",
    "domain": "system",
    "stability": "stable",
    "support": "core"
  }
}
```

The flat `packs` array in `packs list --json` and `packs status --json` is
preserved for backward compatibility. A new top-level `groups` key provides
domain-grouped views:

```json
{
  "packs": [{ "id": "builtin", "domain": "system", ... }, ...],
  "groups": [
    {
      "group_by": "domain",
      "value": "system",
      "taxonomy": { "domain": "system" },
      "packs": [{ "id": "builtin", ... }]
    }
  ]
}
```

### Plain-Text Output

Plain-text `packs list` and `packs status` group output by domain:

```
taxonomy: domain=development
iteration       Astrid Iteration        1.0.0   origin=builtin  tier=core       type=capability  stability=stable       support=core

taxonomy: domain=system
builtin Astrid Built-in        1.0.0   origin=builtin  tier=core       type=capability  stability=stable       support=core
```

`packs inspect` adds a dedicated taxonomy block:

```
id: builtin
name: Astrid Built-in
...
taxonomy:
  origin: builtin
  install_tier: core
  pack_type: capability
  domain: system
  stability: stable
  support: core
```

## Filtering with Taxonomy

All six taxonomy fields have corresponding CLI flags:

```bash
# Filter by domain (most common)
python3 -m astrid packs list --domain system
python3 -m astrid packs status --domain media

# Filter by origin
python3 -m astrid packs list --origin builtin

# Filter by install tier
python3 -m astrid packs list --install-tier core

# Filter by pack type
python3 -m astrid packs list --pack-type capability

# Filter by stability
python3 -m astrid packs list --stability stable

# Filter by support level
python3 -m astrid packs list --support core
```

Multiple filters can be combined. The `--category` flag remains separate and
filters on `metadata.category` only — it is not a taxonomy filter.

```bash
# These are different filters with different semantics:
python3 -m astrid packs list --domain system      # taxonomy.domain
python3 -m astrid packs list --category system     # metadata.category
```

## Visibility and Hidden Packs

The `visibility` field is not a taxonomy axis — it controls whether a pack
appears in default discovery. Packs with `visibility: hidden` are excluded
from `packs list` and `packs status` unless `--show-hidden` is passed.

```bash
# Default discovery excludes hidden packs
python3 -m astrid packs list

# Include hidden packs
python3 -m astrid packs list --show-hidden

# Status respects visibility too
python3 -m astrid packs status --show-hidden

# Inspect always works for any pack (hidden or visible)
python3 -m astrid packs inspect upload
```

### Example Packs vs. Runtime Packs

Not every pack directory in the repository is a runtime-discovered pack:

- **`astrid/packs/`** — Runtime packs. Discovered by `packs list`, `packs status`,
  and capability searches. Currently: `rendering`, `understanding`, `generation`,
  `editorial`, `video_editing`, `foley`, `training`, `reigh`, `youtube`, `fal`,
  `vibecomfy`, `runpod`, `moirae`, `iteration`, `media`, plus the
  dynamically-created `local` scratch pack. The legacy `builtin`, `external`,
  and `upload` packs are hidden shells that preserve backward compatibility
  through pack-level aliases.

- **`examples/packs/`** — Teaching packs. These are committed reference examples
  that demonstrate pack authoring patterns (multi-step pipelines, agent-attested
  workflows, element components). They are **not** runtime-discovered — you will
  not see them in `packs list` output even with `--show-hidden`. Validate them
  with `packs validate`:

  ```bash
  python3 -m astrid packs validate examples/packs/minimal
  python3 -m astrid packs validate examples/packs/file_summarizer
  ```

  The example packs are: `minimal` (canonical external-pack contract),
  `media` (pack with elements and schemas), `file_summarizer` (multi-step text
  pipeline), `text_digest` (agent-in-the-loop text pipelines), and `text_review`
  (machine summary + agent verdict workflow).

### Canonical Clip Extraction

The canonical product clip extraction executor is `media.clip_extract`. It
lives in `astrid/packs/media/executors/clip_extract/` and appears in runtime
discovery as `media.clip_extract`:

```bash
python3 -m astrid executors search clip_extract
```

The former scaffold-only packs `clip_tools` and `video_tools` (which contained
duplicate `clip_extract` scaffolding) have been removed. The example packs in
`examples/packs/` no longer carry `clip_extract` executor artifacts — they
demonstrate text-processing workflows, not media extraction.

## Defaults for Unspecified Fields

When a manifest omits taxonomy fields, deterministic defaults apply:

| Field | Default | Notes |
|---|---|---|
| `origin` | `"unknown"` | Explicitly declare for shipped packs |
| `install_tier` | `"default"` | Override to `core` for non-removable packs |
| `pack_type` | `"capability"` | Most packs are capabilities |
| `domain` | `"general"` | Always override for shipped packs |
| `stability` | `"stable"` | Derived from `status` if present |
| `support` | `"project"` | Override to `core` for maintained packs |

These defaults ensure backward compatibility: existing manifests that do not
declare taxonomy fields continue to work, and newly scaffolded packs start
with sensible values that authors can override.

## Scaffolded Pack Template

Running `packs new` creates a manifest with explicit taxonomy fields:

```yaml
schema_version: 1
id: my_pack
name: My Pack
version: 0.1.0
description: A pack for My Pack.
origin: project
install_tier: default
pack_type: capability
domain: general
stability: stable
support: project
```

This gives pack authors immediate visibility into the taxonomy vocabulary and
reminds them to set appropriate values before shipping.
