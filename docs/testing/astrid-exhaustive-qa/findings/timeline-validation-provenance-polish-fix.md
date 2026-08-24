# Timeline validation and provenance polish — live UX fix

Date: 2026-08-24  
Wave: independent Luna live-agent CLI replay  
Result: **PASS after bounded fixes** (three P2 ergonomics defects confirmed and corrected)

## Scope and method

This was a live agent-UX replay through the public Astrid CLI, not a source-led
or programmatic test exercise. Source was inspected only after the failures
were reproduced. The disposable root was:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-timeline-polish.4eXw1b/projects
project slug: polish
project id: 4f09e301-4c46-5516-bed3-f6f8748541b9
```

The wave tested:

1. the documented shape of clip fade envelopes versus reusable visual-effect
   element references;
2. admission behavior for an unknown referenced element id;
3. the size, actionability, and machine structure of invalid timeline errors;
4. non-overrejection of arbitrary nested clip parameters;
5. visualization source provenance and frozen `--from-view` navigation.

## Finding 1 — unknown reusable element was rejected too late (P2)

### Before

The canonical timeline `unknown-element` contained this clip:

```json
{
  "id": "unknown",
  "at": 0,
  "track": "fx",
  "clipType": "definitely-missing-effect",
  "hold": 1,
  "params": {"amount": 1}
}
```

The draft was intentionally accepted. Rendering then admitted run
`16cf625033c6e2a2b674198408`, task `2fbb56a6fab3d6bde8c626abc9`, and attempt
`01m0sp1y0p4p6b5kgmd3bc6h38` before failing with:

```text
timeline uses unregistered Remotion clip types: definitely-missing-effect
```

The failure was correct, but admission was wasteful and made an authoring error
look like a renderer/runtime failure.

### Canonical effect shape established

There are two distinct concepts:

- `clip.effects` is only a fade envelope. It accepts a numeric map such as
  `{"fade_in":0.2,"fade_out":0.2}` or a list of objects containing only
  `fade_in` / `fade_out`.
- A reusable registered visual element is the clip itself:
  `{"clipType":"<effect-id>","params":{...}}`.

The core and rendering agent skills now say this explicitly.

### After

Live command:

```bash
python3 -m astrid timelines render unknown-element \
  --project polish --expected-version 1 --json
```

returned exit 1 and one typed JSON envelope. The actionable detail was:

```json
{
  "path": "$.clips[0].clipType",
  "reason": "unregistered reusable visual element id 'definitely-missing-effect'",
  "recovery": "Use a built-in clipType ... or an installed effect id ...",
  "validator": "registered_element_reference"
}
```

All IDs were null:

```text
run_id=null
kernel_run_id=null
kernel_task_id=null
kernel_attempt_id=null
```

The public `runs list` count stayed **3 -> 3**, proving zero admission.

The preflight checks only `clips[*].clipType`. It does not recursively scan
`params`, `generation`, or other opaque maker metadata.

## Finding 2 — schema diagnostics were an enormous raw dump (P2)

### Before

The timeline `effect-object` used an intuitive but invalid reusable-effect
shape in `clip.effects`:

```json
"effects": [{"id":"definitely-missing-effect","params":{"amount":1}}]
```

Canonical create accepted the draft as intended. Managed render rejected it
before admission, but the top-level message included jsonschema's full schema
fragment and instance dump (`Failed validating ... On instance ...`). The
useful fact was buried in several screens of protocol internals.

### After

Live command:

```bash
python3 -m astrid timelines render effect-object \
  --project polish --expected-version 1 --json
