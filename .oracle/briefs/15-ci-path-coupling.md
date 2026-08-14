# Explore: CI path coupling

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle

Inspect CI and scripts for hardcoded paths that would silently stop working after the planned extractions (core/integrations moves, host verb removals, pack layout changes). Start from:
- .github/workflows/* (list all; read triggers, steps, path filters). Known: bridge-latency.yml (Reigh bridge — check its paths/scripts), any test/typecheck/lint lanes, ci-lanes.md reference
- scripts/reshape/run_ci_checks.sh (what does it run — quote)
- scripts/reshape/check_repo_hygiene.py (ROOT_DIR_ALLOWLIST — quote; what it checks)
- scripts/ references to astrid/core/integrations/*, gateway verbs (serve/worker/reigh-data/runpod/publish), packs/blender, experiments (grep scripts/ + .github/)
- Makefile (test/ci targets)
- Any docs/guides referencing CI lanes that name files being moved

Report verified facts with file:line evidence: (1) complete CI surface (workflows + script lane) with the exact paths each touches; (2) which lanes reference code being moved (integration paths, gateway verbs, blender, experiments) — for each: what silently stops running after the move; (3) whether tests referenced by CI (tests/integrations/reigh, tests/packs/runpod, etc.) are path-pinned anywhere; (4) the ROOT_DIR_ALLOWLIST contents and its hygiene checks. Suggest per-lane update list. Ranked findings, <300 words.
