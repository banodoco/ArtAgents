# Custody baseline — megado run: unified execution

Captured at run start (2026-08-22, after worktree creation), before any mutation.

## Source ref and worktree
- HEAD: `b4c70e0ac766c69de0298fa19f3d7fede796a97c` (main @ b4c70e0a, "docs(round6b): correct three falsifiable run-ledger claims (Sol #5)")
- Run worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-unified-oracle`
- Run branch: `oracle-unified-execution`
- Source worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid` (branch `main`)

## Remotes / refs
- origin: https://github.com/peteromallet/Astrid.git (fetch+push)
- origin/main @ b4c70e0a (pushed, verified equal to local main HEAD)

## Other worktrees (untouched by this run)
- /Users/peteromalley/Documents/Astrid-oracle (branch oracle-run, HEAD 0b69557b)
- /Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle (branch oracle-packification, HEAD 0c93fd8a)

## Protected local work in the MAIN worktree (never touched by this run)
Uncommitted user in-flight files (present at baseline; must survive unchanged):
- astrid/core/generation/backends/{__init__,fal,registry}.py (modified)
- astrid/core/generation/backends/wavespeed.py (untracked)
- astrid/core/model_catalog/{models.yaml,taxonomy.py} (modified)
- astrid/core/util/{credentials_scope,http}.py (modified)
- astrid/packs/generation/executors/generate_audio/** and generate_image/** (modified; includes generate_image/skill/SKILL.md with known `astrid start` ghosts — user-owned)
- docs/generation/32-audio-contract.md, 33-music-models.md (modified)
- tests/core/model_catalog/test_audio_taxonomy.py, test_registry.py; tests/core/test_generation_backend_registry.py; tests/core/generation/backends/test_wavespeed_extract_audio_urls.py (modified)
- .megaplan/initiatives/{pluggable-timeline-renderers,timeline-visualization}/ (untracked)
- .oracle/findings/stacked-render-proof.txt (untracked)

## Environment
- macOS arm64 (Apple M2), Darwin 24.4.0, Python 3.11.11 (pyenv), omp agent harness.
- Models: normal + [XHARD] + oracle = openrouter:stealth/ox-alpha (user-declared).
- Disk: constrained (~9-15 GiB free); suite runs need fresh basetemp + cleanup.
