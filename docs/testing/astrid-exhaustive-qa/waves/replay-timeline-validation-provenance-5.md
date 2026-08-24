# Timeline validation + provenance polish replay 5

Date: 2026-08-24 (Europe/Berlin)  
Surface: fresh public `python3 -m astrid` CLI/help only; no source, test, or
product edits.

## Verdict

PASS, 9.7/10. No P0/P1 issues. Validation admission is concise and typed,
opaque nested element parameters remain opaque, registered text-card content
renders successfully, and visualization manifests carry durable project and
timeline identity while supporting `from_view` navigation.

## Fresh fixture

- projects root: `/tmp/astrid-timeline-validation-kRfgNF`
- project: `polish` (`ce863c90-ef5e-52a7-84cb-e722a7ae8207`)
- timeline: `main`
  - UUID: `e12248ce-1692-5778-9cd9-afbbbb0321a6`
  - ULID: `0j5r4y21x02wr7hz8b0859g1j5`
  - stable visualization ref: `TL01`

The root was fresh: `doctor --json` returned exit 0 with explicit
`uninitialized` statuses before bootstrap. A one-second `text-card` timeline
was created and then exercised through canonical save/render/visualize.

## Admission validation

### Unknown clip type

The canonical document was saved with `clipType: "mystery-card"` to exercise
the render boundary. `timelines render main --json` failed before admission:

- exit 1, `validation_error`;
- path: `$.clips[0].clipType`;
- reason: unregistered reusable visual element `mystery-card`;
- recovery listed built-ins and the available installed effect IDs;
- `kernel_attempt_id`, `kernel_run_id`, `kernel_task_id`, and `run_id` were all
  null;
- `runs list --project polish` remained `[]`.

The error was short enough to act on and did not dump the full document.

### Invalid effects-shaped list

The document was then saved with an object-shaped effects entry containing
unexpected `bogus`/`params` properties and opaque nested data. Render failed
pre-admission with:

- exit 1, `validation_error`;
- path: `$.clips[0].effects[0]`;
- concise `additionalProperties` reason naming the unexpected fields;
- recovery explaining that `clip.effects` is for fade timing and reusable
  elements belong in `clipType` + `params`;
- all kernel/run/task IDs null and no run created.

The failure did not include a large serialized config dump.

### Opaque nested params

A registered `text-card` was saved with nested arbitrary parameters:

```json
{"opaque":{"deep":[{"provider":"custom","payload":{"any":[1,true,"x"]}}],"nested":{"x":{"y":null}}}}
```

The save succeeded without recursive schema rejection, and canonical render
succeeded on the first attempt. Managed output:

- media id `01m0sq477k6t9d5396vbczsm0m`;
- `opaque.mp4`, 52,690 bytes;
- MP4, 1920x1080, H.264 video + AAC audio, 1.045333 seconds;
- provenance media id `01m0sq477sjeqpffe9ah2dv21n`;
- provenance recorded kernel authority, config version 6, canonical timeline
  UUID/slug/ULID, project UUID/slug, and registry hash.

This proves registered text-card rendering remains compatible with opaque
nested element parameters.

## Visualization provenance

Project-scoped visualization succeeded with `--timeline-slug main --format md`.
Manifest:

`/private/tmp/astrid-timeline-validation-kRfgNF/.astrid/media/sha256/e7/cd/e7cd77f33b11e9db3afe26f04c6b64a3eb4fa7212aeedf0a92380f226278c5aa`

Its `inputs` retained the compatibility input and resolved identity:

- `source_mode: "project"`;
- `timeline_source: ["polish"]`;
- `resolved_project.id` = `ce863c90-ef5e-52a7-84cb-e722a7ae8207`;
- `resolved_project.slug` = `polish`;
- `resolved_timelines[0]` carried `TL01`, `main`, the UUID, and the ULID;
- snapshot version 6 and event-head hash were present.

## Durable `from_view` navigation

The same manifest was passed back with:

```text
--from-view <manifest> --focus TL01.CL01 --format md
```

The second visualization succeeded and produced manifest
`.../sha256/b6/3e/b63ee3bf1d329ff0fc171bb95ea6cadbdee8b186ee5c0ccecacb56d941535318`.
Its inputs retained the exact prior manifest path, `focus: TL01.CL01`,
`scope: clip`, the same resolved project identity, and the same exact timeline
identity. This is durable navigation through a managed manifest, not a
process-local reference.

## Friction / wrong turns

- Timeline save accepts a document containing an unknown clip type; the
  canonical render boundary is where the actionable validation appears. This
  is internally safe and produced no run, but earlier feedback at save time
  could reduce a wrong turn.
- Visualization's top-level manifest stores most identity under `inputs` and
  `snapshots`, rather than duplicating fields at the root. The structure is
  inspectable but requires one extra `jq` descent.
- `from_view` requires a focus as documented; the paired requirement is clear
  in help and the successful replay was straightforward.

No product changes were made because the advertised live behavior passed.
