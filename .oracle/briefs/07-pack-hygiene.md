# Explore: pack-layout hygiene + validation

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle

Explore the pack tree hygiene surface in depth. Start from:
- astrid/packs/ top-level listing: every dir and file. Known items: _core/ (manifest-less, skill only), external/ (empty placeholder), local/ (gitignored scratch pack — check .gitignore + how loader creates it, ensure_local_pack_for_elements), builtin/ (status: deprecated? visibility?), __pycache__ dirs
- astrid/packs/blender/ root: server/, renders/, render_core.py, deploy.py, mesh_fetch.py, __init__.py, README.md, executors/
- astrid/packs/editorial/hype/ (arrangement_rules.py, enriched_arrangement.py, text_match.py) + who imports it (video_editing pack? tests? docs/architecture/repo-shape.md §4)
- astrid/core/pack/validate_layout.py (_CANONICAL_PACK_ROOT_DIRS incl. golden/fixtures at ~156), validate_first_party.py (_FIRST_PARTY_PACK_IDS missing blender/discord_local/seedance_local; _FIRST_PARTY_INTERNAL_DIRS)
- golden/ + fixtures/ dirs across packs (builtin, text_analysis, generation executors) — are they in layout allowlist?
- Foreign root dirs at repo root: ideogram-competition/, fal-voice-upscale/, mgt-evkinds-nhi8a13v/, pipeline-tests-_nahkzb4/, avatars/, runs/ — tracked or gitignored?

Report verified facts with file:line evidence: (1) complete hygiene inventory: each item → verdict (fold into executor / declare layout exception / delete / gitignore) with the validation rule it violates or satisfies; (2) does `packs validate` / validate_first_party currently pass or fail on main (list the errors); (3) what happens to the local/ pack if legacy_workspace element source dies (is local pack creation tied to it?); (4) examples/packs exclusion mechanism (how discover_packs skips it — which line). Suggested cleanup list ordered by risk. Ranked findings, <300 words.
