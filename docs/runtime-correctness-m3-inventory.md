# Runtime Correctness M3 Except/Assert Inventory

Generated from Python AST over non-pack source under `astrid/`, excluding `astrid/packs/**`, hidden runtime state such as `astrid/.astrid/**`, and non-Python files. The secondary grep command was used only as a lexical cross-check:

```bash
rg -n '\bexcept\b|\bassert\b' astrid --glob '!astrid/packs/**'
```

## Summary

- AST sites inventoried: 567 (565 `except`, 2 `assert`).
- Status counts: deferred=24, fixed=0, justified=437, justified-with-caveat=106
- Allowed statuses: `fixed`, `justified`, `justified-with-caveat`, `deferred`.
- `fixed` now means the approved M3 runtime assert conversions have been applied in code; no current AST row remains marked fixed.

## Secondary Grep Cross-Check

- Grep lexical hits after the same source exclusions: 577.
- AST sites not present as direct grep hits: 0. These are parser-normalized multi-line handlers/asserts or sites whose keyword line differs from the AST node line; AST remains authoritative.
- Grep-only hits: 10. These are comments, docstrings, or non-runtime text references and are not executable sites.

| grep-only location | text | triage |
| --- | --- | --- |
| `astrid/core/executor/cli.py:520` | `# TODO: assert on expected behavior` | justified: non-executable text/comment/docstring reference |
| `astrid/core/executor/cli.py:521` | `assert result.returncode == 0, f"dry-run failed: {result.stderr}"` | justified: non-executable text/comment/docstring reference |
| `astrid/core/executor/folder.py:222` | `except TypeError:` | justified: non-executable text/comment/docstring reference |
| `astrid/core/executor/folder.py:259` | `except Exception:` | justified: non-executable text/comment/docstring reference |
| `astrid/core/orchestrator/folder.py:200` | `except TypeError:` | justified: non-executable text/comment/docstring reference |
| `astrid/core/orchestrator/folder.py:237` | `except Exception:` | justified: non-executable text/comment/docstring reference |
| `astrid/core/session/binding.py:31` | `# directly; spike tests assert env-inheritance specifically):` | justified: non-executable text/comment/docstring reference |
| `astrid/core/session/cli.py:64` | `# Tests assert on these literal strings; keep them stable.` | justified: non-executable text/comment/docstring reference |
| `astrid/core/timeline/_edit_helpers.py:63` | `via a single ``except TimelineEditError`` clause.` | justified: non-executable text/comment/docstring reference |
| `astrid/core/timeline/erasure.py:183` | `Never mutates — always read-only.  Callers should assert preview is` | justified: non-executable text/comment/docstring reference |

## Seed-File Non-Fixed Reasons
- `astrid/pipeline.py`: Seed CLI gateway/recovery path; narrow catches surface gate/session errors, but silent nudge/interrupt cleanup sites are deferred for explicit handling. Non-fixed AST sites in this file: 12.
- `astrid/core/task/run_audit.py`: Seed audit path; command wrappers intentionally capture SystemExit/Exception for report entries, but interactive KeyboardInterrupt swallowing is deferred. Non-fixed AST sites in this file: 20.
- `astrid/orchestrate/cli.py`: Seed orchestration CLI; domain errors are surfaced, cleanup OSError is best effort, broad explanation failure is deferred. Non-fixed AST sites in this file: 12.
- `astrid/threads/provenance.py`: Seed thread metadata reader; tolerant metadata degradation avoids breaking provenance display on corrupt sidecars, with broad default labeled caveated. Non-fixed AST sites in this file: 4.
- `astrid/skills/__init__.py`: Seed skills installer; broad filesystem/probe failures currently degrade optional harness state and need narrower follow-up. Non-fixed AST sites in this file: 2.
- `astrid/skills/discovery.py`: Seed skills discovery; malformed optional pack skill metadata is skipped so one bad pack does not break discovery, with broad skips caveated. Non-fixed AST sites in this file: 3.
- `astrid/skills/harnesses/base.py`: Seed harness probing; broad probe failure returns no harness to keep optional integrations non-fatal, with narrower logging deferred. Non-fixed AST sites in this file: 2.
- `astrid/audit/context.py`: Seed audit context; cwd/output path failures use bounded fallback values for report generation. Non-fixed AST sites in this file: 2.
- `astrid/core/session/binding.py`: Seed session binding; validation errors are wrapped, while auto-resolve/corrupt-file broad fallbacks are deferred. Non-fixed AST sites in this file: 4.
- `astrid/core/session/cli.py`: Seed session CLI; user-facing domain errors return messages, status display skips corrupt optional rows with caveat, and planned runtime assert conversion is now explicit CLI error handling. Non-fixed AST sites in this file: 19.
- `astrid/core/task/gate.py`: Seed task gate; explicit gate errors surface, benign parse fallbacks stay justified, and for_each parent builders now warn on narrow plan/event replay failures. Non-fixed AST sites in this file: 10.

