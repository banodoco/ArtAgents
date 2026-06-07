# M2: Alias Compatibility Layer

## Outcome

Make compatibility aliases real before any physical pack migration. Old ids
such as `builtin.render`, `external.vibecomfy.run`, and `upload.youtube` should
be able to resolve to future canonical ids through manifest-declared aliases.

## Scope

In:

- Add `aliases` support to pack manifests and schemas.
- Load aliases from discovered pack manifests into executor and orchestrator
  registries.
- Preserve and expose alias metadata such as `deprecated` and
  `deprecation_message` in inspect output where appropriate.
- Add tests proving old ids can resolve to new ids once aliases are declared.
- Add tests for child executor/orchestrator references resolving through
  aliases.
- Document the deprecation strategy for `builtin.*`, `external.*`, and
  `upload.*`.

Out:

- Do not physically move capabilities.
- Do not delete `builtin` or `external`.
- Do not introduce shim pack folders unless the alias resolver is proven
  insufficient.
- Do not solve element aliasing unless it is required for M4; record the chosen
  design if elements need different kind-aware handling.

## Locked Decisions

- Aliases live with the new canonical pack, not in old shim packs, where
  possible.
- Old ids remain functional during migration.
- Deprecation warnings should be clear but should not break existing plans.

## Initial Alias Targets

The migration sprint may refine exact placement, but tests should be able to
exercise representative aliases such as:

- `builtin.render -> rendering.render`
- `builtin.transcribe -> media.transcribe` or `understanding.transcribe`
- `builtin.hype -> video_editing.hype`
- `builtin.foley_map -> foley.foley_map`
- `builtin.publish -> reigh.publish`
- `builtin.youtube_audio -> youtube.youtube_audio`
- `external.fal_foley -> fal.fal_foley`
- `external.vibecomfy.run -> vibecomfy.run`
- `external.vibecomfy.validate -> vibecomfy.validate`
- `external.moirae -> moirae.moirae`
- `upload.youtube -> youtube.upload`

Do not overfit the final move map in this sprint; prove the compatibility
machinery.

## Touchpoints

- `astrid/core/alias_resolver.py`
- executor/orchestrator registries
- `astrid/core/pack_machinery/schemas/v1/pack.json`
- `astrid/packs/validate.py`
- `astrid/packs/cli.py`
- docs for aliases/deprecation
- tests for alias resolver, registry loading, CLI inspect/list

## Done Criteria

- Manifest-declared aliases validate and load.
- Registry lookup by an old id returns the canonical capability.
- Inspect/search output makes aliases discoverable enough for users and agents.
- Tests cover aliases through direct lookup and child dependency validation.
