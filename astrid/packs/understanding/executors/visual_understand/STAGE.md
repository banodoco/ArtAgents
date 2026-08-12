---
name: visual_understand
description: Inspect images or sampled video frames with an OpenAI vision model — free-text query or JSON-schema-constrained structured output.
---

# Visual Understand

Wraps OpenAI's `/v1/responses` vision API. Pass an image (or a video plus
`--at` timestamps) plus a free-text `--query` and get the model's answer.

## Modes

**Free-text (default):**
```bash
python3 -m astrid executors run understanding.visual_understand \
  --input image=path/to.jpg \
  --query "Describe this scene in one sentence." \
  --out runs/x/answer.json
```

**Structured-output (schema-constrained):** pass `--response-schema PATH` to
force the model's reply to be JSON validating against your schema. Uses the
OpenAI Responses API `text.format = json_schema` (strict mode).

```bash
python3 -m astrid executors run understanding.visual_understand \
  --input image=path/to.jpg \
  --query "Classify into one bucket from this list." \
  --response-schema my_schema.json \
  --out runs/x/answer.json
```

Schema file may be either the raw JSON schema or an object of the form
`{ "name": "<id>", "schema": {...}, "strict": true }`. If you pass the raw
schema, the name defaults to `"response"` and strict defaults to true.

## Ordered multi-image evidence API

Evaluation gates that must preserve original page resolution and order use the
additive Python API in `visual_understand.run`:

```python
evidence = understand_ordered(
    ordered_png_paths,
    prompt=reading_guide,
    model="gpt-5.6-sol",  # explicit provider id; aliases are rejected
    settings={"detail": "high", "max_output_tokens": 700, "cost_ceiling": 12},
    structured=answer_schema,
)
artifact_path.write_bytes(evidence.to_json_bytes())
```

This sends one Responses API request with one `input_image` block per source
file, in caller order. It never enters the crop/contact-sheet pipeline. The
returned `OrderedImageEvidence` contains the exact paths and byte hashes,
prompt hash, resolved settings and ceiling, requested and returned model ids,
response id, usage, and client-validated answers. Its canonical JSON excludes
wall-clock metadata and is suitable for an ignorable run artifact.

## Use cases

- **VLM bucket-judge / caption with locked vocab.** Generate a schema whose
  fields are enums over your vocabulary file; the model can't emit
  out-of-vocab tokens. This is how dataset-build configs can enforce
  caption-template adherence without a project-specific VLM wrapper.
- **One-off image questions.** Skip `--response-schema` and use the free-text
  mode.
- **Crop / contact-sheet contact.** See `--crop-aspect`, `--cols`, etc.

## Models

`--mode fast` (gpt-4o-mini, default, cheap) or `--mode best` (gpt-5.4, full
detail). Pass `--compare-model <id>` to fan out the same query across
multiple models.

## Frames from video

```bash
python3 -m astrid executors run understanding.visual_understand \
  --input video=clip.mp4 \
  --query "What's happening at these moments?" \
  -- --at 0:05,0:12,0:20
```

Run `editorial.boundary_candidates` first if you need help picking timestamps.
