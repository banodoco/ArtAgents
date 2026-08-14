# Explore: discovery load graph

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle

Explore the pack/skill/element discovery load graph in depth. Start from:
- astrid/core/pack/discovery.py (discover_pack_metadata, discover_packs_ordered, layers: source tree, project local pack, extra roots, ASTRID_PACKS_PATH, installed)
- astrid/core/pack/loader.py, validate_layout.py (canonical dirs, INTERNAL_PACK_DIRS, underscore-prefix skip), validate.py
- astrid/skills/discovery.py (flat-walk fallback for manifest-less dirs; lines ~130-205; pack_dir.name fallback) + astrid/skills/harnesses/{claude,codex,hermes}.py (_core special-case → symlink name "astrid")
- astrid/core/element/registry.py default_sources() (~281-291: active_theme dirs) and astrid/core/element/catalog.py (~91-98: legacy_workspace, WORKSPACE_ROOT = REPO_ROOT.parent, priority 15)
- astrid/core/pack/validate_first_party.py (_FIRST_PARTY_PACK_IDS, _FIRST_PARTY_INTERNAL_DIRS = {"_core"})
- astrid/core/structure.py _child_dirs / underscore handling; astrid/core/pack/store.py installed packs

Report verified facts with file:line evidence: (1) every seam where non-pack content enters a registry or skill listing; (2) exact behavior if _core/ gets a pack.yaml (would discover_packs enumerate it? would skills keep the flat-walk? what breaks); (3) exact behavior if legacy_workspace and active-theme element sources are removed — who loads theme elements today, where do theme dirs live, what priority do they have; (4) alias resolution path (aliases in pack.yaml, builtin aliases); (5) hidden/deprecated pack handling. Unknowns and risks: what in-progress local skills or theme elements would disappear. Suggested approach for "one load graph" (packs/skills/elements all resolve via discover_pack_metadata). Ranked findings, <300 words.
