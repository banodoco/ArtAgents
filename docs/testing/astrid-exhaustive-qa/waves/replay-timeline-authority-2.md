# Replay: corrected timeline authority (live agent UX)

Date: 2026-08-24

Mode: fresh black-box live usage. I used only the public Astrid skill, CLI,
CLI help, returned JSON envelopes, and returned durable artifacts. I did not
inspect product source, tests, or prior QA reports, and I did not modify
product code.

Disposable root:

`ASTRID_PROJECTS_ROOT=/tmp/astrid-live-timeline-authority-2.b0neXx/projects`

macOS resolved returned paths through `/private/tmp/...`.

## Verdict

PASS. Canonical timeline visualization is demonstrably pinned to the kernel
timeline's public `config_version` and event head. Format changes do not
change the source snapshot. A timeline save does change the source snapshot.
Archive/unarchive lifecycle changes advance the stream head without losing
document content. Frozen navigation from a returned, extensionless durable
manifest CAS path works. Identical visualization requests return the complete
prior artifact set rather than an empty replay shell.

No P0 or P1 failure was found in this replay.

## Journey and exact evidence

### 1. Fresh root and default v1

Created project `authority`, then default timeline `primary` with one valid
text clip and a real render-shaped output (`640x360`, 30 fps, `.mp4`). The
create/show envelopes agreed on:

- timeline UUID: `026f8407-5098-5dcb-a54c-dd0064a539f6`
- timeline ULID: `yfr03bvqhqf8d7vgsg2h3thtcn`
- `config_version: 1`
- authored text: `AUTHORITY V1`
- `is_default: true`

`timelines history primary` returned exactly one immutable
`timeline.created` entry at version 1 containing that document. `timelines
diff primary` returned an empty list, as expected for a one-version stream.

### 2. Same v1 source, two format inputs, then an identical replay

`timelines visualize --format png` (using the default) returned:

- kernel run: `292ba8e2004613ee58cb753670`
- manifest CAS path ending `f194bececbb85b74db6425b1c2430f28ec3e0a65d68c668c95069f050f972ffb`
- source run id in manifest: `WTTJDEB3YY1WWJMRSTCN1KYFHM`
- SNS: `SNS:ff8743df4077a9370ad2efde57d134f5423e482b1a9080fe6358960ba994f66f`
- event-head version: `1`
- event-head hash: `a8d99138f5edd0698e07a05f8cac1c1faf22586890eec93904febffb8767071d`

`timelines visualize primary --format md` returned a distinct format-specific
manifest ending
`0a35b11f58ee504b56a912a4bb3f60c33898e9c09f2a2c6f729c65abeab13c17`,
but the same source run id, SNS, event-head version, and event-head hash. This
is the desired separation: requested presentation changes while source
authority stays fixed.

Repeating the identical `--format md` request returned the same kernel run
`e398c094e6cbfd9b21a5023b49`, the same manifest CAS path, and the full
artifact array (manifest, indexes, diagnostics, ground truth, reading guide,
and `structure.md`). It did not return an empty artifact set.

The v1 ground-truth artifact contained one clip:

`TL01.CL01 / AUTHORITY V1 / end_frame 60`.

### 3. Save v2 and prove content + authority move together

Saved `primary` with `--expected-version 1`. The new document changed the
first title to `AUTHORITY V2`, added `EVENT HEAD ADVANCED`, and extended the
timeline from 2 to 3 seconds. Save/show both returned `config_version: 2`.

History became:

1. `timeline.created`, version 1
2. `timeline.saved`, version 2

Diff reported document keys `clips` and `output` changed, with no registry
change.

Both the v2 PNG and Markdown visualizations pinned:

- source run id: `SVC60DCB1V897FD7W39VQRWDQM` (different from v1)
- SNS: `SNS:b2a337aad49074aedcdfe11c4e13228e5a5bcbeb3a899edf1dcfc50566c4381d`
- event-head version: `2`
- event-head hash: `486e64813bdb2e93c58b991c6fb78dafd1272ee7bda62d223c593b31dd3d5201`
- authoritative warning event id: `529a7048258c488f862bd2f55aefd0b1`

The v2 ground truth contained exactly the current content:

- `TL01.CL01 / AUTHORITY V2 / end_frame 60`
- `TL01.CL02 / EVENT HEAD ADVANCED / end_frame 90`

Thus the public read model (`show`), immutable history, diff, SNS, event head,
and visualized evidence all advanced coherently.

### 4. Archive/unarchive lifecycle and version pin

Archive returned `config_version: 3`; active list became empty and inclusive
list retained `primary`. Attempting visualization while archived failed
explicitly with exit 1 and `validation_error: no kernel timeline with ref
'primary'`.

Unarchive returned `changed: true` and `config_version: 4`. `show` retained
the exact v2 document content while reporting version 4. History preserved all
four ordered lifecycle events:

1. created v1
2. saved v2
3. archived v3
4. unarchived v4

