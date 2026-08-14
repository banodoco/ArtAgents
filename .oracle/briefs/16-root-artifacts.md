# Explore: root artifact provenance

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle

Identify the producer of every tracked foreign root directory or media file and the narrowest prevention rail. Verified: only fal-voice-upscale/ is tracked at root (6 files); ideogram-competition/, mgt-evkinds-nhi8a13v/, pipeline-tests-_nahkzb4/, avatars/, runs/, coverage.xml are untracked (absent from this worktree). Start from:
- git ls-files | grep -E '^[^/]+/' with depth 1 → full tracked root inventory (also remotion/, themes/, schema/, examples/, docs/, tests/, scripts/, tools/, projects/, .github/, .desloppify/, out/, avatars/, fal-voice-upscale/, coverage.xml, .coverage, .mypy_cache, .pytest_cache)
- fal-voice-upscale/ contents (run_replicate.py, run_round2.py, wav files) — who produced it (git log --oneline -5 -- fal-voice-upscale, blame run scripts; do they reference other repos/APIs?)
- scripts/reshape/check_repo_hygiene.py ROOT_DIR_ALLOWLIST (quote; what would flag a new root dir)
- tests/reshape/test_repo_hygiene.py (what it asserts — tracked paths only?)
- .gitignore (which of these are ignored vs untracked-by-accident)
- scripts/inventory_astrid_projects.py and similar inventory scripts (do they create root dirs?)

Report verified facts with file:line evidence: (1) full tracked root inventory classified: repo product vs tooling vs accidental commit; (2) fal-voice-upscale provenance (commit history, what the scripts do, why it is in the repo); (3) what the hygiene checker currently enforces and its gap (filesystem roots vs tracked paths); (4) recommended deletion set + the narrowest rail (extend ROOT_DIR_ALLOWLIST semantics or test) to prevent recurrence. Ranked findings, <300 words.
