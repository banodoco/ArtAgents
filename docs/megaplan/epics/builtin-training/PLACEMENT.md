# PLACEMENT: Module/File Ownership Map

> **Status:** FROZEN — M0 handoff. M1-M4 must follow this map.
> **Target end state:** After M4, nothing remains under `astrid/packs/seinfeld/`.

## Generic Built-In Homes

### Dataset Orchestrator Package
- **Location:** `astrid/packs/builtin/dataset_build/`
- **Contents:** Orchestrator YAML, run.py, STAGE.md, `__init__.py`
- **Notes:** Created in M1. Replaces `seinfeld.dataset_build`.

### Source Providers
- **Location:** `astrid/packs/builtin/dataset_build/source_providers/`
- **Contents:** `__init__.py`, `youtube_provider.py` (M1), `local_folder_provider.py` (M1 or later), placeholder files for `reigh_asset`, `stock_api`, `generated`, `image_audio`, `paired`
- **Notes:** Provider registry pattern: `provider_id -> module.ProviderClass`.

### Caption Providers
- **Location:** `astrid/packs/builtin/dataset_build/caption_providers/`
- **Contents:** `__init__.py`, `visual_understand_provider.py` (M1), `video_understand_provider.py` (M1), placeholder for `transcribe_provider`
- **Notes:** Wraps existing `builtin.visual_understand`, `builtin.video_understand`, `builtin.transcribe`.

### Filter Stages
- **Location:** `astrid/packs/builtin/dataset_build/filter_stages/`
- **Contents:** `__init__.py`, `duration_filter.py` (M2a), `resolution_filter.py` (M2a), `content_hash_filter.py` (M2a), `black_frame_filter.py` (M2a), `source_cap_filter.py` (M2a), `rights_filter.py` (M2a), `semantic_filter.py` (M2b), `transcript_filter.py` (M2b), `near_duplicate_filter.py` (M2b)
- **Notes:** Each filter implements `FilterStage` Protocol from `contracts/interfaces.py`.

### Manifest Adapters
- **Location:** `astrid/packs/builtin/dataset_build/manifest_adapters/`
- **Contents:** `__init__.py`, `ai_toolkit_ltx.py` (M1)
- **Notes:** Adapter registry: `format_id -> adapter instance`. ai-toolkit-ltx exports flat `clips` shape per `ai-toolkit-adapter-manifest.schema.json`.

### Generic Review UI Assets
- **Location:** `astrid/packs/builtin/dataset_build/review_ui/`
- **Contents:** `review.html`, `review.js`, `review.css`
- **Notes:** Moved from `seinfeld/dataset_build/review.html` in M1. Generic, list-first UI. No Seinfeld-specific prompts or branding.

### Training Orchestrator Package
- **Location:** `astrid/packs/builtin/training_run/`
- **Contents:** Orchestrator YAML, run.py, STAGE.md, `__init__.py`
- **Notes:** Created in M3. Replaces `seinfeld.lora_train`.

### Trainer Adapters
- **Location:** `astrid/packs/builtin/training_run/trainer_adapters/`
- **Contents:** `__init__.py`, `ai_toolkit_ltx.py` (M3)
- **Notes:** Adapter registry: `trainer_id -> adapter`. First: ai-toolkit-ltx.

### Compute Backends
- **Location:** `astrid/packs/builtin/training_run/compute_backends/`
- **Contents:** `__init__.py`, `runpod_backend.py` (M3)
- **Notes:** Backend registry: `backend_id -> backend`. First: runpod.

### AI-Toolkit Support Code
- **Location:** `astrid/packs/builtin/training_run/aitoolkit_support/`
- **Contents:** `stage.py`, `train.py`, `samples.py`, `register.py`
- **Notes:** Generalizes `seinfeld/aitoolkit_stage`, `seinfeld/aitoolkit_train`, `seinfeld/samples_collage`, `seinfeld/lora_register`. No Seinfeld-specific paths or defaults.

### Creative-Writing / Script Pipeline
- **Location:** `astrid/packs/builtin/script_pipeline/`
- **Contents:** Executor YAML, run.py, STAGE.md, `__init__.py`, `presets/`
- **Notes:** Extracted from `seinfeld.script_pipeline` in M4. Generic pipeline: parallel rough attempts → synthesis → voice pass → judge/select. Seinfeld-specific prompts and laugh-tag policy become a preset config, not built-in code.

### Script Pipeline Presets
- **Location:** `astrid/packs/builtin/script_pipeline/presets/`
- **Contents:** `seinfeld.yaml`, `always_sunny.yaml`
- **Notes:** Preset configs that encode show-specific writing rules, prompts, and voice/style parameters.

## Example and Config Locations

### Example Dataset Configs
- **Location:** `examples/configs/dataset/`
- **Contents:** `seinfeld-dataset.yaml`, `always-sunny-dataset.yaml`
- **Notes:** Config files that reproduce Seinfeld/Always Sunny behavior through `builtin.dataset_build`.

### Example Training Configs
- **Location:** `examples/configs/training/`
- **Contents:** `seinfeld-training.yaml`, `always-sunny-training.yaml`
- **Notes:** Config files for `builtin.training_run` with ai-toolkit-ltx trainer.

### Fixtures
- **Location:** removed
- **Contents:** The former checked-in offline fixture tree has been retired.
- **Notes:** Historical fixture planning remains in `FIXTURES.md`; active docs should use placeholder paths or project-local fixtures.

## Historical / Archived Locations

### Seinfeld Example Vocabulary
- **Location:** `docs/examples/seinfeld/vocabulary.yaml`
- **Contents:** Wired vocabulary fixture referenced by `examples/configs/training/seinfeld-training.yaml`.
- **Notes:** Historical Seinfeld archive docs and schemas were retired after migration.

## Existing Executors (Unchanged)

These existing built-in executors remain in place — they are dependencies of the new orchestrators, not targets for migration:

| Executor | Location | Used By |
|---|---|---|
| `builtin.human_review` | `astrid/packs/builtin/human_review/` | M1 dataset review |
| `builtin.youtube_audio` | `astrid/packs/builtin/youtube_audio/` | M1 source acquisition |
| `builtin.scenes` | `astrid/packs/builtin/scenes/` | M1 scene detection |
| `builtin.visual_understand` | `astrid/packs/builtin/visual_understand/` | M1 captioning, M2b semantic |
| `builtin.video_understand` | `astrid/packs/builtin/video_understand/` | M1 captioning, M2b semantic |
| `builtin.transcribe` | `astrid/packs/builtin/transcribe/` | M2b transcript filtering |
| `builtin.audio_understand` | `astrid/packs/builtin/audio_understand/` | Future audio workflows |
| `builtin.understand` | `astrid/packs/builtin/understand/` | Dispatcher (unchanged) |

## Deletion Target

After M4, the following is REMOVED:

```
astrid/packs/seinfeld/          # entire directory
```

Before deletion, all useful code has moved to generic homes under `astrid/packs/builtin/` or `examples/`. The deletion is the final M4 step, gated on:
- Example configs exist for Seinfeld and Always Sunny
- Script pipeline preset configs exist
- Historical docs are archived
- All tests pass against generic homes

## What Does NOT Move

- `astrid/packs/seinfeld/dataset_build/run.py` bucket-fill loop → replaced by generic orchestrator
- `astrid/packs/seinfeld/dataset_build/review.html` → replaced by generic review UI
- Seinfeld-specific hardcoded queries, bucket maps, character descriptions → example configs only
- `builtin.human_review` → stays in place (already generic)
- `builtin.youtube_audio`, `builtin.scenes`, etc. → stay in place (already generic executors)
