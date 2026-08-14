# Explore: test rails (what guards each seam)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle

Explore the test suite to map the safety net for each planned change. Start from:
- tests/ top-level: test_url_pipeline_smoke.py, test_sdk_rendering.py, test_sdk_render_context.py, test_pipeline_caching.py, test_override.py, test_human_notes.py, test_canonical_aliases.py, test_asset_cache.py, tests/session/, tests/reshape/, tests/packs/ (list and describe)
- Grep tests for coverage of: pack discovery (discover_pack_metadata), skills discovery/install, element registry default_sources / theme elements / legacy_workspace, generation backends (fal/vibecomfy/codex ids), gateway verbs (runpod/reigh-data/worker/scratch), validate_first_party / packs validate, alias resolution (test_canonical_aliases.py), import-layering validation
- scripts/smoke_wheel_install.sh (what does it smoke), scripts/reshape/ (what is this — migration scripts?)
- pytest config in pyproject.toml (testpaths, markers), any CI workflows (.github/workflows/) that run tests

Report verified facts with file:line evidence: (1) per planned move (a) discovery load graph, (b) generation backends extraction, (c) integrations extraction, (d) host verb retirement, (e) legacy_workspace removal, (f) allowlist refresh: which tests would catch a regression, which would need updating, which seams have NO test coverage; (2) whether any test asserts the CURRENT behavior that the plan changes (list them — they will need updating as part of the change, not after); (3) how long the suite takes / what CI runs. Suggested "test rail" additions the executor should include with each batch. Ranked findings, <300 words.
