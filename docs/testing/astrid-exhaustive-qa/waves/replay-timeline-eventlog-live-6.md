# Replay: live timeline event-log authority journey (wave 6)

## Scope and method

Fresh black-box LIVE journey on 2026-08-24 using only the public CLI gateway
against disposable roots. The source checkout had one pre-existing dirty test
file (`tests/v10/test_m7_dogfood.py`), which was left untouched. No pytest was
used as primary evidence.

Primary root: `/private/tmp/astrid-live-timeline.qfRln0`.
Backup: `/private/tmp/astrid-live-backup.RkZgsb`.
Restored root: `/private/tmp/astrid-live-restore.Pd9XE4`.

## Public journey and evidence

The following public commands were exercised:

- `doctor --json`, `projects create/show/list`, and `timelines create/show`.
- `timelines save` version 1→2→3→4→5, where the document added clips,
  removed `title`, moved `second`, and added `third`/`fourth`/`fifth`.
- A stale CAS save (`--expected-version 1` while current was 2) failed with
  `stale_version`, returned no receipt, and did not advance history.
- `media import`, `timelines shots create/add/show/reorder/remove`; the shot
  stream recorded `shot.created`, two `shot.item_added`, `shot.reordered`, and
  `shot.item_removed`.
- `timelines visualize primary --format all --layout both --filmstrip off`
  succeeded as run `76288d4fe70a589f6bd184caa5`, producing a 15-artifact,
  hash-addressed evidence pack.
- `timelines render primary --expected-version 5` succeeded as run
  `c20d16dc3d61377fd8207c35c6`; `runs show --evidence` reported one succeeded
  child and `hype.mp4` (513,719 bytes) plus its provenance sidecar.
- `timelines archive`, inclusive `timelines list`, `timelines show`,
  `timelines unarchive`, repeated `unarchive`, and final `list`. Archive and
  unarchive advanced the timeline stream to versions 6 and 7; repeated
  unarchive returned `changed:false` without another event.
- `backup create` and `backup restore` into the restored root, followed by
  `doctor`, project/timeline list/show, and timeline history.

The timeline history after restore contained the expected seven versions:
`timeline.created`, four `timeline.saved`, `timeline.archived`, and
`timeline.unarchived`. The final config was identical to version 5, with
`config_version: 7` reflecting lifecycle events.

## Authority and replay checks

Read-only SQLite inspection was performed only after the public actions. The
timeline aggregate row was keyed by the timeline stream id
`852a40d2-8a62-558a-9062-f5464cac1c81:timeline.timeline`; it was not edited.

- Source and restored roots both had `head_seq=7`, the same terminal event id
  `f8269be7f2874756ace1a52ed275f176`, and head hash
  `12acc62d4204bd76939b4ed263870bd929542466cf6c8488ff7391d0bf429d42`.
- Recomputed event hashes and `previous_event_hash` links passed for all seven
  timeline events and all five shot events in the source root.
- The materialized timeline document SHA-256 was
  `4624319a101136c3b5ee0fac6307cc7924db8aa893420dfbcabe9d1d9838b903` in
  both roots.
- Render snapshot `authority.json` pinned `authority: kernel`, the exact
  timeline version, event id, event hash, config hash, and registry hash. The
  version-5 render run input carried the same version-5 event id/hash as the
  corresponding snapshot.
- `astrid.read_events("journey", run_id, projects_root=..., verify=True)`
  fell back to `source="kernel"` for the successful render and visualization
  runs because there was no filesystem run projection; verification succeeded.
- Both roots returned `doctor state=ready`, SQLite quick-check `ok`, no foreign
  key violations, and schema versions `core=1, references=1, shots=2,
  timeline=1`.

These observations show timeline changes route through the canonical kernel
event stream and are projected into the read model. The shot mount has its own
canonical shot stream and projection; it does not mutate the timeline stream
or media identity. No direct filesystem timeline authority was observed.

## UX/environment friction

On the checkout's default interpreter, visualize and render failed closed
before useful execution because `banodoco_timeline_schema` was not installed.
Installing the sibling vendored schema into a disposable venv and running the
public CLI from that venv made visualization succeed. Remotion required the
venv's `bin` directory on `PATH` because its backend manifest invokes
`python3`; with that setup, the render succeeded. This is setup friction, not
an event-log or authority defect, and no product code was changed.

## Verdict and design recommendation

**PASS — canonical event-log authority is preserved.** Timeline create/save/
archive/unarchive and shot add/remove/reorder all append hash-chained events;
CAS protects whole-document saves; read models, visualization, rendering,
restart/reopen, and portable backup/restore agree on the same kernel head.

Keep the current design: whole-document timeline CAS for authored timeline
content, a separate event-sourced shot aggregate for reusable shot ordering,
and kernel-pinned render/visualization snapshots. Improve onboarding by making
the canonical schema dependency and renderer interpreter/PATH requirement
discoverable in the clean-machine setup path.
