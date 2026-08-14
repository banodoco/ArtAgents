# Explore: Reigh bridge boundary (generic vs transport)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle

Explore what is generic timeline/asset-registry state vs Reigh transport, so extraction can invert the dependency. Start from:
- astrid/core/timeline/asset_registry_edits.py, asset_registry_state.py (if exists), asset_registry.py, sources.json handling
- astrid/core/integrations/reigh/ (local_bridge.py, local_bridge_server.py, timeline_io.py, data_provider.py, env.py, event_construction.py, supabase_client.py, append_service.py)
- astrid/core/timeline/eventlog/reigh_events.py, supabase_client.py (host protocol pieces), eventlog/selector.py (preferred_backend="supabase")
- astrid/core/cli/project_handlers.py (remote timeline mutation), cli/timeline_*.py
- Consumers: gateway serve (local_bridge_server), worker (banodoco_worker), packs/reigh executors, scripts/reigh_seed_timeline_events.py, .github/workflows/bridge-latency.yml
- Tests: tests/timeline/test_asset_registry_sync.py, tests/integrations/reigh/

Report verified facts with file:line evidence: (1) the exact "read latest asset-registry sidecar/event" logic that is generic (quote it; where does it live?); (2) what the Reigh bridge adds on top (transport, JWT, HTTP, cross-project --projects-root behavior); (3) which of the generic pieces core/timeline already owns vs which are buried in integrations/reigh; (4) the event-stream recovery, CAS, sidecar repair, no-pruning behaviors in tests/timeline/test_asset_registry_sync.py — which functions they pin; (5) cross-project server behavior (local_bridge_server --projects-root) — is it Reigh-specific or generic? Suggest the host helper (e.g. core/timeline/asset_registry_state.py) shape and what moves to packs/reigh/integration/. Ranked findings, <300 words.
