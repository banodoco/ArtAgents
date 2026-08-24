# Live UX replay: serve/editor bridge 2

Date: 2026-08-23

## Scope

Fresh live run only, with no programmatic tests or source inspection. Used an
isolated `ASTRID_PROJECTS_ROOT=/tmp/astrid-live-ZcYK0b/projects`, unused
`127.0.0.1:18743`, and a copied PNG fixture.

## Evidence

- Created `editor-demo`, imported `tiny.png` (18,945 bytes), and created the
  default `primary` timeline through the CLI.
- While `astrid serve --host 127.0.0.1 --port 18743 --no-open-editor` owned the
  store, `projects --help`, `timelines save --help`, and `media --help` all
  printed successfully. This demonstrates help paths do not contend with the
  exclusively-owned database.
- Serve readiness output explicitly reported the bridge URL, projects root,
  exclusive database ownership, HTTP discovery at `GET /routes`, the save JSON
  shape, and registry-key asset semantics.
- `GET /` returned a clear 404 unknown-route response; `GET /health` returned
  200 with the isolated root; `GET /routes` returned 200 and documented root,
  ownership, canonical read/save routes, save payload and response version,
  and `GET|HEAD .../assets/{registry_key}` with single-range support.
- Used documented routes successfully: `GET /projects`, timeline list/read,
  `POST .../save` from version 1 to 2 with a registry asset key `hero`, and a
  subsequent read confirming the saved config and registry.
- Deliberate stale save with `expected_version: 1` returned HTTP 409
  `timeline_version_conflict`, stated no write occurred, reported current
  version 2, and gave merge/retry recovery guidance.
- Fetched the registered asset by registry key (not media ID): full GET returned
  200 with `Accept-Ranges: bytes`, and `Range: bytes=0-15` returned 206 with
  `Content-Range: bytes 0-15/18945`.
- Shut down the bridge cleanly. Post-shutdown CLI timeline read preserved
  `config_version: 2`, the saved config, and `registry.assets.hero`; media list
  preserved the imported media. `doctor --json` returned `ok: true`, quick
  check OK, no foreign-key violations, and all schema versions OK.

## Verdict

PASS. The live serve/editor bridge is discoverable, clearly communicates
exclusive ownership and canonical HTTP usage, supports read/save/stale-recovery
and registry-key asset retrieval, and hands state back to the CLI intact after
shutdown. The incompatible/migration-root help probe was not attempted because
the required live ownership proof was already complete and no safe need arose
to mutate or manufacture an incompatible store.
