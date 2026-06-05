# Runtime Correctness M3 Inventory

Generated inventory of non-pack `astrid/` Python `except` and runtime `assert` sites.

## Summary

- AST sites inventoried: 658 (656 `except`, 2 `assert`).
- Grep lexical hits after the same source exclusions: 669.
- AST sites not present as direct grep hits: 0. These are parser-normalized multi-line handlers/asserts or sites whose keyword line differs from the AST node line; AST remains authoritative.

## Seed-File Non-Fixed Reasons

- `astrid/gateway.py`: Seed inventory row. Non-fixed AST sites in this file: 19. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/core/task/run_audit.py`: Seed inventory row. Non-fixed AST sites in this file: 21. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/orchestrate/cli.py`: Seed inventory row. Non-fixed AST sites in this file: 12. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/threads/provenance.py`: Seed inventory row. Non-fixed AST sites in this file: 4. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/skills/__init__.py`: Seed inventory row. Non-fixed AST sites in this file: 3. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/skills/discovery.py`: Seed inventory row. Non-fixed AST sites in this file: 3. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/skills/harnesses/base.py`: Seed inventory row. Non-fixed AST sites in this file: 2. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/audit/context.py`: Seed inventory row. Non-fixed AST sites in this file: 2. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/core/session/binding.py`: Seed inventory row. Non-fixed AST sites in this file: 4. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/core/session/cli.py`: Seed inventory row. Non-fixed AST sites in this file: 18. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/core/task/gate.py`: Seed inventory row. Non-fixed AST sites in this file: 5. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.

## Deferred Tickets

- M3-INV-001: Follow up on deferred runtime correctness inventory rows after the split milestones settle.

## Planned Runtime Assert Conversions Completed

- `astrid/core/executor/install.py:239`: completed
- `astrid/core/executor/install.py:245`: completed
- `astrid/core/runpod/sweeper.py:149`: completed
- `astrid/core/session/cli.py:711`: completed

## Inventory