## Deferred Tickets
- `M3-INV-025: log child fork inspection failures.` Site: `astrid/core/orchestrator/registry.py:323`.
- `M3-INV-026: log child fork inspection failures.` Site: `astrid/core/orchestrator/registry.py:337`.
- `M3-INV-021: log skipped run-id enumeration errors.` Site: `astrid/core/project/cli.py:566`.
- `M3-INV-022: log assembly repair errors.` Site: `astrid/core/project/cli.py:657`.
- `M3-INV-023: log skipped run summary errors.` Site: `astrid/core/project/cli.py:676`.
- `M3-INV-024: log project summary aggregation errors.` Site: `astrid/core/project/cli.py:844`.
- `M3-INV-005: narrow/log auto-resolve hook failures.` Site: `astrid/core/session/binding.py:87`.
- `M3-INV-006: distinguish corrupt session file from absent binding.` Site: `astrid/core/session/binding.py:120`.
- `M3-INV-007: narrow corrupt session display handling in status.` Site: `astrid/core/session/cli.py:121`.
- `M3-INV-008: log skipped corrupt timeline status rows.` Site: `astrid/core/session/cli.py:871`.
- `M3-INV-004: make audit follow interrupt return deterministic instead of pass.` Site: `astrid/core/task/run_audit.py:581`.
- `M3-INV-017: log schema detection fallback failures.` Site: `astrid/core/timeline/migration.py:189`.
- `M3-INV-018: log schema detection fallback failures.` Site: `astrid/core/timeline/migration.py:199`.
- `M3-INV-019: log checkpoint resolution failures.` Site: `astrid/core/timeline/migration.py:581`.
- `M3-INV-020: log checkpoint projection degradation.` Site: `astrid/core/timeline/projection.py:959`.
- `M3-INV-012: explain skipped invalid child orchestrator definitions in list/search.` Site: `astrid/orchestrate/cli.py:223`.
- `M3-INV-011: report plan explanation render failures.` Site: `astrid/orchestrate/cli.py:509`.
- `M3-INV-001: make agent-skill nudge failures telemetry-visible or narrowed.` Site: `astrid/pipeline.py:100`.
- `M3-INV-002: return/surface interrupted adapter wait instead of silent pass.` Site: `astrid/pipeline.py:659`.
- `M3-INV-003: log adapter cleanup kill failures.` Site: `astrid/pipeline.py:663`.
- `M3-INV-013: narrow filesystem record probe failure.` Site: `astrid/skills/__init__.py:241`.
- `M3-INV-014: log malformed skill metadata fallback.` Site: `astrid/skills/discovery.py:70`.
- `M3-INV-015: log skipped malformed pack skill descriptor.` Site: `astrid/skills/discovery.py:141`.
- `M3-INV-016: narrow optional harness probe failures.` Site: `astrid/skills/harnesses/base.py:73`.

## Planned Runtime Assert Conversions Completed

