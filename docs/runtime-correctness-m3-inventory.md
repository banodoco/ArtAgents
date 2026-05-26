# Runtime Correctness M3 Inventory

Generated inventory of non-pack `astrid/` Python `except` and runtime `assert` sites.

## Summary

- AST sites inventoried: 570 (568 `except`, 2 `assert`).
- Grep lexical hits after the same source exclusions: 580.
- AST sites not present as direct grep hits: 0. These are parser-normalized multi-line handlers/asserts or sites whose keyword line differs from the AST node line; AST remains authoritative.

## Seed-File Non-Fixed Reasons

- `astrid/pipeline.py`: Seed inventory row. Non-fixed AST sites in this file: 12. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/core/task/run_audit.py`: Seed inventory row. Non-fixed AST sites in this file: 20. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/orchestrate/cli.py`: Seed inventory row. Non-fixed AST sites in this file: 12. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/threads/provenance.py`: Seed inventory row. Non-fixed AST sites in this file: 4. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/skills/__init__.py`: Seed inventory row. Non-fixed AST sites in this file: 2. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/skills/discovery.py`: Seed inventory row. Non-fixed AST sites in this file: 3. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/skills/harnesses/base.py`: Seed inventory row. Non-fixed AST sites in this file: 2. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/audit/context.py`: Seed inventory row. Non-fixed AST sites in this file: 2. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/core/session/binding.py`: Seed inventory row. Non-fixed AST sites in this file: 4. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/core/session/cli.py`: Seed inventory row. Non-fixed AST sites in this file: 19. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/core/task/gate.py`: Seed inventory row. Non-fixed AST sites in this file: 10. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.

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
| 32 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 73 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 88 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 147 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 153 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 156 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 169 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/alias_resolver.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 71 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/dirty.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 38 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 92 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 117 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/element/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 42 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/element/registry.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 85 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 293 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/element/schema.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 241 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/banodoco_catalog.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 69 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 73 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 50 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 296 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/folder.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 73 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 102 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 113 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/install.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 170 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/registry.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 398 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/runner.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 120 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 130 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/schema.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 287 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 289 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 293 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 300 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 918 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 921 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/generation/backends/fal.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 57 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 83 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 155 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 260 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/generation/backends/vibecomfy.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 175 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 181 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 204 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 262 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/git_util.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 50 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 52 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 76 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 78 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 133 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 135 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/manifest.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 30 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 37 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 45 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/model_catalog/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 71 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 90 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 186 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 192 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/model_catalog/registry.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 40 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/orchestrator/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 52 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/orchestrator/folder.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 65 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 92 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 103 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/orchestrator/registry.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 323 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 337 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 490 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/orchestrator/runner.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 139 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 146 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 196 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 203 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 205 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/orchestrator/runtime.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 117 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 161 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/orchestrator/schema.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 170 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 174 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/override.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 88 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 365 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 370 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 381 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 383 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack_resolver.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 23 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 66 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 70 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack_store.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 36 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 125 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 175 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 210 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 232 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 258 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 307 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 311 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 403 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 419 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 423 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 425 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 63 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 423 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 457 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 566 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 657 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 676 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 844 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/current_run.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 53 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 117 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/jsonio.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 21 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 23 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 25 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 52 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/run.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 211 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 349 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/schema.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 262 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 301 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/sidecar.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 45 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/reigh/data_provider.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 335 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/reigh/supabase_client.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 71 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 78 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 87 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 109 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 116 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 125 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

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
| 52 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 69 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 93 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 141 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 236 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 266 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 289 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 325 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 349 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/binding.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 88 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 121 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 128 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 133 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 114 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 183 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 218 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 257 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 264 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 273 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 308 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 345 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 406 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 588 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 630 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 642 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 653 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 712 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 727 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 747 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 771 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 864 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 906 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

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
| 77 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 82 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 86 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 275 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 280 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 284 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/model.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 72 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/active_run.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 83 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 136 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/claim.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 203 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 226 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 246 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 269 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/command_render.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 135 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/events.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 184 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 186 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 249 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 293 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 295 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 309 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 333 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 335 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 337 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 979 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1010 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1012 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1016 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1036 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/gate.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 1003 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1172 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1326 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1699 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1827 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1928 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1939 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1969 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2254 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2417 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

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
| 165 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 180 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 227 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 268 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 343 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 368 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 397 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 447 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

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
| 160 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 165 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 303 | `assert` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 405 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 651 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 695 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 712 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 744 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 773 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1006 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1013 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/orchestrator_resolver.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 82 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 112 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 125 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/plan.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 328 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 423 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 533 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 535 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 537 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 912 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

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
| 414 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 417 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 457 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 493 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 522 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 574 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/run_audit.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 36 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 41 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 86 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 178 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 183 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 234 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 255 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 266 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 309 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 314 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 375 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 380 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 459 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 464 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 545 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 550 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 576 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 581 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 679 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 799 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/run_store.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 94 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 111 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 116 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 134 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 209 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 215 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 253 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/session_discovery.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 28 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 70 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 152 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 167 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/validator.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 83 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 102 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 159 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 178 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/_edit_helpers.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 124 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 126 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/assembly_helper.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 146 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 148 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 164 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 182 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/branch.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 167 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 169 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 297 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 378 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 53 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 56 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 59 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 62 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1095 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1386 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1652 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2118 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2180 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2196 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2265 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2270 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2309 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2332 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2341 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2349 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2448 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2460 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2472 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2507 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2575 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2613 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2652 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2680 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2717 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2775 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2781 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2829 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2867 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2902 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2933 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 2974 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 3005 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 3042 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 3078 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 3105 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/crud.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 169 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 179 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 604 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/erasure.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 323 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 340 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 342 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/eventlog/local_fs.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 75 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 127 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 167 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 189 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 246 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 272 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 277 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 290 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 326 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 328 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 346 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 403 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 405 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 407 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 452 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/eventlog/selector.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 375 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/eventlog/supabase.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 226 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/events/schema/types.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 107 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 325 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 815 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 1027 | `assert` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/integrity.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 59 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/inverses.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 830 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 947 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/migration.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 166 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 176 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 391 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 467 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 558 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

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
| 98 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 149 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 160 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 189 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 203 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/operations.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 281 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 402 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

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
| 294 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 302 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 306 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 312 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/projection.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 239 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 705 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 959 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/repair.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 159 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 194 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 196 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 244 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 289 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 300 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/transfer.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 286 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 288 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 301 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/undo.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 200 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 292 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 314 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 350 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 373 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/update.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 58 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/util/http.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 127 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 134 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 191 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 200 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/worker/banodoco_worker.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 189 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 320 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 349 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 376 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 392 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 412 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 441 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 497 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/doctor.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 126 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 405 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/domains/hype/enriched_arrangement.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 94 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 302 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/modalities/__init__.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 75 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/orchestrate/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 116 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 123 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 135 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 223 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 235 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 293 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 337 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 347 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 374 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 483 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 509 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 594 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/orchestrate/compile.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 70 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/orchestrate/dsl.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 184 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 191 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 506 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/orchestrate/test_runner.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 138 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 238 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/pipeline.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 111 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 143 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 169 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 265 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 476 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 615 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 633 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 648 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 667 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 710 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 713 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 716 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 720 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 763 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 806 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/__init__.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 241 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 311 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 27 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/discovery.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 70 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 101 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 141 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/harnesses/base.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 73 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 94 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/harnesses/claude.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/harnesses/codex.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 97 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 115 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/harnesses/hermes.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 110 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 130 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 151 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 155 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 162 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/state.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 48 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/structure.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 87 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 90 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 138 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 149 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 215 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 245 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 318 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 369 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 444 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/theme_schema.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 204 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 206 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/threads/attribute.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 142 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 226 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 277 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 291 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 359 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 367 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 382 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 388 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 390 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 412 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/threads/cli.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 104 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 195 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

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
| 190 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 208 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 224 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 254 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 321 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/threads/variants.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 38 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 49 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 166 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 195 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 241 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 269 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 363 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 376 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/timeline/timeline_model.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 44 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 530 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 603 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/utilities/llm_clients.py`

| line | kind | owner | status | reason |
| --- | --- | --- | --- | --- |
| 76 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 78 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 132 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 278 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 376 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |
| 396 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after m5b split; behavior unchanged and reviewed as non-pack runtime surface. |

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