The next visualization manifest (CAS path ending
`961402eceabd30530073e50fb3f29a707475c54c0bec7b15ae02c13372ff01e5`)
pinned:

- source run id: `2XAAW6V942FJFGBHSNN191FSHM`
- SNS: `SNS:b7fe9a97ebadc0bc42ace48f8af63a41ed67e384398a28299aff52638b059895`
- event-head version: `4`
- event-head hash: `f03759dc711059a04c970a09eb8494d8e7bd4f976c4a6120d9ee083ec00c3f5d`
- authoritative warning event id: `fc0e5fcf00004ddbb5023cef88ec5998`

This is important: lifecycle changes advance the authority pin even though
the authored document remains the v2 document.

### 5. Frozen navigation from the returned CAS manifest

Used the returned extensionless managed manifest path directly:

`astrid timelines visualize --from-view <9614...CAS path> --focus TL01.CL01 --format md --json`

It succeeded and returned a new manifest CAS path ending
`4764add1f5369a06896142268a5945678b9e3c40dc0932aaebb50f41fc200044`.
That manifest reported:

- `inputs.from_view`: the exact returned CAS path
- `inputs.focus`: `TL01.CL01`
- `scope.kind`: `clip`
- `scope.ref`: `TL01.CL01`
- the same v4 SNS and event-head hash/version
- a complete Markdown evidence artifact set

This proves durable-manifest navigation is not dependent on a filename
extension or a transient run workspace.

### 6. Invalid canonical config fails explicitly

Created a separate non-default timeline `invalid` so the valid authority
journey stayed recoverable.

First invalid config omitted a required track label. Visualization exited 1
with an explicit schema failure naming `tracks[0]` and the required `label`.
After adding the label while intentionally keeping structured text without a
`clipType`, visualization again exited 1 with the precise failure:

`clips[0] contains structured text; set clipType to 'text'`

Neither request succeeded with empty content.

### 7. Managed-media authority path

Generated a local one-second 320x180 H.264/AAC maker fixture with no network,
credentials, or GPU requirement, then imported it via `media import --realm
managed_local`.

- media id: `c82d68ce-93b9-5177-9c01-6a45932f3382`
- content SHA-256: `ef86c7ee49b5531795b5238add4efb81c0083c27ddd43ae1792537ad58c9787c`
- managed locator: the corresponding
  `.astrid/media/sha256/ef/86/<hash>` CAS path

Created canonical timeline `managed` referencing that locator with the same
declared content hash, then visualized it successfully. Manifest CAS path:

`.../sha256/8b/2d/8b2d4669d93838f8a303b2a818da3b3bf83a5ad31000fd09718ea59f14e22ea5`

The evidence pack emitted filmstrip frames. Its `asset-index.json` reported:

- `integrity_state: verified_original`
- expected SHA-256 equals observed SHA-256
- canonical ref `TL01.AS01`
- event-head version `1` matching the timeline's public config version

This exercises the managed-media route without external services.

## Friction and lower-severity findings

### P2: schema-invalid documents are admitted, then rejected downstream

`timelines create/save` accepted the two invalid documents and advanced their
canonical versions; schema validation happened only when visualization ran.
The failure is explicit and safe for evidence generation, but an agent can
persist a canonical timeline that no renderer/visualizer can consume. Earlier
validation, or a clear `validated: false` state in create/save responses,
would reduce recovery work.

### P2: manifest `inputs.timeline_source` is provenance-ambiguous

For `primary` and `managed`, manifests reported
`inputs.timeline_source: ["authority"]`—the project slug—while the snapshot
correctly identified the actual timeline slug/UUID/ULID. A field named
`timeline_source` appearing to contain the project ref can mislead an agent
reading only the manifest inputs. Prefer the resolved timeline ref there, or
rename it to `project_source` and keep the authoritative timeline identity in
an adjacent explicit field.

### P2: pristine-root doctor conflicts with the advertised first-run order

Running `doctor --json` first on the brand-new root returned `ok: false`
because the projects root/database did not yet exist, although its messages
correctly explained that creation initializes the store. The public skill's
clean-machine flow starts with `doctor`, so an agent using fail-fast shell
semantics would stop before the instructed bootstrap command.

### P3: workspace selection escapes the disposable data root

`projects select authority` wrote its workspace preference at
`/Users/peteromalley/Documents/reigh-workspace/Astrid/.astrid/config.json`,
not beneath `ASTRID_PROJECTS_ROOT`. This is documented behavior, but it is an
easy isolation surprise in live QA. Subsequent commands in this replay used
the disposable root, and the selected ref was valid there.

## Agent UX assessment

The authority model is now legible from live use: `show` exposes the current
materialized document and public `config_version`; `history` exposes ordered
immutable lifecycle versions; `diff` compares adjacent documents; and
visualization consumes the canonical kernel selection and freezes both an SNS
digest and hash-chained event head. Files returned from visualization behave
as durable evidence/projections rather than a competing timeline authority.

The remaining friction is chiefly admission-time validation and provenance
naming, not silent divergence or stale-source behavior.
