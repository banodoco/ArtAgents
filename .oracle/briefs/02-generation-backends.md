# Explore: generation backends extraction seam

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle

Explore the generation backends seam in depth. Start from:
- astrid/core/generation/backends/{__init__,base,registry,fal,vibecomfy,codex}.py — especially _builtin_generation_backend_descriptors() (registry.py ~185-205), GENERATION_RESULT_KEY, verb/feature imports
- astrid/core/generation/verbs.py (legacy "plugin" = pack extension language), features.py
- astrid/packs/generation/ (pack.yaml — has NO extensions block; executors/ incl. generate_image etc.)
- The pack manifest extensions hook: astrid/core/pack/schemas/v1/pack.json (~lines 108-128, extensions.generation.backends) — quote the schema shape
- Consumers: astrid/sdk/generation.py, astrid/sdk/discovery.py, gateway `astrid generate`, astrid/core/model_catalog/ (CLOUD_BACKEND_* env ids?), packs/generation executors importing BackendAdapter/FalBackend/CodexBackend directly, scripts/gen_effect_registry.py or similar

Report verified facts with file:line evidence: (1) the exact mechanism _builtin_generation_backend_descriptors uses (ids, env vars, lazy imports) and who consumes it; (2) whether the extensions.generation.backends hook is actually read anywhere in core today (grep for it) or is schema-only; (3) what moving fal.py/vibecomfy.py/codex.py into packs/generation would break (direct imports from core, sdk, model_catalog); (4) whether builtin backend ids are referenced in pack.yaml aliases/manifests elsewhere. Suggested approach: smallest change that moves the three backends into the generation pack via the existing hook, with what stays in core (base protocol, registry). Ranked findings, <300 words.
