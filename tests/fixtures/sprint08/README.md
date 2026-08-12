# Retired Sprint-08 fixture staging notes

This directory was reserved for JSON snapshots of the sprint-08 timeline-fixture helpers
from reigh-app: `createAgentWorkflowTimelineFixture` and
`createEmbedDemoTimelineFixture` (originally exported from
`reigh-app/src/tools/video-editor/testing.ts`).

It is no longer the renderer parity gate. The blocking, repository-owned
semantic fixtures live in `tests/fixtures/renderer_parity/` and are exercised
by `tests/packs/test_renderer_parity.py` without an environment opt-in.

For historical reference, the old population recipe was:

1. Run `npx tsx ../reigh-app/src/tools/video-editor/testing.ts` (or wire up the
   helper export of your choice) and write the resulting timeline JSON as
   `tests/fixtures/sprint08/<name>.json`.
2. Render that JSON via `npm --prefix remotion run smoke` (or a dedicated
   headless render) to produce the golden artifact.
3. Commit `tests/fixtures/sprint08/golden/<name>.sha256` with the hex digest.

`scripts/node/export_fixtures.mjs --json` enumerates the current state of this
directory and reports which goldens are present.
