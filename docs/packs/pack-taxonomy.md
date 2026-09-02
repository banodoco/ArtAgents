# Pack Taxonomy (strict v2)

Taxonomy is pack metadata in the canonical `pack.yaml`; it is not a second
identity or database registry. The catalog normalizes these fields and exposes
them through `packs list`, `packs status`, `packs inspect`, and SDK discovery.

## Fields

| Field | Meaning | Values |
|---|---|---|
| `id` | Stable owning namespace | lowercase identifier |
| `domain` | Functional area | `general`, `development`, `editorial`, `generation`, `infrastructure`, `integration`, `media`, `system` |
| `status` | Lifecycle state | `active`, `experimental`, `deprecated` |
| `visibility` | Whether normal discovery shows it | `visible`, `hidden` |
| `stability` | API maturity | `stable`, `experimental`, `deprecated` |
| `support` | Maintenance boundary | `project`, `core`, `community` |

`schema_version: 2`, `name`, and semantic `version` are required identity
fields. Optional metadata such as `description`, `keywords`, `permissions`,
`agent`, and `secrets` remains in the same manifest. Unknown top-level fields
are rejected by the v2 schema.

`id` is identity; `domain` is grouping. `status` and `stability` describe
lifecycle and API maturity independently. `visibility` controls discovery, not
trust. Permissions disclose expected network, filesystem, subprocess,
accelerator, or service access; they are not a sandbox.

## Current bundled catalog

The bundled catalog contains these 22 product packs:

```text
blender       comfy_wrap    editorial     fal
foley         generation    iteration     media
moirae        references    reigh         rendering
runaway       runpod        shots         stream_content
timeline      training      understanding vibecomfy
video_editing youtube
```

Each has exactly `astrid/packs/<id>/pack.yaml` and
`astrid/packs/<id>/skill/SKILL.md`. `_core/skill/SKILL.md` is code-owned kernel
guidance, not a product pack and not an unloadable catalog entry. Its generated
census is the routing view for these 22 owners.

## Contribution and database axes

Taxonomy does not determine what a pack contributes. Inspect the canonical
entry for its typed projections:

- capability/content roots for executors, orchestrators, and elements;
- rendering extension manifests;
- structured documentation and required context;
- pack-relative standalone runtime resources;
- optional bundled-only `database` ownership and migration head.

The default database composition is derived from entries with
`database.default_enabled: true`: core, timeline, shots, and references.
Runaway declares a real database contribution with `default_enabled: false` and
is explicitly composable through the same catalog projection. No fixed tuple,
independent parser, or second schema-pack identity exists.

## Inspecting taxonomy

```bash
python3 -m astrid.core.pack.cli list
python3 -m astrid.core.pack.cli list --domain media
python3 -m astrid.core.pack.cli inspect references
python3 -m astrid.core.pack.cli inspect references --json
python3 -m astrid.core.pack.cli validate /path/to/pack
```

Use the owning pack skill for agent instructions. Do not infer taxonomy from
folder names, capability prefixes, legacy aliases, or alternate manifest
filenames. `pack.yml`, `pack.json`, and `schema-pack.yaml` are invalid.
