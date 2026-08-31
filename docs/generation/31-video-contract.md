# Video Modality Contract (schema_version: 2)

**Status**: Implemented (Sprint 04)  
**Executor**: `generation.generate_video`  
**Escape hatch**: `external.vibecomfy` (custom video pipelines, frame-level control)

## Canonical video modes

The video modality has five canonical modes.  Three are wired in Sprint 04;
`v2v` and `video-edit` are deferred to a future sprint.

| Mode         | Description | Status |
|-------------|-------------|--------|
| `t2v`       | Text-to-video (prompt → video). | Wired (Sprint 04) |
| `i2v`       | Image-to-video (prompt + image_ref → video; first-frame conditioning). | Wired (Sprint 04) |
| `flf`       | First-last-frame interpolation (prompt + image_ref + image_end_ref → video). | Wired (Sprint 04) |
| `v2v`       | Video-to-video (prompt + video_ref → video; style transfer, reimagining). | Not wired |
| `video-edit` | Instruction-guided video edit (prompt = instruction, video_ref required). | Not wired |

## Wired cells (Sprint 04)

| Model     | Mode | Local | Cloud | Notes |
|-----------|------|-------|-------|-------|
| `wan-2.2` | t2v  |   —   |   ✓   | FLAG-001: no local wan-2.2 t2v template; wan2.1 substitution forbidden |
| `wan-2.2` | i2v  |   ✓   |   ✓   | Local via wan22_i2v_comfy_lightx2v bare template (FLAG-003) |
| `wan-2.2` | flf  |   —   |   ✓   | Q1: fal image-to-video/turbo accepts `end_image_url` |
| `ltx-2.3` | t2v  |   ✓   |   ✓   | |
| `ltx-2.3` | i2v  |   ✓   |   ✓   | FLAG-005: local `image_ref` → `image` rename |
| `ltx-2.3` | flf  |   ✓   |   —   | A5: no cloud flf endpoint for ltx-2.3 |

### Absent cells (not wired, with reasons)

- **wan-2.2 t2v/local**: No local wan-2.2 text-to-video ready template
  exists, and wan2.1 substitution is forbidden by SD-001 (FLAG-001).
- **wan-2.2 flf/local**: No local wan-2.2 first-last-frame template exists.
- **ltx-2.3 flf/cloud**: The fal.ai LTX-2.3 API does not expose a
  first-last-frame endpoint (A5).

## Inputs

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `--mode` | `string` | **yes** | Generation mode: `t2v`, `i2v`, or `flf`. `v2v` and `video-edit` are not wired. REQUIRED (SD-005). |
| `--model` | `string` | **yes** | Model ID from the registry (`wan-2.2`, `ltx-2.3`). |
| `--execution` | `string` | **yes** | `"local"` or `"cloud"`. |
| `--prompt` | `string` | no* | Text prompt for video generation. |
| `--prompts-file` | `file` | no* | JSONL file of per-line generation requests. |
| `--image-ref` | `string` | no | Reference image (required for i2v/flf; first-frame conditioning). |
| `--image-end-ref` | `string` | no | End-frame reference image (required for flf mode). |
| `--count` | `integer` | no | Number of videos (default `1`). |
| `--seed` | `integer` | no | Deterministic seed. |
| `--negative-prompt` | `string` | no | Negative prompt. |
| `--frames` | `integer` | no | Number of frames to generate. |
| `--fps` | `integer` | no | Frames per second. |
| `--duration` | `float` | no | Video duration in seconds (alternative to `--frames`; requires `--fps`). |
| `--resolution` | `string` | no | Output resolution (e.g. `"1280x720"`). |
| `--guidance-scale` | `float` | no | Classifier-free guidance scale. |
| `--steps` | `integer` | no | Number of sampling steps. |

\* `--prompt` and `--prompts-file` are mutually exclusive.

## Outputs

| Port | Type | Description |
|------|------|-------------|
| `generated_videos` | `dir` | Directory at `{out}/videos/` containing generated video files. |
| `video_manifest` | `file` | JSON manifest at `{out}/manifest.json` (common shape + video extensions). |

## Request validation

Same hard-fail semantics as image modality: missing `requires` features fail
before the generation loop; unsupported features are dropped-with-warning
(SD-004).  `--mode` is required.

Per-mode requires:

| Mode | Required inputs |
|------|----------------|
| `t2v` | `prompt` |
| `i2v` | `prompt`, `image_ref` |
| `flf` | `prompt`, `image_ref`, `image_end_ref` |

## Backends

- **local**: `VibeComfyBackend` adapter driving ComfyUI via vibecomfy
  ready templates.  Video templates live under `video/` in the
  vibecomfy ready-templates directory.
- **cloud**: `FalBackend` adapter submitting to fal.ai queue endpoints
  (`fal-ai/wan/*`, `fal-ai/ltx-2.3/*`) via `HttpClient`.

## Video-modality manifest extensions

The `request` object includes video-specific fields: `frames`, `fps`,
`duration`, `resolution`, `image_ref_resolved`, `image_end_ref_resolved`.
Output entries carry `content_hash`, `bytes`, `duration_seconds`, `fps`,
`resolution` (the latter three via ffprobe best-effort; `null` if unavailable).
Manifest `schema_version` is 2 (per SD-006).

## Escape hatch

**For frame-level control, multi-pass pipelines, keyframe conditioning,
LoRAs, custom samplers, or any video workflow beyond the basic happy path,
use `external.vibecomfy` directly.**  The `generation.generate_video` executor
covers basic text-to-video, image-to-video, and first-last-frame
interpolation only — everything else belongs in the escape hatch.

See:
- `astrid/packs/external/vibecomfy/STAGE.md` — VibeComfy workflow runner
  and escape-hatch documentation
- `astrid/packs/generation/executors/generate_video/STAGE.md` — the generate_video
  executor documentation with wired-cells table, CLI examples, and golden
  demo reference
- `astrid/packs/generation/executors/generate_video/golden/demo_wan_ltx_local_cloud.py` —
  golden demo exercising all wired cells with mocked backends
- `docs/generation/20-manifest-schema.md` — manifest JSON shape (v2)
- `docs/generation/00-features.md` — canonical feature list
