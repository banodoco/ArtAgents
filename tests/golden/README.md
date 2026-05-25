# Golden Fixtures — Timeline Projection (m4)

This directory contains backend-neutral fixture files for the
`project_to_assembly()` projector. Runtime fixtures must project to raw
`TimelineConfig` only: top-level `clips` and `tracks`, with no
`{schema_version, assembly}` wrapper and no `pool` or `arrangement` read-model
keys. Legacy wrapper/no-label/arrangement cases are kept only as explicit
runtime-rejection fixtures or in migration tests.

Each fixture is a single JSON file with:

- **`events`** — an ordered list of `TimelineEvent` dicts.
- **`expected_assembly`** — the expected raw `TimelineConfig` dict for runtime
  fixtures. Rejection fixtures may carry historical read-model shapes only to
  prove runtime projection rejects them.

## Coverage

| Fixture | Event families covered |
|---|---|
| `fixture_clip.json` | `clip.added`, `clip.removed`, `clip.moved`, `clip.retimed`, `clip.swapped`, `clip.replaced`, `clip.text_set`, `clip.annotated` |
| `fixture_transition.json` | `transition.set`, `transition.removed` |
| `fixture_effect.json` | `effect.added`, `effect.removed`, `effect.tuned` |
| `fixture_theme.json` | `theme.set`, `theme.overridden` |
| `fixture_track.json` | `track.added`, `track.removed` |
| `fixture_audio.json` | `audio.bound`, `audio.unbound` |
| `fixture_pool.json` | `pool.asset_added`, `pool.asset_removed`, `pool.asset_scored` |
| `fixture_arrangement.json` | `arrangement.replaced` |
| `fixture_bootstrap_created.json` | Fresh created timeline — bare first domain event, lifecycle no-ops |
| `fixture_bootstrap_legacy.json` | Historical legacy timeline — rejected by runtime projection |

## Bootstrap variants

1. **Created** (`fixture_bootstrap_created.json`): A fresh `timeline.created`
   followed by a bare `clip.added`. The projector treats lifecycle events as
   no-ops. No `timeline.imported` is present.

2. **Legacy** (`fixture_bootstrap_legacy.json`): A historical
   `timeline.imported` event with a snapshot containing the full
   `assembly.json` wrapper shape (`{schema_version: 1, assembly: {...}}`).
   Runtime projection rejects this fixture; Sprint 2 migration code owns
   loose decoding and conversion.

## Usage in tests

Consumers should:

1. Load a fixture JSON file.
2. Parse the `events` list into `TimelineEvent` objects via
   `TimelineEvent.from_dict()`.
3. For runtime fixtures, call `project_to_assembly(events)`, assert the result
   equals `expected_assembly`, and validate it as raw `TimelineConfig`.
4. For explicit rejection fixtures, assert `project_to_assembly(events)` raises
   rather than converting legacy read-model shapes.
5. Assert that `project_to_assembly(events[:k])` for any runtime prefix `k`
   produces intermediate state consistent with stepwise replay.

Cross-backend parity tests (m6, m8) consume these same fixtures unchanged.

## Benchmark targets

These targets are verified by the projection benchmark suite (`T9` / `T10`):

- **Full replay of 1000 events**: ≤ 500 ms
- **Checkpoint replay of 50-event tail on 1000-event stream**: ≤ 100 ms

Benchmarks measure wall-clock time for `project_to_assembly()` on a
representative 1000-event stream (mix of all event kinds), running on a
standard CI worker. The 50-event tail benchmark seeds the projector with a
pre-built checkpoint assembly and replays only the suffix.
