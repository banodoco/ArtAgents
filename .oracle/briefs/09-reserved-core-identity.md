# Explore: reserved _core identity

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle

Trace every place `_core` (the pack-id) is special-cased today, and what a "reserved _core id" rule must cover. Start from:
- astrid/packs/_core/ (skill/SKILL.md only; no pack.yaml) and astrid/core/pack/validate_first_party.py (_FIRST_PARTY_INTERNAL_DIRS = {"_core"}), validate_layout.py (INTERNAL_PACK_DIRS / underscore skip)
- astrid/core/pack/schemas/v1/_defs.json + pack.json (id pattern? reserved ids? schema-level id validation)
- astrid/core/pack/_common.py (id helpers), loader.py (underscore-prefixed dir handling), discovery.py (does it enumerate _core today?)
- astrid/skills/ harness branding: harnesses/{claude,codex,hermes}.py special-case pack_id == "_core" → symlink/install name "astrid"; skills/registry.py, state.py (installed table excludes _core?), cli.py
- Any aliases referencing _core (grep for "_core" across astrid/ and docs/)
- astrid/packs/_core/skill/SKILL.md content: does it index discord_local/seedance_local (stale)? (git-verified: those packs are untracked, 0 tracked files)

Report verified facts with file:line evidence: (1) every special-case site for "_core" (id, dir, branding, registry, validation, docs); (2) whether giving _core a pack.yaml changes discovery behavior anywhere (loader's underscore handling: quote it); (3) what "reserved id" means in the schema today — can a user pack declare id: _core? (4) the branding path in each harness (what would need to keep working if _core becomes manifest-backed); (5) how installed-wheel discovery would find _core. Suggest the narrowest reserved-id rule (schema + validator + tests). Ranked findings, <300 words.
