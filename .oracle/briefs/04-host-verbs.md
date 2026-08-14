# Explore: host verbs inventory (gateway dispatch)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle

Explore the gateway verb surface in depth. Start from:
- astrid/core/gateway/dispatch.py — _TOP_LEVEL_HANDLERS (full inventory: attach, sessions, start/next/ack/skip/abort, status, packs, executors, orchestrators, elements, skills, doctor, setup, audit, projects, timelines, themes, models, modalities, runpod, reigh-data, worker, publish-youtube, upload-youtube, scratch, serve, runs, orchestrate, author, renderers, replay, events, plan, hooks, claim, test...), _dispatch_* functions, _dispatch_executor_main, _dispatch_runpod, _dispatch_scratch, _dispatch_serve, _dispatch_worker, _dispatch_reigh
- astrid/core/gateway/help.py (_print_entrypoint_help), project.py, scratch.py, runpod.py
- astrid/core/gateway/__init__.py (dispatch table, session gate, verb allowlists)
- CLI contract: astrid/core/cli_contract.py, any argparsers

Report verified facts with file:line evidence: (1) complete table of _TOP_LEVEL_HANDLERS entries: verb → handler → runtime vs capability-shaped (capability-shaped = runpod, reigh-data, worker, publish-youtube, upload-youtube); (2) which capability-shaped verbs already delegate to pack executors via _dispatch_executor_main and which have bespoke code (runpod.py); (3) the exact callers of gateway/runpod.py and how `astrid runpod` maps to core/integrations/runpod; (4) whether scratch/serve are load-bearing for packs (who calls them); (5) the session-gate rules for unbound commands (list of legal unbound verbs) — do runpod/reigh-data/worker bypass it? Suggested retire plan per capability-shaped verb: what replaces it (executors run <id>), what breaks, what docs/help mention it. Ranked findings, <300 words.
