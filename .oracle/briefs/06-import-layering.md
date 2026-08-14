# Explore: import-layering legality of each planned move

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle

Explore the import-layering rules and whether each planned extraction keeps them green. Start from:
- astrid/core/structure.py (validate_import_layering ~547-570, TOP_LEVEL_ASTRID_FILES, INTERNAL_PACK_DIRS, _child_dirs underscore skip)
- astrid/core/foundation/paths.py (REPO_ROOT, WORKSPACE_ROOT)
- docs/architecture/import-tiers.md (tiers 0-5; integrations same tier as timeline/session/project?)
- The planned moves to test for legality: (a) generation backends fal/vibecomfy/codex.py → packs/generation; (b) core/experiments/ → packs/iteration; (c) core/integrations/runpod → packs/runpod; (d) core/integrations/reigh (+ worker?) → packs/reigh; (e) skills flat-walk removal; (f) _core pack.yaml; (g) legacy_workspace removal
- For each: which core modules currently import the code being moved (grep importers), which packs import core (packs may import core — check the reverse rule), what stub/adapter would remain in core (e.g. a protocol class or a thin factory), and whether a core→packs import would be introduced illegally (the one sanctioned bridge: astrid/core/runtime/in_process.py)
- astrid/core/runtime/in_process.py: what it is, why it is the only legal core→packs import

Report verified facts with file:line evidence: (1) the exact rule text/logic of validate_import_layering (what is forbidden, what is sanctioned); (2) per planned move (a)-(g): legal today / legal with stub X / illegal-as-is, with the violating import edge if any; (3) whether extraction can proceed with zero exemptions or whether structure.py must grow a new sanctioned bridge (and what it should look like). Ranked findings, <300 words.
