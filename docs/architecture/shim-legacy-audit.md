# Retired Shim and Legacy Surface Audit

This document records the current no-shim state of the Astrid checkout. It is
the live architecture audit, not a historical milestone brief.

## Rule

Astrid has no live Python compatibility shim modules. Canonical imports are the
only supported imports inside the repo. Historical megaplan briefs may describe
earlier migration stages, but live source, tests, and architecture docs should
not preserve compatibility import surfaces.

## Retired Python Shim Surfaces

| Retired surface | Canonical surface |
| --- | --- |
| `astrid._media` | `astrid.media` |
| `astrid._paths` | `astrid.paths` |
| `astrid.pipeline` | `astrid.gateway` |
| `astrid.timeline` and timeline re-export modules | `astrid.core.timeline` |
| `astrid.core._search` | `astrid.core.search` |
| `astrid.core.pack_machinery.*` | `astrid.core.pack.*` |
| `astrid.core.pack_discovery` | `astrid.core.pack.discovery` |
| `astrid.core.pack_resolver` | `astrid.core.pack.resolver` |
| `astrid.core.pack_store` | `astrid.core.pack.store` |
| `astrid.core.manifest` | `astrid.core.pack.manifest` |
| `astrid.core.alias_resolver` | `astrid.core.pack.alias_resolver` |
| `astrid.packs.{cli,validate,agent_index,gitignore,install,_canonical_entrypoint}` | `astrid.core.pack.*` |
| `astrid.sdk_*`, `astrid.sdk_results` | `astrid.sdk.*` |

## Remaining Legacy Concepts

These names may still contain the word `legacy`, but they are not Python import
compatibility shims:

| Surface | Status |
| --- | --- |
| `LEGACY_PUBLIC_DIRS` / `LEGACY_LOCAL_DIRS` | Permanent structure guardrails rejecting old directory names. |
| `_LEGACY_RUN_RECORD_STATUS_TOKENS` | Validator token list used to prevent old run statuses from being written. |
| Deprecated CLI aliases such as `astrid run` and `astrid author` | CLI behavior, not Python module compatibility. Remove through a separate CLI deprecation decision. |
| Historical megaplan docs | Archival planning records; they may mention shims that no longer exist. |
| Synthetic shim fixtures in `tests/test_structure_contracts.py` | Detector tests proving new compatibility shims are rejected. |

## Enforcement

`astrid/structure.py` owns the live guardrails:

- `validate_repo_structure()` rejects unexpected top-level files and generated debris.
- `_validate_packs_top_level_modules()` allows only `astrid/packs/__init__.py`.
- `validate_migration_completion()` scans for deprecated markers, `sys.modules`
  injection, dangling alias `__all__` patterns, and compatibility shim text with
  live callers.

The current expected result is zero live compatibility shim modules and zero
compatibility-shim exemptions.