- `astrid/core/executor/install.py:239`: completed - approved M3 runtime-validation assert conversion now uses an explicit raise or CLI error path.
- `astrid/core/executor/install.py:245`: completed - approved M3 runtime-validation assert conversion now uses an explicit raise or CLI error path.
- `astrid/core/runpod/sweeper.py:149`: completed - approved M3 runtime-validation assert conversion now uses an explicit raise or CLI error path.
- `astrid/core/session/cli.py:711`: completed - approved M3 runtime-validation assert conversion now uses an explicit raise or CLI error path.

## Full AST Inventory

### `astrid/audit/cli.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 41 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/audit/context.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 52 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 56 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/audit/transport.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 58 | `except` | `(UnicodeDecodeError, json.JSONDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 95 | `except` | `AuditLedgerError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 160 | `except` | `(IndexError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/audit/util.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 74 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/adapter/local.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 47 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 61 | `except` | `(FileNotFoundError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 86 | `except` | `(json.JSONDecodeError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 93 | `except` | `ProcessLookupError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 97 | `except` | `PermissionError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 115 | `except` | `(OSError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 158 | `except` | `(json.JSONDecodeError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/adapter/manual.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 114 | `except` | `(json.JSONDecodeError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/adapter/remote_artifact.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 32 | `except` | `(OSError, json.JSONDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 73 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 88 | `except` | `(FileNotFoundError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 147 | `except` | `(TypeError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 153 | `except` | `ProcessLookupError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 156 | `except` | `PermissionError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 169 | `except` | `(OSError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/alias_resolver.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 71 | `except` | `AliasResolutionError` | `justified` | Narrow/domain catch with local recovery or wrapping. |

### `astrid/core/dirty.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 38 | `except` | `GitUtilError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 92 | `except` | `(json.JSONDecodeError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 117 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/element/cli.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 42 | `except` | `(KeyError, ElementRegistryError, ElementValidationError, ValueError, OverrideStoreError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/element/registry.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 85 | `except` | `KeyError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 293 | `except` | `ElementValidationError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/element/schema.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 241 | `except` | `ManifestParseError` | `justified` | Narrow/domain catch with local recovery or wrapping. |

### `astrid/core/executor/banodoco_catalog.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 69 | `except` | `urllib.error.URLError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 73 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/executor/cli.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 50 | `except` | `(KeyError, ExecutorValidationError, ProjectRunError, ValueError, OverrideStoreError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 296 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |

### `astrid/core/executor/folder.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 73 | `except` | `ExecutorValidationError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 102 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 113 | `except` | `ExecutorValidationError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/executor/install.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 170 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/executor/registry.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 398 | `except` | `ManifestParseError` | `justified` | Narrow/domain catch with local recovery or wrapping. |

### `astrid/core/executor/runner.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 120 | `except` | `task_gate.TaskRunGateError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 130 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |

### `astrid/core/executor/schema.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 287 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 289 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 293 | `except` | `ExecutorValidationError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 300 | `except` | `ManifestParseError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 918 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 921 | `except` | `KeyError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/generation/backends/fal.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 57 | `except` | `(ValueError, TypeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 83 | `except` | `(ValueError, TypeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 155 | `except` | `(ValueError, TypeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 260 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |

### `astrid/core/generation/backends/vibecomfy.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 175 | `except` | `(ValueError, TypeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 181 | `except` | `(ValueError, TypeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 204 | `except` | `(ValueError, TypeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 262 | `except` | `(ValueError, TypeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/git_util.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 50 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 52 | `except` | `subprocess.TimeoutExpired` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 76 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 78 | `except` | `subprocess.TimeoutExpired` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 133 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 135 | `except` | `subprocess.TimeoutExpired` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/manifest.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 30 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 37 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 45 | `except` | `yaml.YAMLError` | `justified` | Narrow/domain catch with local recovery or wrapping. |

### `astrid/core/model_catalog/cli.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 69 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 89 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 185 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 191 | `except` | `KeyError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/model_catalog/registry.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 40 | `except` | `KeyError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/orchestrator/cli.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 52 | `except` | `(KeyError, OrchestratorValidationError, ProjectRunError, ValueError, OverrideStoreError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/orchestrator/folder.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 65 | `except` | `OrchestratorValidationError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 92 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 103 | `except` | `OrchestratorValidationError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/orchestrator/registry.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 323 | `except` | `Exception` | `deferred` | M3-INV-025: log child fork inspection failures. |
| 337 | `except` | `Exception` | `deferred` | M3-INV-026: log child fork inspection failures. |
| 490 | `except` | `ManifestParseError` | `justified` | Narrow/domain catch with local recovery or wrapping. |

