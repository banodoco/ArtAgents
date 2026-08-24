# Human Notes

**Executor**: `editorial.human_notes`  
**Status**: implemented  
**Role**: Auxiliary (outside the numbered pipeline)

Converts free-text human editorial revision notes into structured
`editor_review.json` for downstream pipeline consumption. This is an
auxiliary tool — it does not appear in the numbered pipeline step order.
Use it when a human editor provides plain-language revision instructions
(e.g., "swap clip 3 with something punchier, trim the first 2 seconds off
clip 7") that need to be translated into the structured note format
expected by the editorial pipeline.

The executor uses Claude (via `editorial.editor_review`'s response schema
and validation) to ground human instructions in the actual arrangement and
pool. It maps free-text intent to the correct editor action (accept,
micro-fix, swap, reorder, insert-stinger, needs-better-pool-entry),
identifies the correct `clip_uuid` values, and sets appropriate priority
and brief_impact fields.

An optional `--apply` flag chains the full revise pipeline: it re-runs
arrange (in revise mode), cut, refine, and render with the generated
editor_review.json, enabling a human-notes → rendered-video round-trip.

## SDK quick-start

Translate human notes into structured editor_review.json:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.human_notes",
        kind="executor", project="demo",
    inputs={
        "instructions": "./notes.txt",
        "arrangement": "./out/arrangement.json",
        "pool": "./out/pool.json",
    },
)
```

With full pipeline application after translation:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.human_notes",
        kind="executor", project="demo",
    inputs={
        "instructions": "./notes.txt",
        "arrangement": "./out/arrangement.json",
        "pool": "./out/pool.json",
        "apply": True,
        "brief": "./briefs/my-hype.md",
        "brief_dir": "./out",
        "run_dir": "./runs/my-run",
        "video": "./source.mp4",
        "env_file": ".env.local",
    },
)
```

## Inputs

| Name         | Type | Required | Description                                      |
|--------------|------|----------|--------------------------------------------------|
| instructions | file | yes      | Plain-text human revision instructions            |
| arrangement  | file | yes      | Existing arrangement.json to ground notes against |
| pool         | file | yes      | Existing pool.json for candidate clip reference   |
| env_file     | file | no       | Optional env file for Claude API credentials      |

## Outputs

| Name          | Type | Path                          | Description                              |
|---------------|------|-------------------------------|------------------------------------------|
| editor_review | file | `{out}/editor_review.json`    | Structured review notes from human input |

## Auxiliary tool

`editorial.human_notes` is an auxiliary executor — it is **not** part of the
numbered editorial pipeline (steps 0–14). It bridges human editorial intent
into the pipeline's structured format but does not appear in the automatic
pipeline execution order. Use it ad-hoc when human revision notes are
available, then feed the resulting `editor_review.json` into
`editorial.arrange` (revise mode) or `editorial.refine` as appropriate.

There is no `pipeline_step_order` in executor.yaml for this executor,
and no `depends_on` graph — it operates standalone on user-provided files.
