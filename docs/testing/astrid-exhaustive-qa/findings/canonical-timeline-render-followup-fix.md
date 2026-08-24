# Canonical timeline render follow-up fix

Date: 2026-08-24

## Outcome

The two P1 live-agent UX defects from the independent canonical-render replay
are fixed and verified through a fresh public-CLI journey:

1. A fresh successful `astrid timelines render ... --json` now owns stdout and
   emits exactly one JSON document. The nested renderer's transient staging
   path is captured at the capability boundary and is not exposed.
2. Asset-backed clips using the intuitive `clipType: "video"` spelling now
   pass Remotion support selection, staging, and a real render. The same
   built-in-media treatment applies to `media`, `image`, and `audio`.

No product source was changed for MP4 byte determinism because Astrid does not
promise byte-identical fresh encodes. Exact replay remains deterministic by
returning the already-completed run and all of its durable artifacts.

## Root causes and fixes

### P1: nested executor stdout leaked into the product CLI

`CapabilityTaskHandler` invokes pack executor entrypoints in-process. It
captured child stderr but allowed child stdout to escape. The render executor's
long-standing direct-CLI contract prints its output path, so a fresh product
render produced a transient path followed by the product JSON envelope.

The shared task boundary now captures both child stdout and stderr around
`executor_runner.run_executor`. Successful execution discovers artifacts from
the staging/result-manifest contract, not printed paths. On failure, captured
stdout/stderr remain available as bounded, labelled `child_logs`. The render
entrypoint itself still prints its output when used directly; stream ownership
is fixed at the correct nesting boundary rather than by special-casing one
executor.

Changed:

- `astrid/core/task_executor/capability_handler.py`
- `tests/core/test_capability_handler_streams.py`

### P1: built-in media aliases were mistaken for effect ids

The Remotion TypeScript composition already renders non-effect asset-backed
clips as ordinary visual/audio media. The Python support and effect-staging
layers had a narrower exception for only `clipType: "media"`, so `video`,
`image`, and `audio` were incorrectly sent through dynamic effect resolution
and rejected as unregistered effect clip types.

The backend now has one `_BUILTIN_MEDIA_CLIP_TYPES` set used by both support
selection and effect staging. The renderer manifest advertises the same
aliases. Focused guards cover every alias and the staging path specifically.

Changed:

- `astrid/packs/rendering/backends/remotion/run.py`
- `astrid/packs/rendering/backends/remotion/renderer.yaml`
- `tests/packs/rendering/test_remotion_backend.py`

### Resolution authority and the 320x180 -> 1920x1080 observation

The original mismatch was not an encoder defect. `config.output.resolution`
and `config.output.fps` are legacy metadata hints; they are not the render
profile. An explicit render profile is authoritative when supplied. Otherwise
the resolved theme canvas is authoritative, falling back to 1920x1080 at 30
fps.

Changing that precedence would silently turn old metadata into a rendering
request and conflict with the existing typed `RenderProfile` contract. The fix
therefore clarifies the agent-facing skill and `timelines render --profile`
help instead of changing output behavior.

Changed:

- `astrid/packs/_core/skill/SKILL.md`
- `astrid/packs/timeline/cli.py`

### Fresh-encode MP4 byte determinism

Astrid promises deterministic backend selection/request identity and exact
replay of an admitted request. It does not promise that two separately
admitted Remotion/codec executions produce byte-identical MP4 containers.
A lifecycle event changes the canonical timeline head and therefore changes
the pinned authority and invocation identity even when authored config bytes
do not change. A fresh encode is correct in that case; container metadata or
encoder behavior may change its hash.

Accordingly:

- identical canonical request: same completed run and same durable bytes;
- lifecycle-head change: new request/provenance identity, with semantic media
  equivalence required but no byte-hash equality promise.

No codec-level determinism change was made.

## Fresh live CLI evidence

Disposable root:

`ASTRID_PROJECTS_ROOT=/tmp/astrid-canonical-render-followup.X7NEr6/projects`

Created project `fixlab`, generated and imported a one-second H.264/AAC managed
video, then created default canonical timeline `primary` version 1. Its media
clip used exactly:

```json
{
  "id": "source-video",
  "at": 0,
  "track": "source",
  "clipType": "video",
  "asset": "source-video",
  "from": 0,
  "to": 1
}
```

Before rendering, the same canonical document also completed
`timelines visualize primary --format md --filmstrip off --json` as kernel run
`0f761240eb783a241a0e0d3440`, returning its durable manifest and ten supporting
evidence artifacts. Thus create, visualization, and render now agree on the
same explicit video-clip shape.

The config intentionally declared conflicting legacy output hints
`640x360@24`, while its authoritative theme canvas declared `320x180@30`.

Fresh render command:

```bash
python3 -m astrid timelines render primary \
  --project fixlab --expected-version 1 \
  --output-name video-alias.mp4 --json
```

Its stdout was piped directly to Python's strict `json.load`. Parsing
succeeded and reported:

```json
{
  "ok": true,
  "one_json_document": true,
  "run": "5bf8fc2053ca97b2b6cb5a1870",
  "task": "8d05cf8c98c17037ee4e318ed5"
}
```

A prefixed transient staging path or second JSON value would make that parse
fail. The returned artifact paths were durable managed CAS paths:

- video hash:
  `4d4eaaf59d0d323e5dd5d66f8f873006276a2e6ff23edd2aa6c71a8e1408db69`
- provenance hash:
  `2459ad0580ba7a0779c0e125d6d93af0c6157d3971a29b69897735c0831f777f`

`ffprobe` verified H.264, 320x180, and 30 fps. This proves the explicit theme
canvas, not the conflicting legacy `output` hint, controlled the render.

The durable provenance points at the durable video CAS path and pins:

```json
{
  "authority": "kernel",
  "timeline_id": "3a5e2687-ca01-53bf-a91b-d60314b92f0a",
  "timeline_ulid": "5rn417kqy97zk7nqrdjr642ks5",
  "timeline_slug": "primary",
  "config_version": 1,
  "head_event_id": "4514803b00e44e75abbf12bdb296418e",
  "head_hash": "12cecb885086206dc2fc6e85c39acdc70c8c710ed35656ad1e7c45f3e81d6fef"
}
```

Repeating the identical command returned the same run
`5bf8fc2053ca97b2b6cb5a1870` and both artifacts, again as one JSON document.

## Automated guards

Focused run:

```text
pytest -q \
  tests/core/test_capability_handler_streams.py \
  tests/packs/rendering/test_remotion_backend.py::test_support_accepts_builtin_media_clip_type_aliases \
  tests/packs/rendering/test_remotion_backend.py::test_effect_staging_treats_video_as_builtin_media_not_unknown_effect \
  tests/packs/rendering/test_render_facade.py::test_main_accepts_output_name_and_forward_parses_any_order

6 passed in 0.75s
```

The focused modules also compile successfully.

A broader Remotion-backend run produced 29 passes and one unrelated existing
failure in the real alpha-MOV test: a separate output-profile preflight now
requires `.mp4` before the test reaches Remotion. This follow-up neither caused
nor masks that failure; the relevant media-alias and stream-ownership guards
all pass.

## Agent UX verdict

PASS. Fresh and replayed `--json` responses now have the same one-document
grammar, returned paths are durable, the intuitive video clip spelling works
end to end, and render-size authority is explicit in public help instead of
being inferred from legacy timeline metadata.