### `astrid/core/orchestrator/runner.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 139 | `except` | `task_gate.TaskRunGateError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 146 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 196 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 203 | `except` | `OrchestratorRunnerError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 205 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |

### `astrid/core/orchestrator/runtime.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 117 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 161 | `except` | `ImportError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/orchestrator/schema.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 170 | `except` | `ManifestParseError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 174 | `except` | `OrchestratorValidationError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/override.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 88 | `except` | `(json.JSONDecodeError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/pack.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 365 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 370 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 381 | `except` | `PackValidationError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 383 | `except` | `yaml.YAMLError` | `justified` | Narrow/domain catch with local recovery or wrapping. |

### `astrid/core/pack_resolver.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 23 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves import-context wrapping for resolver failures; caveat: it intentionally normalizes arbitrary import-time exceptions into PackResolverError. |
| 66 | `except` | `CallableNotFoundError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 70 | `except` | `PackResolverError` | `justified` | Narrow/domain catch with local recovery or wrapping. |

### `astrid/core/pack_store.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 36 | `except` | `ImportError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 125 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 175 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 210 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 232 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 258 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 307 | `except` | `(OSError, _json.JSONDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 311 | `except` | `(TypeError, Exception)` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 403 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 419 | `except` | `(OSError, _json.JSONDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 423 | `except` | `TypeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 425 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |

### `astrid/core/project/cli.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 63 | `except` | `(FileExistsError, FileNotFoundError, ProjectError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 423 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 457 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 566 | `except` | `Exception` | `deferred` | M3-INV-021: log skipped run-id enumeration errors. |
| 657 | `except` | `Exception` | `deferred` | M3-INV-022: log assembly repair errors. |
| 676 | `except` | `Exception` | `deferred` | M3-INV-023: log skipped run summary errors. |
| 844 | `except` | `Exception` | `deferred` | M3-INV-024: log project summary aggregation errors. |

### `astrid/core/project/current_run.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 53 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 117 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/project/jsonio.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 21 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 23 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 25 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 52 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/project/run.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 211 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 349 | `except` | `TimelineCrudError` | `justified` | Narrow/domain catch with local recovery or wrapping. |

### `astrid/core/project/schema.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 262 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 301 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/project/sidecar.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 45 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/reigh/data_provider.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 335 | `except` | `RuntimeError` | `justified` | Narrow/domain catch with local recovery or wrapping. |

### `astrid/core/reigh/supabase_client.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 71 | `except` | `urllib.error.HTTPError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 78 | `except` | `urllib.error.URLError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 87 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 109 | `except` | `urllib.error.HTTPError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 116 | `except` | `urllib.error.URLError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 125 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/reigh/task_client.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 79 | `except` | `urllib.error.HTTPError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 81 | `except` | `urllib.error.URLError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 118 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/reigh/timeline_io.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 216 | `except` | `SupabaseHTTPError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 287 | `except` | `SupabaseHTTPError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 312 | `except` | `SupabaseHTTPError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/reigh/worker_jwt.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 61 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 72 | `except` | `InvalidTokenError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 87 | `except` | `AttributeError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 126 | `except` | `InvalidTokenError` | `justified` | Narrow/domain catch with local recovery or wrapping. |

### `astrid/core/runpod/sweeper.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 52 | `except` | `(json.JSONDecodeError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 69 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 93 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 141 | `except` | `StaleTailError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 236 | `except` | `(ValueError, TypeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 266 | `except` | `LeaseError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 289 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 325 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 349 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |

### `astrid/core/session/binding.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 87 | `except` | `Exception` | `deferred` | M3-INV-005: narrow/log auto-resolve hook failures. |
| 120 | `except` | `Exception` | `deferred` | M3-INV-006: distinguish corrupt session file from absent binding. |
| 127 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 132 | `except` | `SessionValidationError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/session/cli.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 114 | `except` | `Exception` | `deferred` | M3-INV-007: narrow corrupt session display handling in status. |
| 183 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 218 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 257 | `except` | `IdentityError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 264 | `except` | `(ValueError, IdentityError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 273 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 308 | `except` | `ProjectError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 345 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 406 | `except` | `(EOFError, KeyboardInterrupt)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 588 | `except` | `(IdentityError, ProjectError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 630 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 642 | `except` | `SessionBindingError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 653 | `except` | `LeaseError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 712 | `except` | `LeaseError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 727 | `except` | `LeaseError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 747 | `except` | `LeaseError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 771 | `except` | `SessionBindingError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 864 | `except` | `Exception` | `deferred` | M3-INV-008: log skipped corrupt timeline status rows. |
| 906 | `except` | `LeaseError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/session/config.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 28 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/session/identity.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 49 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 83 | `except` | `EOFError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 90 | `except` | `IdentityError` | `justified` | Narrow/domain catch with local recovery or wrapping. |

### `astrid/core/session/lease.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 77 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 82 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 86 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 275 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 280 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 284 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/session/model.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 72 | `except` | `KeyError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/task/active_run.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 79 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 132 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/task/claim.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 203 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 226 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 246 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 269 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |

### `astrid/core/task/command_render.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 135 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/task/events.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 184 | `except` | `(StaleTailError, StaleEpochError, NotWriterError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 186 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 249 | `except` | `EventLogError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 293 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 295 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 309 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 333 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 335 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 337 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 979 | `except` | `(json.JSONDecodeError, UnicodeDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1010 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1012 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1016 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1036 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/task/gate.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 1003 | `except` | `(FileNotFoundError, json.JSONDecodeError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1172 | `except` | `(FileNotFoundError, json.JSONDecodeError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1326 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1699 | `except` | `(TaskPlanError, EventLogError)` | `justified` | Narrow parent-autoclose builder catch emits a contextual runtime warning and skips only the synthetic parent event. |
| 1827 | `except` | `(TaskPlanError, EventLogError)` | `justified` | Narrow parent-autocomplete builder catch emits a contextual runtime warning and skips only the synthetic parent event. |
| 1928 | `except` | `(json.JSONDecodeError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1939 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1969 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 2254 | `except` | `(json.JSONDecodeError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 2417 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/task/hook.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 49 | `except` | `SessionBindingError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 55 | `except` | `ProjectPathError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 65 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 71 | `except` | `ProjectPathError` | `justified` | Narrow/domain catch with local recovery or wrapping. |

### `astrid/core/task/inbox.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 274 | `except` | `(OSError, json.JSONDecodeError, InboxValidationError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 301 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 310 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 431 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 568 | `except` | `TaskRunGateError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 599 | `except` | `TaskRunGateError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/task/lifecycle.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 317 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 322 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 327 | `except` | `ProjectError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 341 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 374 | `except` | `(OSError, json.JSONDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 409 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 416 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 436 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 448 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 489 | `except` | `SessionBindingError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 537 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 542 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 560 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 662 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 667 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 813 | `assert` | `"$ASTRID_" not in result` | `justified` | Non-runtime assert: debug/type-narrowing or test/dev helper path, not user input validation. |
| 922 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1130 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 1194 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 1235 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 1266 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 1280 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 1316 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 1401 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 1416 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1472 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1516 | `except` | `SessionBindingError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 1533 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 1565 | `except` | `_SBErr` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 1594 | `except` | `(TaskRunGateError, OSError, EventLogError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1827 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 1834 | `except` | `(OSError, json.JSONDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1949 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1955 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 1999 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/task/lifecycle_ack.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 165 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 180 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 227 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 268 | `except` | `TaskRunGateError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 343 | `except` | `TaskRunGateError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 368 | `except` | `(EventLogError, NoRunBoundError, RuntimeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 397 | `except` | `TaskRunGateError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 447 | `except` | `(EventLogError, NoRunBoundError, RuntimeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/task/lifecycle_skip.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 96 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 111 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 194 | `except` | `StaleEpochError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 200 | `except` | `StaleTailError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 206 | `except` | `EventLogError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/task/plan.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 328 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 423 | `except` | `TaskPlanError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 533 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 535 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 537 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 912 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/task/plan_verbs.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 414 | `except` | `MutationInvariantError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 417 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 457 | `except` | `TaskPlanError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 493 | `except` | `TaskPlanError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 522 | `except` | `TaskPlanError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 574 | `except` | `TaskPlanError` | `justified` | Narrow/domain catch with local recovery or wrapping. |

### `astrid/core/task/run_audit.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 36 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 41 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 86 | `except` | `(json.JSONDecodeError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 178 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 183 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 234 | `except` | `(json.JSONDecodeError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 255 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 266 | `except` | `(json.JSONDecodeError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 309 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 314 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 375 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 380 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 459 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 464 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 545 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 550 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 576 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 581 | `except` | `KeyboardInterrupt` | `deferred` | M3-INV-004: make audit follow interrupt return deterministic instead of pass. |
| 679 | `except` | `(json.JSONDecodeError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 799 | `except` | `(MutationInvariantError, Exception)` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |

### `astrid/core/task/validator.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 74 | `except` | `TaskPlanError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 83 | `except` | `TaskPlanError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 102 | `except` | `TaskPlanError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 159 | `except` | `TaskPlanError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 178 | `except` | `TaskPlanError` | `justified` | Narrow/domain catch with local recovery or wrapping. |

### `astrid/core/timeline/_edit_helpers.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 124 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 126 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |

### `astrid/core/timeline/assembly_helper.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 146 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 148 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 164 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 182 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |

### `astrid/core/timeline/branch.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 167 | `except` | `ProjectionError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 169 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 297 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 378 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |

### `astrid/core/timeline/cli.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 53 | `except` | `(crud.TimelineCrudError, TimelineEditError, SessionBindingError, EventLogError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 56 | `except` | `ErasedPayloadProjectionError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 59 | `except` | `ProjectionError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 62 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1095 | `except` | `(EOFError, KeyboardInterrupt)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1386 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 1652 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 2118 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 2180 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 2196 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 2265 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 2270 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 2309 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 2332 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 2341 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 2349 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 2448 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 2460 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 2472 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 2507 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 2575 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 2613 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 2652 | `except` | `(ValueError, ProjectionError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 2680 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 2717 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 2775 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 2781 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 2829 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 2867 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 2902 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 2933 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 2974 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 3005 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 3042 | `except` | `(ValueError, ProjectionError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 3078 | `except` | `(ValueError, ProjectionError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 3105 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |

### `astrid/core/timeline/crud.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 169 | `except` | `(TimelineValidationError, OSError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 179 | `except` | `(TimelineValidationError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 604 | `except` | `(TimelineValidationError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/timeline/erasure.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 323 | `except` | `AttributeError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 340 | `except` | `ProjectionError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 342 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |

### `astrid/core/timeline/eventlog/local_fs.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 75 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 127 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 167 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 189 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 246 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 272 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 277 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 290 | `except` | `EventLogError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 326 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 328 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 346 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 403 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 405 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 407 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 452 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/timeline/eventlog/selector.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 375 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |

### `astrid/core/timeline/eventlog/supabase.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 226 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |

### `astrid/core/timeline/events/schema/types.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 107 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 325 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 815 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 1027 | `assert` | `isinstance(payload, dict)` | `justified` | Non-runtime assert: debug/type-narrowing or test/dev helper path, not user input validation. |

### `astrid/core/timeline/integrity.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 59 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/timeline/inverses.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 830 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 947 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |

### `astrid/core/timeline/migration.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 189 | `except` | `Exception` | `deferred` | M3-INV-017: log schema detection fallback failures. |
| 199 | `except` | `Exception` | `deferred` | M3-INV-018: log schema detection fallback failures. |
| 414 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 490 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 581 | `except` | `Exception` | `deferred` | M3-INV-019: log checkpoint resolution failures. |

### `astrid/core/timeline/model.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 25 | `except` | `ProjectPathError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 32 | `except` | `ProjectPathError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 39 | `except` | `ProjectPathError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 47 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/timeline/observability.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 98 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 149 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 160 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 189 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 203 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |

### `astrid/core/timeline/operations.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 281 | `except` | `ProjectionError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 402 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |

### `astrid/core/timeline/paths.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 108 | `except` | `(ProjectJsonError, OSError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 122 | `except` | `(ProjectJsonError, OSError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 142 | `except` | `(ProjectJsonError, OSError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 170 | `except` | `(ProjectJsonError, OSError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 176 | `except` | `(ProjectJsonError, OSError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 212 | `except` | `TimelineValidationError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 227 | `except` | `(ProjectJsonError, FileNotFoundError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 265 | `except` | `(ProjectJsonError, FileNotFoundError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 269 | `except` | `TimelineValidationError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 289 | `except` | `ErasedPayloadProjectionError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 294 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 302 | `except` | `(ProjectJsonError, FileNotFoundError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 306 | `except` | `TimelineValidationError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 312 | `except` | `TimelineValidationError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/timeline/projection.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 239 | `except` | `KeyError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 705 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 959 | `except` | `Exception` | `deferred` | M3-INV-020: log checkpoint projection degradation. |

### `astrid/core/timeline/repair.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 159 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 194 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 196 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 244 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 289 | `except` | `(FileNotFoundError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 300 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/timeline/transfer.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 286 | `except` | `EventLogIdempotentError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 288 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 301 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |

### `astrid/core/timeline/undo.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 200 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 292 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 314 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 350 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 373 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |

### `astrid/core/update.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 58 | `except` | `(KeyError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/util/http.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 127 | `except` | `HTTPError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 134 | `except` | `URLError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 191 | `except` | `HTTPError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 200 | `except` | `URLError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/core/worker/banodoco_worker.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 189 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 320 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 349 | `except` | `JwtVerificationError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 376 | `except` | `ProjectOwnershipError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 392 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 412 | `except` | `DispatchError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 441 | `except` | `RuntimeError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 497 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |

### `astrid/doctor.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 126 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 405 | `except` | `(ValueError, TypeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/domains/hype/enriched_arrangement.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 94 | `except` | `(TypeError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 302 | `except` | `(KeyError, TypeError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/modalities/__init__.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 83 | `except` | `KeyError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/orchestrate/cli.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 116 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 123 | `except` | `(OrchestrateDefinitionError, TaskPlanError)` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 135 | `except` | `(OrchestrateDefinitionError, TaskPlanError)` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 223 | `except` | `OrchestrateDefinitionError` | `deferred` | M3-INV-012: explain skipped invalid child orchestrator definitions in list/search. |
| 235 | `except` | `(OrchestrateDefinitionError, TaskPlanError)` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 293 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 337 | `except` | `OrchestrateDefinitionError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 347 | `except` | `(OrchestrateDefinitionError, TaskPlanError)` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 374 | `except` | `RuntimeError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 483 | `except` | `(OrchestrateDefinitionError, TaskPlanError)` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 509 | `except` | `Exception` | `deferred` | M3-INV-011: report plan explanation render failures. |
| 551 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/orchestrate/compile.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 74 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |

### `astrid/orchestrate/dsl.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 184 | `except` | `TaskPlanError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 191 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 506 | `except` | `TaskPlanError` | `justified` | Narrow/domain catch with local recovery or wrapping. |

### `astrid/orchestrate/test_runner.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 138 | `except` | `(ChildProcessError, ProcessLookupError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 238 | `except` | `TaskRunGateError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/pipeline.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 100 | `except` | `Exception` | `deferred` | M3-INV-001: make agent-skill nudge failures telemetry-visible or narrowed. |
| 132 | `except` | `SessionBindingError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 158 | `except` | `task_gate.TaskRunGateError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 558 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 576 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 591 | `except` | `SystemExit` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 610 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 653 | `except` | `ChildProcessError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 656 | `except` | `ProcessLookupError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 659 | `except` | `KeyboardInterrupt` | `deferred` | M3-INV-002: return/surface interrupted adapter wait instead of silent pass. |
| 663 | `except` | `OSError` | `deferred` | M3-INV-003: log adapter cleanup kill failures. |
| 706 | `except` | `(ValueError, OSError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/skills/__init__.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 241 | `except` | `Exception` | `deferred` | M3-INV-013: narrow filesystem record probe failure. |
| 311 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/skills/cli.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 27 | `except` | `(KeyError, FileExistsError, ValueError, RuntimeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/skills/discovery.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 70 | `except` | `Exception` | `deferred` | M3-INV-014: log malformed skill metadata fallback. |
| 101 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 141 | `except` | `Exception` | `deferred` | M3-INV-015: log skipped malformed pack skill descriptor. |

### `astrid/skills/harnesses/base.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 73 | `except` | `Exception` | `deferred` | M3-INV-016: narrow optional harness probe failures. |
| 94 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/skills/harnesses/claude.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 74 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/skills/harnesses/codex.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 97 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 115 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/skills/harnesses/hermes.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 110 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 130 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 151 | `except` | `ImportError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 155 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 162 | `except` | `ImportError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/skills/state.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 48 | `except` | `(OSError, json.JSONDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/structure.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 94 | `except` | `SyntaxError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 97 | `except` | `UnicodeDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 130 | `except` | `UnicodeDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 141 | `except` | `SyntaxError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 203 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 233 | `except` | `Exception` | `justified-with-caveat` | Broad catch is bounded by wrapping, stderr/reporting, validation accumulation, or final CLI guard; keep under review for narrower exception tuples. |
| 306 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 357 | `except` | `(SyntaxError, UnicodeDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 432 | `except` | `(SyntaxError, UnicodeDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/theme_schema.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 204 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 206 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/threads/attribute.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 142 | `except` | `(OSError, json.JSONDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 226 | `except` | `(OSError, json.JSONDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 277 | `except` | `(OSError, json.JSONDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 291 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 359 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 367 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 382 | `except` | `(TypeError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 388 | `except` | `ProcessLookupError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 390 | `except` | `PermissionError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 412 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/threads/cli.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 104 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 195 | `except` | `(OSError, json.JSONDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/threads/index.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 77 | `except` | `BlockingIOError` | `justified` | Narrow/domain catch with local recovery or wrapping. |
| 91 | `except` | `(OSError, json.JSONDecodeError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 96 | `except` | `(OSError, json.JSONDecodeError, ValueError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 131 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 141 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/threads/provenance.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 45 | `except` | `(OSError, json.JSONDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 56 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 116 | `except` | `(OSError, json.JSONDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 141 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |

### `astrid/threads/record.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 190 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 208 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 224 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 254 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 321 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/threads/variants.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 38 | `except` | `(OSError, json.JSONDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 49 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 166 | `except` | `(OSError, json.JSONDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 195 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 241 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 269 | `except` | `(OSError, json.JSONDecodeError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 363 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 376 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/timeline.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 36 | `except` | `ImportError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 525 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 598 | `except` | `ImportError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |

### `astrid/utilities/llm_clients.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 76 | `except` | `TypeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 78 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 132 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 278 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 376 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |
| 396 | `except` | `Exception` | `justified-with-caveat` | Broad catch preserves best-effort optional discovery/projection behavior; caveat: should be narrowed or logged when touched. |

### `astrid/verify/checks.py`

| line | kind | caught/test | status | reason |
| ---: | --- | --- | --- | --- |
| 74 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 89 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 91 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 95 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 108 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 110 | `except` | `json.JSONDecodeError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 112 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 175 | `except` | `re.error` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 283 | `except` | `(wave.Error, EOFError)` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 291 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 293 | `except` | `subprocess.TimeoutExpired` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 295 | `except` | `subprocess.CalledProcessError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 297 | `except` | `ValueError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 323 | `except` | `FileNotFoundError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 325 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
| 368 | `except` | `OSError` | `justified` | Named catch handles expected filesystem, JSON, CLI, validation, process, import, network, or domain-error boundary. |
