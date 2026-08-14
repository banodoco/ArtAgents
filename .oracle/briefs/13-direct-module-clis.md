# Explore: direct module CLIs / alternate entrypoints

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle

Search for undiscovered alternate entrypoints into pack or core code that bypass the gateway/pack registry. Start from:
- grep for `if __name__ == "__main__"` / `if __name__ == '__main__'` across astrid/ (especially astrid/packs/* and astrid/core/integrations/*)
- grep for `python -m astrid.packs` references in docs/, scripts/, .github/workflows/, STAGE.md files
- Known candidates: astrid/packs/blender/deploy.py (30KB — standalone?), astrid/packs/blender/mesh_fetch.py, astrid/packs/rendering/run.py (raw-command launcher?), astrid/packs/editorial/hype/*, any pack executor run.py with main() guards
- astrid/core/gateway/help.py entrypoint listing (what it advertises as runnable)
- Entry points: pyproject.toml [project.scripts] (astrid console script target), astrid.egg-info/entry_points.txt
- scripts/ references to python -m astrid or astrid.packs (gen_effect_registry.py, gen_remotion_types.py, build_2rp_*.py, reshape/)

Report verified facts with file:line evidence: (1) complete list of `__main__` guards and `python -m` runnable modules inside astrid/ (path + what it does + who uses it); (2) which are pack-owned support entrypoints that should become executors or be documented (blender deploy/mesh_fetch), which are legitimate host entrypoints; (3) the console-script surface (entry_points) vs the gateway; (4) anything a wheel user could run that bypasses packs entirely. Ranked findings, <300 words.
