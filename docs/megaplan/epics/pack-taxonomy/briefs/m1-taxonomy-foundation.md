# M1: Taxonomy Foundation

## Outcome

Add the first durable layer of the pack taxonomy without broad file moves:
metadata fields, grouped pack CLI output, user-facing docs, and the immediate
visibility cleanup for `text_review`.

## Scope

In:

- Add optional pack manifest fields for taxonomy metadata. Suggested fields:
  `origin`, `install_tier`, `pack_type`, `domain`, `stability`, `support`.
- Extend `PackDefinition` and pack JSON output to carry those fields with
  backward-compatible defaults.
- Update `astrid packs list`, `packs status`, and `packs inspect` so visible
  output groups packs by taxonomy. JSON output should include enough structured
  fields for agents/scripts to group without parsing text.
- Add or update docs explaining pack vs capability vs bundle/category.
- Fix `astrid/packs/text_review/pack.yaml` so it is hidden until M3 moves it.
- Regenerate the capability index if the visibility fix changes `_core` output.
- Add focused tests for metadata parsing and grouped list/status behavior.

Out:

- Do not physically move `builtin`, `external`, or `upload` capabilities.
- Do not implement aliases here unless it is a trivial schema-only preparatory
  change with no registry behavior.
- Do not delete or move demo packs beyond the `text_review` visibility fix.

## Locked Decisions

- Pack ids express purpose, not origin. Do not introduce `builtin_media` or
  similar names.
- Built-in/default/external-ness is represented by metadata.
- `hype` is a recipe/orchestrator name, not the domain taxonomy.
- Later reclassification should be cheap: changing default/optional/bundled
  status should be a manifest/config/docs change.

## Touchpoints

- `astrid/core/pack.py`
- `astrid/core/pack_machinery/schemas/v1/pack.json`
- `astrid/packs/cli.py`
- `astrid/packs/*/pack.yaml`
- `docs/creating-packs.md`
- `docs/discovery-for-agents.md`
- new or updated `docs/pack-taxonomy.md`
- `astrid/packs/_core/skill/SKILL.md` if regenerated
- tests covering pack parsing/list/status/inspect

## Done Criteria

- Existing packs validate.
- `astrid packs list` remains useful in plain text and has stable JSON output.
- `text_review.clip_extract` is no longer accidentally exposed as a visible
  product capability.
- Docs clearly explain pack/capability/bundle and the metadata distinction.
- Focused tests pass.
