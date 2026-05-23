# Milestone 3 — Secondary primitives (transitions / effects / themes / tracks / audio / pool / arrangement)

> **DRAFT** — flesh out before this milestone inits. Inherits the backend-agnostic API pattern from m1+m2.

## Outcome

Complete the non-clip timeline mutation surface. Transitions, effects, themes, tracks, audio bindings, pool metadata, and arrangement-level edits all become semantic events emitted through `EventLogBackend`. The CLI and Python APIs remain storage-agnostic: LocalFs is the concrete test backend, and Supabase remains a stub until m6.

By the end of this milestone, ordinary timeline construction should no longer need ad hoc direct writes for anything except compatibility projection that m4 removes.

## Scope (IN)

CLI verbs:

- `timelines transition set --between A,B --kind cross-fade --duration <t>`
- `timelines transition remove --between A,B`
- `timelines effect add --clip <id> --effect-id <id> [--params k=v ...]`
- `timelines effect remove --clip <id> --effect-id <id>`
- `timelines effect tune --clip <id> --effect-id <id> --param k=v`
- `timelines theme set --theme <id>`
- `timelines theme override --override-id <id> --value <v>`
- `timelines track add --kind {visual,audio,caption}`
- `timelines track remove --track-id <id>`
- `timelines audio bind --clip <id> --asset <id>`
- `timelines audio unbind --clip <id>`
- `timelines pool add --asset <id|path>`
- `timelines pool remove --asset-id <id>`
- `timelines pool score --asset-id <id> --score <0..1>`
- `timelines arrangement set --from-json <file>`
- `timelines arrangement show`

Event kinds added:

- `transition.set`
- `transition.removed`
- `effect.added`
- `effect.removed`
- `effect.tuned`
- `theme.set`
- `theme.overridden`
- `track.added`
- `track.removed`
- `audio.bound`
- `audio.unbound`
- `pool.asset_added`
- `pool.asset_removed`
- `pool.asset_scored`
- `arrangement.replaced`

Python API:

- Add functions beside the m2 clip APIs, grouped by domain if that matches current package style.
- Every mutation receives/resolves an `EventLogBackend` and appends one semantic event through `append_event(timeline_id, kind, payload, *, actor, expected_version=None, txn_id=None) -> TimelineEvent`.
- Each new event kind extends the canonical event schema package from m1 at `astrid/core/timeline/events/schema/`, preserving the same canonical serializer and schema-version bumping rules.
- Compatibility writes to `assembly.json` must be routed through the same narrow helper used in m2, so m4 can replace it with projection.

Pack migration:

- Continue the m2 audit and convert any pack code that mutates transition/effect/theme/track/audio/pool/arrangement fields.
- Prioritize builtin render/cut/hype paths whose outputs are likely to be consumed by Remotion or Reigh.
- Exhaustive pack and worker write-path closure is m3.5's job; m3 only migrates what is necessary to prove each secondary primitive.

## Anti-scope

- Clip primitive changes; m2 owns those. If a clip bug blocks m3, keep the fix narrowly tied to compatibility with m2's API rather than expanding the clip surface here.
- Backend-specific Supabase implementation.
- Projection purity and snapshot replay.
- CAS enforcement and soft locks.
- User-facing history/diff/audit commands.
- Exhaustive pack and worker write-path migration; m3.5 owns that sweep.

## Locked Decisions

- All secondary primitives use the same `EventLogBackend` protocol and actor handling as clip primitives.
- `arrangement.replaced` is the coarse-grained escape hatch for arrangement changes that cannot yet be represented as smaller semantic events. It must still be deterministic and replayable.
- Pool assets and tracks should use UUIDs when creating new ids; preserve existing ids only where schema compatibility requires it.
- `arrangement show` is read-side only and should read through the current compatibility projection until m4.
- Events stay semantic-batched, especially for effect tuning sliders and theme override editing.

## Open Questions

- Theme override namespace: what is the stable key shape in `astrid/timeline.py::ThemeOverrides`?
- Is `arrangement set --from-json` intentionally a full replacement, or should the planner introduce smaller arrangement events?
- Does pool scoring trigger downstream recompute or is it pure metadata?
- Are audio bindings represented as clip fields, separate audio tracks, or asset relationships in the current schema?
- Should transition identity be "between clip ids" or its own UUID entity?

## Constraints

- Do not duplicate backend selection logic; use the m1 selector.
- Do not let CLI parsing details leak into event payloads. Payloads should be API-level concepts, not raw argv.
- Keep compatibility projection output stable for existing rendering tests.
- Supabase paths must still fail explicitly via stub, not silently no-op.
- Keep event namespaced exactly as listed unless the plan documents a better compatible convention before implementation begins.

## Done Criteria

- All listed verbs exist or the plan explicitly narrows/renames them with rationale.
- Each mutation appends the expected event through `EventLogBackend`.
- LocalFs unit/integration tests cover every new event kind.
- Existing render/cut/hype output tests still pass.
- Converted pack code has no direct secondary-field `assembly.json` mutation except through the temporary compatibility helper.
- Supabase stub behavior remains covered.

## Touchpoints

**Likely new/modified files:**

- `astrid/core/timeline/edits.py` or domain modules such as `effect_edits.py`, `track_edits.py`, `pool_edits.py`.
- `astrid/core/timeline/eventlog/types.py` — event payload typing.
- Current `astrid timelines` CLI command module.
- `astrid/packs/builtin/cut/`
- `astrid/packs/builtin/render/`
- `astrid/packs/builtin/hype/`
- Timeline API/CLI tests following existing test layout.

**Reference reads:**

- `astrid/timeline.py`
- `examples/hype.timeline.json`
- `remotion/node_modules/@banodoco/timeline-schema/typescript/src/schemas.ts`