### `astrid/audit/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 41 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/audit/context.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 52 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 56 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/audit/transport.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 58 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 95 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 160 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/audit/util.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/contracts/capability_runner.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 116 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 126 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 141 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 144 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/contracts/run_status.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 119 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 136 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 150 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 168 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/adapter/local.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 47 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 61 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 86 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 93 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 97 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 115 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 158 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/adapter/manual.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 114 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/adapter/remote_artifact.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 33 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 89 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 148 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 154 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 157 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 170 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/alias_resolver.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 71 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/dirty.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 37 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 91 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 116 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/element/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 49 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/element/registry.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 93 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 282 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 297 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/element/schema.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 263 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 294 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/banodoco_catalog.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 69 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 73 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 61 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/folder.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 104 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 115 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/install.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 170 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/registry.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 367 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/runner.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 187 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 532 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 545 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/schema.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 284 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 286 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 290 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 297 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 801 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 804 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/generation/backends/base.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 34 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 41 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 60 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/generation/backends/fal.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 143 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 298 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/generation/backends/registry.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 103 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 201 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/generation/verbs.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 49 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 109 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/git_util.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 49 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 51 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 75 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 77 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 132 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 134 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/manifest.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 30 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 37 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 45 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/model_catalog/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 72 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 91 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 190 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 199 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/model_catalog/registry.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 51 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 184 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/model_catalog/schema.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 318 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/orchestrator/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 64 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/orchestrator/folder.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 66 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 94 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 105 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/orchestrator/registry.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 324 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 338 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 456 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/orchestrator/runner.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 178 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 263 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 270 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 272 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 362 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 373 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 454 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/orchestrator/schema.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 173 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 177 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/override.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 87 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 324 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1035 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1040 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1051 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1053 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack_resolver.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 23 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 66 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 70 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack_store.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 34 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 128 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 178 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 213 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 235 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 261 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 310 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 314 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 406 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 422 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 426 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 428 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 65 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 67 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 431 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 465 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 574 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 681 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 700 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 763 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 873 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 913 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/current_run.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 53 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 117 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/jsonio.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 29 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 31 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 33 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 44 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/run.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 300 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 327 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 482 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 568 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 579 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 631 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 641 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/schema.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 254 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 301 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 359 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/sidecar.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 45 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/reigh/data_provider.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 336 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/reigh/supabase_client.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 70 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 77 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 86 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 108 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 115 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 124 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/reigh/task_client.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 79 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 81 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 118 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/reigh/timeline_io.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 216 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 287 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 312 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/reigh/worker_jwt.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 61 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 72 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 87 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 126 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/runpod/sweeper.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 60 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 77 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 101 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 149 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 215 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 263 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 293 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 316 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 352 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 376 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/runtime/in_process.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 136 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 168 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 215 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 217 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/runtime/log_capture.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 55 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 177 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/scaffold.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 126 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/binding.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 152 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 185 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 192 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 197 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 190 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 252 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 258 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 269 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 307 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 413 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 525 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 593 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 633 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 643 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 674 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 689 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 738 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 755 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 804 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 833 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 925 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 968 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/config.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 28 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/identity.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 49 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 83 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 90 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/lease.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 89 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 94 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 98 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 327 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 332 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 336 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/lifecycle.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 299 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/model.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 84 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 121 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 125 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 139 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/claim.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 236 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 242 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 272 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 297 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 303 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 333 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/command_render.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 135 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/events.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 185 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 187 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 250 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 294 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 296 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 310 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 334 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 336 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 338 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 886 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 917 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 919 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 923 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 943 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/gate.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 581 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 954 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1082 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1379 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1449 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/gate_attestation.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 66 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 77 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 107 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/gate_repeat.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 103 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 209 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/hook.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 49 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 55 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 65 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 71 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/inbox.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 274 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 301 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 310 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 431 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 568 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 599 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/lifecycle_ack.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 153 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 168 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 215 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 256 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 331 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 356 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 385 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 435 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/lifecycle_skip.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 96 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 111 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 194 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 200 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 206 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/operator_view.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 163 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 168 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 306 | `assert` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 403 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 702 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 748 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 779 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 824 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 866 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1193 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1200 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/orchestrator_resolver.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 83 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 113 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 126 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/plan.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 327 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 422 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 532 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 534 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 536 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 911 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/plan_builder.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 263 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 268 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 273 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 287 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 320 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 355 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 362 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 382 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 394 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 435 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/plan_verbs.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 415 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 418 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 458 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 494 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 523 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 575 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/run_audit.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 37 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 42 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 175 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 180 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 231 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 252 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 263 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 306 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 311 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 372 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 377 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 459 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 464 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 545 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 550 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 576 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 581 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 633 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 645 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 702 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 822 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/run_gc.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 109 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 147 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 163 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 218 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 225 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 300 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/run_store.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 96 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 113 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 118 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 136 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 192 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 216 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 222 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 277 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/session_discovery.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 28 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 70 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 152 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 167 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 182 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/validator.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 73 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 82 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 101 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 158 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 177 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/_edit_helpers.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 127 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 129 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/banodoco_schema.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 46 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 538 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 611 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/branch.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 166 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 168 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 296 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 377 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 61 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 63 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 65 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 67 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1113 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1413 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1679 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2151 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2216 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2232 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2304 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2312 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2354 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2380 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2389 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2397 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2496 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2511 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2526 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2561 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2632 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2673 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2715 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2749 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2788 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2852 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2861 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2912 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2948 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2986 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 3020 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 3066 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 3100 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 3140 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 3179 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 3209 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/crud.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 15 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 176 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 186 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 627 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/erasure.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 321 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 338 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 340 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/eventlog/local_fs.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 126 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 166 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 188 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 244 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 270 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 275 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 288 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 324 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 326 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 344 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 401 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 403 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 405 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 450 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/eventlog/selector.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 372 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/eventlog/supabase.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 225 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/events/schema/types.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 124 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 342 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 845 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1057 | `assert` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/integrity.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 59 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/inverses.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 828 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 945 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/migration.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 166 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 176 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 394 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 470 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 561 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/model.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 25 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 32 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 39 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 47 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/observability.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 97 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 148 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 159 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 188 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 202 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/operations.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 283 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 404 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/paths.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 108 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 122 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 142 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 170 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 176 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 212 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 227 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 265 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 269 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 289 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 295 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 297 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 305 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 309 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 315 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/projection.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 169 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 260 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 726 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 980 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/repair.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 158 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 193 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 195 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 243 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 289 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 300 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/transfer.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 287 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 289 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 302 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/undo.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 193 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 285 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 307 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 343 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 366 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/update.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 57 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/util/atomic_io.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 28 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 92 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 104 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 126 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 140 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 142 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 144 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/util/http.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 127 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 134 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 191 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 200 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/util/log_and_swallow.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 45 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/util/png_metadata.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 55 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 92 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 102 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/worker/banodoco_worker.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 319 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 348 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 375 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 391 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 410 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 423 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 452 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 508 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/doctor.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 127 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 412 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 449 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 688 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 690 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 692 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/domains/hype/enriched_arrangement.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 95 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 303 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/gateway.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 126 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 128 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 157 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 193 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 226 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 323 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 551 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 645 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 780 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 801 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 819 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 838 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 884 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 887 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 890 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 894 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 936 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1044 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1082 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/modalities/__init__.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/orchestrate/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 112 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 119 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 130 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 216 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 228 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 287 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 331 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 340 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 366 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 474 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 499 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 584 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/orchestrate/compile.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 71 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/orchestrate/dsl.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 184 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 191 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 506 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/orchestrate/test_runner.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 139 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 244 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/sdk.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 565 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 613 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 719 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 808 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 810 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 834 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 836 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 854 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 856 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1302 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1323 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1348 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1377 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1393 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1408 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1436 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1440 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1451 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1743 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1745 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/__init__.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 343 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 413 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 426 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 32 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/discovery.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 69 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 103 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 175 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/harnesses/base.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 73 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 141 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/harnesses/claude.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/harnesses/codex.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 95 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 113 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/harnesses/hermes.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 109 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 129 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 150 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 154 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 161 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/state.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 48 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/structure.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 96 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 99 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 170 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 181 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 249 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 279 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 330 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 336 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 363 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 426 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 501 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 545 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/theme_schema.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 204 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 206 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/threads/attribute.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 144 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 228 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 279 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 285 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 299 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 367 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 375 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 390 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 396 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 398 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 420 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/threads/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 118 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 209 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 214 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/threads/index.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 77 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 91 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 96 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 131 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 141 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/threads/provenance.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 45 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 56 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 116 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 141 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/threads/record.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 193 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 211 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 227 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 257 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 324 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/threads/schema.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 215 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/threads/variants.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 40 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 51 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 168 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 196 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 242 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 270 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 364 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 377 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/utilities/llm_clients.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 75 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 77 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 131 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 277 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 375 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 395 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/verify/checks.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 89 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 91 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 95 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 108 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 110 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 112 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 175 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 283 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 291 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 293 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 295 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 297 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 323 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 325 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 368 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
