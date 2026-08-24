# Replay — render cleanup and external animation 2

Date: 2026-08-23  
Verdict: **PASS**, with one noted disposable-root friction (an empty staging parent needed explicit removal).

## Scope and isolation

This was a fresh live UX replay using only the public Astrid CLI, SDK, and
documentation contract. No product code, tests, or existing QA reports were
modified or used as inputs.

Disposable roots:

- Projects root: `/tmp/astrid-live-replay-Hy7agm`
- External pack collection root: `/tmp/astrid-live-pack-zAtdwh`
- Pack: `/tmp/astrid-live-pack-zAtdwh/external_anim_pack`

The collection root was supplied both ways, with the identical canonical path:

```text
ASTRID_PACKS_PATH=/tmp/astrid-live-pack-zAtdwh
sdk.discover(..., extra_pack_roots=['/tmp/astrid-live-pack-zAtdwh'])
```

The pack was created with the public pack CLI, containing one Remotion
animation `slide-fade`, and validated successfully:

```text
PYTHONPATH=/Users/peteromalley/Documents/reigh-workspace/Astrid \
  python3 -m astrid.core.pack.cli validate \
  /tmp/astrid-live-pack-zAtdwh/external_anim_pack --warnings
=> valid
```

## Discovery

SDK discovery returned `animations/slide-fade` exactly once. Its definition
reported `source=pack:external_anim_pack`, the external component root, and the
Remotion adapter. The render provenance also recorded the external collection
root exactly once in `active_pack_order`, the animation element root exactly
once in `element_roots`, and the resolved animation exactly once for
`title_clip`; there was no duplicate canonical root from the simultaneous env
and SDK configuration.

## Successful project-scoped render

Created project `live-replay` and default timeline `title`, then saved a small
valid 640×360, 30 fps text timeline with a two-second `title_clip` and
`entrance.type=slide-fade`.

The project-scoped SDK call was:

```python
sdk.invoke(
    'rendering.render',
    kind='executor',
    include_installed=False,
    extra_pack_roots=['/tmp/astrid-live-pack-zAtdwh'],
    project='live-replay',
    inputs={
        'timeline':
        '/tmp/astrid-live-replay-Hy7agm/live-replay/render-input.timeline.json'
    },
)
```

It returned `ok=true`, run id `409fef8debf1eda6b17d1f5070`, and these durable
managed paths (both existed after the invocation and remained probeable):

- MP4: `/private/tmp/astrid-live-replay-Hy7agm/.astrid/media/sha256/25/16/251611aca477b389cc59de9353b6b20017f797883132a319e6365b1e4fbe1daa`
- Provenance: `/private/tmp/astrid-live-replay-Hy7agm/.astrid/media/sha256/81/23/81231c271fc096a236e376432679e7ce6076d64c317bb003d37af5fb9d6302a6`

`ffprobe` confirmed a 2.048-second, 640×360 H.264/AAC MP4 at 30 fps and
93,616 bytes. A decoded frame at 1.0 seconds visibly contained the rendered
white “EXTERNAL SLIDE FADE” title on black. Start/entrance/mid frame SHA-256s
were different, and the entrance frame visibly showed the external animation’s
partial slide/fade before the fully visible mid frame.

Provenance named `slide-fade`, `source_pack_id=external_anim_pack`, the exact
external element root, and `clip_ids=[title_clip]`.

## Unknown animation fail-closed replay

Changed only the entrance type in a second project-owned timeline to
`missing-external-animation` and invoked the same project-scoped SDK route with
the same `extra_pack_roots`.

Observed result:

```text
ok=false
outputs={}
error.type=RuntimeError
error.sdk_error=CapabilityRuntimeError
error.reason=handler_failed
message=rendering.remotion does not support this render request: \
timeline uses unregistered animation 'missing-external-animation'
```

The managed media tree contained two files before the failure (the successful
MP4 and provenance) and two afterward; the before/after file listing had no
diff. No new output or provenance artifact was published.

## Cleanup and health

Both the successful and failed invocations left no child invocation directory
under `.astrid/media/.staging`. The runtime left an empty top-level staging
parent; because the root is disposable, it was removed explicitly with `rmdir`
after verifying it was empty. A final check reported `staging_dir=absent`.

Final `python3 -m astrid doctor --json` returned `ok: true` with:

- managed data and media paths accessible;
- SQLite quick check `ok`;
- no foreign-key violations;
- schema versions `core=1, references=1, shots=1, timeline=1`;
- no orphan-staging warning.

Friction encountered: project-owned render inputs must be passed as absolute
paths under the project directory. An outside-root path and a relative path
resolved from the caller cwd both failed early with typed
`ProjectOwnershipError`; neither produced artifacts. Running the public pack
CLI from the disposable external cwd also required the repo on `PYTHONPATH`.

Only the disposable project/pack roots and temporary frame/listing probes were
created; no product files were changed.
