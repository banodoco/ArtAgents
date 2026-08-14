# Explore: wheel contents (what must ship)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle

Explore what non-Python runtime data the wheel must ship so installed-wheel discovery works for every capability kind. Start from:
- pyproject.toml (packages, package-data, include-package-data; current rendering-only package-data declaration — quote it)
- astrid.egg-info/SOURCES.txt (what is currently included; compare vs astrid/packs content)
- astrid/core/pack/discovery.py (installed-pack layer: where does the wheel's pack tree come from — site-packages/astrid/packs? ASTRID_PACKS_PATH?), store.py (InstalledPackStore — ~/.astrid/packs, revisions, install.json)
- Which files manifests reference at runtime: pack.yaml, executor.yaml/orchestrator.yaml/element.yaml, skill/SKILL.md, STAGE.md, extension descriptors (extensions.rendering backends/planners/finalizers), rendering/ element manifests, model catalogs (model_catalog/models.yaml, loras.yaml)
- scripts/smoke_wheel_install.sh (what it currently verifies — quote the checks)
- tests: tests/test_wheel_*.py or packaging tests if any (grep tests/ for 'wheel')

Report verified facts with file:line evidence: (1) current package-data coverage — which manifest types ship today, which do not; (2) whether installed-wheel discovery of packs works at all today (does the installed layer read site-packages/astrid/packs or ~/.astrid/packs?) — quote the discovery code; (3) the exact set of patterns a corrected package-data block needs (pack.yaml, *executor.yaml, *orchestrator.yaml, *element.yaml, SKILL.md, STAGE.md, extension roots, model catalogs); (4) what smoke_wheel_install.sh misses today. Suggest the explicit include list (no blanket recursive junk) + smoke script extensions. Ranked findings, <300 words.