```

returned a 333-character top-level message, with no schema dump:

```text
canonical timeline 'effect-object' is not renderable at
$.clips[0].effects[0]: Additional properties are not allowed ('id', 'params'
were unexpected). Recovery: Use clip.effects only for fade timing
(fade_in/fade_out, or a numeric fade map). Reference a reusable visual element
with clipType:<effect-id> and params:{...}, then retry.
```

Structured detail was retained:

```json
{
  "path": "$.clips[0].effects[0]",
  "reason": "Additional properties are not allowed ('id', 'params' were unexpected)",
  "recovery": "Use clip.effects only for fade timing ...",
  "schema_path": "$.properties.clips.items.properties.effects.anyOf[0].items.additionalProperties",
  "validator": "additionalProperties"
}
```

The run count again stayed **3 -> 3**, and all run/task/attempt IDs were null.
Draft creation remains permissive; only the transition to canonical managed
render gets this strict preflight.

## Non-overrejection proof

A new canonical timeline `opaque-params` used a valid `clipType:"text"` and
arbitrary nested vendor data, deliberately including a suspicious string:

```json
"params": {
  "vendor": {
    "effect": "definitely-not-an-element-reference",
    "nested": [1, 2, 3]
  }
}
```

Creation succeeded, then managed rendering succeeded:

```text
run:     f00e5b97c92df002613ded097e
task:    cfbdd72502cb2672e0288b4d1a
attempt: 01m0spnkz0ts6e33e6pn20h1kj
video:   sha256:3f59fd13b3ab0ded9b2cf3a920b72956ed235190c6a5d53b169eca838ed16fa2
```

This proves the fix fails closed on the actual reference surface without
treating ordinary metadata as capability references.

## Adjacent positive-control regression — registered effect crashed (P1)

A positive control used the real registered `text-card` element with
`clipType:"text-card"` and valid `params`. Preflight correctly admitted it,
but the run failed with:

```text
render service failed: name 'json' is not defined
```

Evidence was run `2650d79af20173cde0956ee522`, task
`125ff0be3ec06965800876b9d7`, attempt `01m0sptvj3fjpztz8x7abrn1xg`.
The root cause was direct: `astrid/core/rendering/service.py` still used
`json.loads` / `json.dumps` in several support and planning paths, but its
`import json` had been removed in the dirty shared branch. The bounded repair
restored that import.

Because a failed request replays its immutable failed identity, the same
canonical config was CAS-saved as version 2 and rendered with the new pin.
The registered element then rendered successfully:

```text
run:     8f23f7e949e769255c4e646031
task:    3a3212488140bc3252922acd0e
attempt: 01m0spwq85fg08ae5vkb5jmx68
video:   sha256:8ce10795e5641f4480d1da268c61a62575938f36920dcfc9250aa1b9c9286d45
```

## Finding 3 — visualization source provenance was ambiguous (P2)

### Before

The successful `visual-clean` manifest at:

```text
/private/tmp/astrid-timeline-polish.4eXw1b/projects/.astrid/media/sha256/56/6a/566a5d06087b759e558864ba59249d00473d810be33649a09eb0ba77cb1b4afd
```

contained:

```json
"inputs": {"timeline_source":["polish"], ...}
```

`polish` is a project slug, not a timeline source path or timeline identity.
The exact timeline identity appeared only later under `snapshots`, and the
resolved project UUID was absent.

### Compatibility-safe correction

`timeline_source` is retained byte-for-shape as the frozen v1 compatibility
locator. Three optional additive fields now disambiguate it:

```json
{
  "source_mode": "project",
  "resolved_project": {
    "id": "4f09e301-4c46-5516-bed3-f6f8748541b9",
    "slug": "polish"
  },
  "resolved_timelines": [{
    "qualified_ref": "TL01",
    "stable_id": "TL01",
    "uuid": "77851c79-5683-58ee-905c-b8f098864917",
    "ulid": "MPMD61RK5FD0MBXKMW5GGJM3Q6",
    "slug": "opaque-params"
  }]
}
```

The new live manifest is the durable CAS file:

```text
/private/tmp/astrid-timeline-polish.4eXw1b/projects/.astrid/media/sha256/a9/be/a9bee1f12e7092121532222b8abe87a6b024cc70b797d379eb433923eff02e09
```

The new fields are optional in the v1 schema, so existing frozen packs without
them still validate. Existing ownership/navigation checks continue to use the
unchanged legacy field.

### Frozen navigation proof

The durable CAS manifest above was passed directly to:

```bash
python3 -m astrid timelines visualize --project polish \
  --from-view <durable-manifest-path> --focus TL01 --format md --json
```

Navigation succeeded as run `770a75c852e85b5953812b5fbb`; its child manifest
retained the same resolved project and timeline identity and recorded the exact
parent path/focus.

## Implementation boundaries

- `managed_timeline.py`: concise structured preflight error plus managed-only
  registered-element validation.
- SDK/CLI error plumbing: preserves the structured `validation` object in the
  public envelope.
- shared render service: restored its required `json` import after the live
  registered-element positive control exposed the missing dependency.
- visualization evidence manifest: additive source mode and resolved identity;
  legacy `timeline_source` retained.
- core/rendering skills: canonical fade-envelope versus reusable-element shape.
- no product source was changed outside these bounded paths; unrelated dirty
  workspace changes were preserved.

## Verification

Focused checks:

```text
47 passed in 6.46s
```

Coverage included:

- unknown effect id rejected before snapshot materialization;
- concise structured schema failure and recovery;
- arbitrary nested params accepted;
- new provenance manifest schema validation;
- stripped legacy manifest (without additive fields) still schema-valid;
- timeline visualization schema suite.

Targeted Ruff checks on the newly changed managed validator, exception surface,
timeline CLI, and evidence pack passed. A broad Ruff invocation also reported
pre-existing import-order/entrypoint-guard exceptions in shared `run.py` and
`invocation.py`; those files already contained substantial unrelated changes,
so this wave did not bulk-format or rewrite them.

## Agent UX verdict

**PASS.** The remaining behavior is coherent:

- authoring drafts remain permissive;
- canonical render admission fails closed on actual element references;
- errors identify one JSON path, one reason, and one recovery while retaining
  machine-readable detail;
- opaque maker metadata stays opaque;
- visualization manifests now state exactly which project and timeline were
  resolved without invalidating existing frozen packs.
