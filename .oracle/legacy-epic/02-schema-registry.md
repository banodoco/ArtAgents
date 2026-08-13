# Explore: manifest schema and registry semantics

Project root: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only exploration. Do NOT edit files.

## What to establish

1. `astrid/core/pack/schemas/v1/pack.json` (JSON Schema) vs the manual
   normalizer `astrid/core/pack/_common.py` (or wherever pack.yaml is
   normalized): are they kept in sync? Which fields does pack.yaml support
   today (id, version, content roots, aliases, permissions)? How are aliases
   declared and resolved (`pack/alias_resolver.py`)?
2. `astrid/core/registry/base.py` — the CapabilityRegistry API: how
   capabilities are registered, looked up, and how conflicts are reported.
   What is the `kind` dimension (executor/orchestrator/element) and how would
   a new kind (renderer) fit?
3. `astrid/core/execution/executor/registry.py` — the executor registry:
   does it use CapabilityRegistry? How do aliases and overrides
   (`pack/override.py`, OverrideStore) interact with it? The epic brief
   warns the default executor registry currently OMITS the override store —
   verify that claim and show where.
4. How override administration works today (`executor override set` CLI) —
   which module, what store file, what precedence semantics (from → to)?

## Report format

Ranked findings with file:line evidence. Max 300 words. End with:
- Verified facts
- Unknowns
- Risks for registering renderer/planner/finalizer capabilities
- Suggested approach (2-3 sentences)
