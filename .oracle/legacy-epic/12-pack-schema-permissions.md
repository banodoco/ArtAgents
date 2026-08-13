# Explore: pack schema, permissions, and pack.yaml extension shape

Project root: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only exploration. Do NOT edit files.

## What to establish

1. `astrid/packs/rendering/pack.yaml`: quote it fully. What content roots,
   aliases, permissions (network? subprocess?) does the rendering pack
   declare today, and what do they apply to (the epic notes pack-wide network
   permission for unrelated rendering features)?
2. `astrid/packs/rendering/executors/render/executor.yaml`: quote the inputs
   (timeline, assets_registry, theme, engine, out, keep_previous_renders?)
   with their types and the engine flag constraints.
3. The pack schema (`astrid/core/pack/schemas/v1/pack.json`): top-level keys
   allowed (id, version, name, description, content roots, permissions,
   aliases, extensions?). Is there an existing `extensions:` mechanism in ANY
   pack today (grep `extensions:` in astrid/packs/*/pack.yaml)? If yes, how
   is it validated and loaded — this is the model for an
   `extensions.rendering` section.
4. How `pack.yaml` is discovered per pack kind: `discover_pack_metadata` and
   the manifest loader (`load_manifest_mapping`) — which file lists known
   manifest filenames per capability kind, and how a new `renderer.yaml`
   manifest kind would be added to that mapping.
5. Where the executor manifest itself is discovered (executor.yaml → how it
   becomes a CapabilityRegistry entry with `rendering.render` as qualified
   id).

## Report format

Ranked findings with file:line evidence. Max 350 words. End with:
- Verified facts (quote pack.yaml/executor.yaml key fields)
- Unknowns
- Risks for adding `extensions.rendering` without breaking existing packs
- Suggested approach
