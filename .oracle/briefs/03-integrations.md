# Explore: integrations extraction (arnold / reigh / runpod / worker)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle

Explore astrid/core/integrations/ in depth. Start from:
- astrid/core/integrations/__init__.py (docstring) and each child:
  - arnold/ (step_adapter.py, authoring.py, session/{compiler,lowering,driver,cli}.py, host/{cli,compat,core,driver,shapes,registry}.py) — second lifecycle engine via --engine arnold
  - reigh/ (env.py, data_provider.py, timeline_io.py, local_bridge.py, local_bridge_server.py, task_client.py, worker_jwt.py, append_service.py, event_construction.py, supabase_client.py)
  - runpod/ (storage.py, sweeper.py)
  - worker/ (banodoco_worker.py)
- Who imports each: grep across astrid/ (gateway/dispatch.py serve/worker/reigh-data/runpod handlers, cli/project_handlers.py, timeline/asset_registry, packs/reigh/executors, packs/runpod/executors, scripts/)
- Existing packs: astrid/packs/reigh/pack.yaml (executors only), astrid/packs/runpod/pack.yaml (executors), packs/training (ENSURE_STORAGE hint?), packs/rendering

Report verified facts with file:line evidence: for EACH integration domain (arnold, reigh, runpod, worker): what it does, its core importers, its pack consumers, and whether it can move to a pack today or needs a thin host adapter left in core (and what that adapter is). Especially: (1) is `--engine arnold` reachable without importing arnold at gateway startup; (2) does `astrid serve` / `astrid worker` / `astrid reigh-data` require local_bridge_server / worker code at startup or lazily; (3) runpod: are storage/sweeper already shadowed by packs/runpod executors; (4) worker: does packs/reigh depend on worker_jwt? Suggested extraction order + which core stubs remain. Ranked findings, <300 words.
