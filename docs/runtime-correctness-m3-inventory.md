# Runtime Correctness M3 Inventory

Generated from the current non-pack `astrid/**/*.py` AST after the core-layout cleanup.

## Summary

- AST sites inventoried: 745
- Grep lexical hits after the same source exclusions: 760.
- Status vocabulary: `fixed`, `justified`, `justified-with-caveat`, `deferred`.

## Seed-File Non-Fixed Reasons

- `astrid/core/gateway/__init__.py`: Non-fixed AST sites in this file: 5. Reviewed non-pack runtime surface after core-layout cleanup. Existing behavior is retained until a targeted correctness milestone changes it.
- `astrid/core/task/run_audit.py`: Non-fixed AST sites in this file: 21. Reviewed non-pack runtime surface after core-layout cleanup. Existing behavior is retained until a targeted correctness milestone changes it.
- `astrid/core/orchestrate/cli.py`: Non-fixed AST sites in this file: 12. Reviewed non-pack runtime surface after core-layout cleanup. Existing behavior is retained until a targeted correctness milestone changes it.
- `astrid/core/threads/provenance.py`: Non-fixed AST sites in this file: 4. Reviewed non-pack runtime surface after core-layout cleanup. Existing behavior is retained until a targeted correctness milestone changes it.
- `astrid/skills/__init__.py`: Non-fixed AST sites in this file: 3. Reviewed non-pack runtime surface after core-layout cleanup. Existing behavior is retained until a targeted correctness milestone changes it.
- `astrid/skills/discovery.py`: Non-fixed AST sites in this file: 3. Reviewed non-pack runtime surface after core-layout cleanup. Existing behavior is retained until a targeted correctness milestone changes it.
- `astrid/skills/harnesses/base.py`: Non-fixed AST sites in this file: 2. Reviewed non-pack runtime surface after core-layout cleanup. Existing behavior is retained until a targeted correctness milestone changes it.
- `astrid/core/audit/context.py`: Non-fixed AST sites in this file: 2. Reviewed non-pack runtime surface after core-layout cleanup. Existing behavior is retained until a targeted correctness milestone changes it.

## Deferred Tickets

- None.

## Planned Runtime Assert Conversions Completed

- `astrid/core/executor/install.py:239`: completed
- `astrid/core/executor/install.py:245`: completed
- `astrid/core/integrations/runpod/sweeper.py:149`: completed
- `astrid/core/session/cli.py:711`: completed

## Inventory

### `astrid/core/adapter/local.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 47 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 61 | `except` | `except (FileNotFoundError, OSError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 86 | `except` | `except (json.JSONDecodeError, ValueError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 93 | `except` | `except ProcessLookupError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 97 | `except` | `except PermissionError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 115 | `except` | `except (OSError, ValueError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 158 | `except` | `except (json.JSONDecodeError, OSError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/adapter/manual.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 114 | `except` | `except (json.JSONDecodeError, OSError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/adapter/remote_artifact.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 33 | `except` | `except (OSError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 74 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 89 | `except` | `except (FileNotFoundError, OSError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 148 | `except` | `except (TypeError, ValueError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 154 | `except` | `except ProcessLookupError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 157 | `except` | `except PermissionError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 170 | `except` | `except (OSError, ValueError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/audit/cli.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 41 | `except` | `except FileNotFoundError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/audit/context.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 52 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 56 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/audit/transport.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 58 | `except` | `except (UnicodeDecodeError, json.JSONDecodeError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 95 | `except` | `except AuditLedgerError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 160 | `except` | `except (IndexError, ValueError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/audit/util.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 74 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/contracts/capability_runner.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 116 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 126 | `except` | `except Exception as finalize_exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 141 | `except` | `except Exception as finalize_exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 144 | `except` | `except Exception as mark_exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/contracts/run_status.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 119 | `except` | `except KeyError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 136 | `except` | `except KeyError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 150 | `except` | `except KeyError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 168 | `except` | `except KeyError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/contracts/schema_validators.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 22 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/dirty.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 37 | `except` | `except GitUtilError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 91 | `except` | `except (json.JSONDecodeError, OSError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 116 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/doctor.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 126 | `except` | `except Exception as exc:  # pragma: no cover - detail shape is tested through mocks.` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 411 | `except` | `except (ValueError, TypeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 448 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 687 | `except` | `except ProcessLookupError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 689 | `except` | `except PermissionError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 691 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/domains/hype/enriched_arrangement.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 95 | `except` | `except (TypeError, ValueError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 303 | `except` | `except (KeyError, TypeError, ValueError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/element/cli.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 49 | `except` | `except (KeyError, ElementRegistryError, ElementValidationError, ValueError, OverrideStoreError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/element/registry.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 94 | `except` | `except KeyError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 283 | `except` | `except ElementValidationError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 298 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/element/schema.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 263 | `except` | `except ManifestParseError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 294 | `except` | `except ElementValidationError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/executor/banodoco_catalog.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 70 | `except` | `except urllib.error.URLError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 74 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/executor/cli.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 63 | `except` | `except (KeyError, ExecutorValidationError, ProjectRunError, ValueError, OverrideStoreError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/executor/folder.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 74 | `except` | `except ExecutorValidationError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 104 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 115 | `except` | `except ExecutorValidationError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/executor/install.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 170 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/executor/registry.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 371 | `except` | `except ManifestParseError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/executor/runner.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 188 | `except` | `except task_gate.TaskRunGateError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 547 | `except` | `except InProcessExecutionPreconditionError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 560 | `except` | `except InProcessInvocationError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/executor/schema.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 284 | `except` | `except FileNotFoundError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 286 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 290 | `except` | `except ExecutorValidationError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 297 | `except` | `except ManifestParseError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 801 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 804 | `except` | `except KeyError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/gateway/__init__.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 176 | `except` | `except AstridError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 178 | `except` | `except Exception as exc:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 207 | `except` | `except Exception as exc:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 243 | `except` | `except SessionBindingError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 279 | `except` | `except task_gate.TaskRunGateError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/gateway/dispatch.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 71 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 303 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 398 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 531 | `except` | `except SystemExit:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 552 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 570 | `except` | `except SystemExit:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 589 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/gateway/help.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 24 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/gateway/project.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 124 | `except` | `except Exception as exc:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/gateway/wait.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 58 | `except` | `except ChildProcessError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 61 | `except` | `except ProcessLookupError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 64 | `except` | `except KeyboardInterrupt:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 68 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 113 | `except` | `except (ValueError, OSError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/generation/backends/base.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 34 | `except` | `except (ValueError, TypeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 41 | `except` | `except (ValueError, TypeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 60 | `except` | `except (ValueError, TypeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/generation/backends/codex.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 157 | `except` | `except FileNotFoundError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 159 | `except` | `except subprocess.TimeoutExpired as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/generation/backends/fal.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 143 | `except` | `except KeyError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 298 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/generation/backends/registry.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 107 | `except` | `except KeyError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 211 | `except` | `except (TypeError, ValueError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/generation/verbs.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 49 | `except` | `except KeyError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 109 | `except` | `except (ImportError, AttributeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/git_util.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 49 | `except` | `except FileNotFoundError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 51 | `except` | `except subprocess.TimeoutExpired as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 75 | `except` | `except FileNotFoundError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 77 | `except` | `except subprocess.TimeoutExpired as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 132 | `except` | `except FileNotFoundError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 134 | `except` | `except subprocess.TimeoutExpired as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/integrations/reigh/data_provider.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 336 | `except` | `except RuntimeError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/integrations/reigh/supabase_client.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 70 | `except` | `except urllib.error.HTTPError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 77 | `except` | `except urllib.error.URLError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 86 | `except` | `except json.JSONDecodeError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 108 | `except` | `except urllib.error.HTTPError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 115 | `except` | `except urllib.error.URLError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 124 | `except` | `except json.JSONDecodeError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/integrations/reigh/task_client.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 79 | `except` | `except urllib.error.HTTPError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 81 | `except` | `except urllib.error.URLError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 118 | `except` | `except json.JSONDecodeError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/integrations/reigh/timeline_io.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 216 | `except` | `except SupabaseHTTPError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 287 | `except` | `except SupabaseHTTPError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 312 | `except` | `except SupabaseHTTPError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/integrations/reigh/worker_jwt.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 61 | `except` | `except Exception as exc:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 72 | `except` | `except InvalidTokenError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 87 | `except` | `except AttributeError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 126 | `except` | `except InvalidTokenError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/integrations/runpod/sweeper.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 60 | `except` | `except (json.JSONDecodeError, OSError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 77 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 101 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 149 | `except` | `except StaleTailError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 215 | `except` | `except RuntimeError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 263 | `except` | `except (ValueError, TypeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 293 | `except` | `except LeaseError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 316 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 352 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 376 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/integrations/worker/banodoco_worker.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 319 | `except` | `except Exception as exc:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 348 | `except` | `except JwtVerificationError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 375 | `except` | `except ProjectOwnershipError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 391 | `except` | `except Exception as exc:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 410 | `except` | `except Exception as exc:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 423 | `except` | `except DispatchError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 452 | `except` | `except RuntimeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 508 | `except` | `except Exception as exc:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/lineage/variants.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 38 | `except` | `except (OSError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 49 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 166 | `except` | `except (OSError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 195 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 241 | `except` | `except json.JSONDecodeError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 269 | `except` | `except (OSError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 363 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 376 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/media.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 77 | `except` | `except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 88 | `except` | `except (ValueError, TypeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 100 | `except` | `except (ValueError, TypeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 110 | `except` | `except (ValueError, ZeroDivisionError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/modalities/__init__.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 74 | `except` | `except KeyError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/model_catalog/cli.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 72 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 91 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 190 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 199 | `except` | `except KeyError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/model_catalog/registry.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 51 | `except` | `except KeyError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 184 | `except` | `except KeyError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/model_catalog/schema.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 318 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/orchestrate/cli.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 112 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 119 | `except` | `except (OrchestrateDefinitionError, TaskPlanError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 130 | `except` | `except (OrchestrateDefinitionError, TaskPlanError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 216 | `except` | `except OrchestrateDefinitionError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 228 | `except` | `except (OrchestrateDefinitionError, TaskPlanError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 287 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 331 | `except` | `except OrchestrateDefinitionError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 340 | `except` | `except (OrchestrateDefinitionError, TaskPlanError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 366 | `except` | `except RuntimeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 474 | `except` | `except (OrchestrateDefinitionError, TaskPlanError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 499 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 584 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/orchestrate/compile.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 71 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/orchestrate/dsl.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 184 | `except` | `except TaskPlanError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 191 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 506 | `except` | `except TaskPlanError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/orchestrate/test_runner.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 139 | `except` | `except (ChildProcessError, ProcessLookupError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 244 | `except` | `except TaskRunGateError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/orchestrator/cli.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 68 | `except` | `except (KeyError, OrchestratorValidationError, ProjectRunError, ValueError, OverrideStoreError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/orchestrator/folder.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 66 | `except` | `except OrchestratorValidationError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 94 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 105 | `except` | `except OrchestratorValidationError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/orchestrator/registry.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 328 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 342 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 460 | `except` | `except ManifestParseError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/orchestrator/runner.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 178 | `except` | `except task_gate.TaskRunGateError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 263 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 270 | `except` | `except OrchestratorRunnerError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 272 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 362 | `except` | `except InProcessExecutionPreconditionError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 373 | `except` | `except InProcessInvocationError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 454 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/orchestrator/schema.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 173 | `except` | `except ManifestParseError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 177 | `except` | `except OrchestratorValidationError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/pack/__init__.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 324 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 1035 | `except` | `except FileNotFoundError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 1040 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 1051 | `except` | `except PackValidationError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 1053 | `except` | `except yaml.YAMLError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/pack/agent_index.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 65 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 106 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 111 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 116 | `except` | `except yaml.YAMLError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 342 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 364 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/pack/alias_resolver.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 71 | `except` | `except AliasResolutionError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/pack/cli.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 166 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 177 | `except` | `except AstridError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/pack/cli_inspect.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 68 | `except` | `except Exception as e:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 82 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 324 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 386 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 458 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/pack/entrypoint.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 89 | `except` | `except AstridError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 91 | `except` | `except (ValueError, RuntimeError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 99 | `except` | `except Exception as exc:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/pack/gitignore.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 150 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 202 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/pack/install_git.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 76 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 81 | `except` | `except subprocess.CalledProcessError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 85 | `except` | `except subprocess.TimeoutExpired:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 119 | `except` | `except subprocess.TimeoutExpired:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 124 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 163 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 174 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 209 | `except` | `except RuntimeError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 237 | `except` | `except RuntimeError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 275 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 329 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 413 | `except` | `except RuntimeError as e:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 437 | `except` | `except RuntimeError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 480 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 506 | `except` | `except Exception as e:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 539 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/pack/install_local.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 132 | `except` | `except Exception as e:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 180 | `except` | `except Exception as e:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 266 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 339 | `except` | `except Exception as e:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 372 | `except` | `except OSError as e:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 392 | `except` | `except OSError as e:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 749 | `except` | `except Exception as e:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 770 | `except` | `except Exception as e:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 885 | `except` | `except (EOFError, KeyboardInterrupt):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 902 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 945 | `except` | `except Exception as e:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 1007 | `except` | `except FileNotFoundError as e:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 1010 | `except` | `except Exception as e:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/pack/install_trust.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 41 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 194 | `except` | `except (EOFError, KeyboardInterrupt):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 211 | `except` | `except (EOFError, KeyboardInterrupt):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/pack/manifest.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 30 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 37 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 45 | `except` | `except yaml.YAMLError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/pack/override.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 87 | `except` | `except (json.JSONDecodeError, OSError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/pack/resolver.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 23 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 66 | `except` | `except CallableNotFoundError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 70 | `except` | `except PackResolverError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/pack/store.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 34 | `except` | `except ImportError:  # pragma: no cover — dev-friendly fallback` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 128 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 178 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 213 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 235 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 261 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 310 | `except` | `except (OSError, _json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 314 | `except` | `except (TypeError, Exception):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 406 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 422 | `except` | `except (OSError, _json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 426 | `except` | `except TypeError:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 428 | `except` | `except Exception as exc:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/pack/validate.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 293 | `except` | `except ManifestParseError as e:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 320 | `except` | `except ValidationError as e:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 334 | `except` | `except Exception as e:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 377 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 596 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 632 | `except` | `except ExecutorValidationError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 642 | `except` | `except OrchestratorValidationError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 669 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 845 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 866 | `except` | `except AliasResolutionError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 920 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 1001 | `except` | `except ManifestParseError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/pack/validate_layout.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 312 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 376 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 428 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/project/cli.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 72 | `except` | `except ProjectError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 74 | `except` | `except (FileExistsError, FileNotFoundError, ValueError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 501 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 544 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 653 | `except` | `except Exception as exc:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 758 | `except` | `except Exception as exc:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 777 | `except` | `except Exception as exc:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 840 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 907 | `except` | `except Exception:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 963 | `except` | `except (json.JSONDecodeError, OSError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 1016 | `except` | `except Exception:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/project/current_run.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 53 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 117 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/project/jsonio.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 29 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 31 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 33 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 44 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/project/project.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 259 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 268 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/project/run.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 125 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 345 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 372 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 555 | `except` | `except TimelineCrudError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 649 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 660 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 712 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 722 | `except` | `except KeyError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/project/schema.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 262 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 309 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/project/sidecar.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 45 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/runtime/in_process.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 136 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 168 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 215 | `except` | `except (CallableNotFoundError, PackResolverError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 217 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/runtime/log_capture.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 55 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 177 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/scaffold.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 126 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/session/binding.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 152 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 185 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 192 | `except` | `except FileNotFoundError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 197 | `except` | `except SessionValidationError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/session/cli_attach.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 112 | `except` | `except IdentityError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 122 | `except` | `except (ValueError, IdentityError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 135 | `except` | `except SessionRecordNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 174 | `except` | `except ProjectError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 296 | `except` | `except (EOFError, KeyboardInterrupt):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/session/cli_sessions.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 106 | `except` | `except SessionRecordNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 181 | `except` | `except (IdentityError, ProjectError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 221 | `except` | `except SessionBindingError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 231 | `except` | `except LeaseError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 262 | `except` | `except SessionTakeoverTargetError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 277 | `except` | `except LeaseError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 333 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 350 | `except` | `except (ValueError, TypeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 399 | `except` | `except (OSError, SessionStoreError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/session/cli_status.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 86 | `except` | `except SessionBindingError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 212 | `except` | `except Exception as exc:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 264 | `except` | `except LeaseError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 338 | `except` | `except Exception as exc:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 373 | `except` | `except LeaseError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/session/config.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 28 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/session/identity.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 49 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 83 | `except` | `except EOFError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 90 | `except` | `except IdentityError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/session/lease.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 89 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 94 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 98 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 327 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 332 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 336 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/session/lifecycle.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 299 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/session/model.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 88 | `except` | `except KeyError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 125 | `except` | `except FileNotFoundError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 129 | `except` | `except (ProjectJsonError, SessionValidationError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 143 | `except` | `except SessionStoreError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/structure.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 78 | `except` | `except SyntaxError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 81 | `except` | `except UnicodeDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 122 | `except` | `except SyntaxError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 125 | `except` | `except UnicodeDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 197 | `except` | `except UnicodeDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 209 | `except` | `except SyntaxError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 312 | `except` | `except (OSError, subprocess.CalledProcessError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 354 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 384 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 435 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 441 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 468 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 582 | `except` | `except (SyntaxError, UnicodeDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 677 | `except` | `except (SyntaxError, UnicodeDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 721 | `except` | `except (SyntaxError, UnicodeDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/claim.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 236 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 242 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 272 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 297 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 303 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 333 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/command_render.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 135 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/events.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 186 | `except` | `except (StaleTailError, StaleEpochError, NotWriterError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 188 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 251 | `except` | `except EventLogError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 295 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 297 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 311 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 335 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 337 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 339 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 886 | `except` | `except (json.JSONDecodeError, UnicodeDecodeError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 917 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 919 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 923 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 943 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/gate.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 576 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/gate_attestation.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 66 | `except` | `except (json.JSONDecodeError, OSError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 77 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 107 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/gate_dispatch.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 118 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/gate_finalize.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 246 | `except` | `except (json.JSONDecodeError, OSError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/gate_repeat.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 111 | `except` | `except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 217 | `except` | `except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 361 | `except` | `except (TaskPlanError, EventLogError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 493 | `except` | `except (TaskPlanError, EventLogError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/hook.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 50 | `except` | `except SessionBindingError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 56 | `except` | `except ProjectPathError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 66 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 72 | `except` | `except ProjectPathError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/inbox.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 274 | `except` | `except (OSError, json.JSONDecodeError, InboxValidationError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 301 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 310 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 431 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 568 | `except` | `except TaskRunGateError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 599 | `except` | `except TaskRunGateError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/lifecycle_ack.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 175 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 189 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 233 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 273 | `except` | `except TaskRunGateError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 358 | `except` | `except TaskRunGateError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 383 | `except` | `except (EventLogError, NoRunBoundError, RuntimeError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 420 | `except` | `except TaskRunGateError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 469 | `except` | `except (EventLogError, NoRunBoundError, RuntimeError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/lifecycle_skip.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 113 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 127 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 207 | `except` | `except StaleEpochError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 212 | `except` | `except StaleTailError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 217 | `except` | `except EventLogError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/operator_render.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 185 | `assert` | `assert "$ASTRID_" not in result, (` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 289 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/operator_view.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 140 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 145 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 301 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 347 | `except` | `except SessionBindingError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 376 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 419 | `except` | `except _SBErr as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 459 | `except` | `except (TaskRunGateError, OSError, EventLogError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 784 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 791 | `except` | `except (OSError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/orchestrator_resolver.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 83 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 113 | `except` | `except Exception as exc:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 126 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/plan.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 327 | `except` | `except json.JSONDecodeError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 422 | `except` | `except TaskPlanError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 532 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 534 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 536 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 911 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/plan_builder.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 269 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 274 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 279 | `except` | `except ProjectError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 293 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 326 | `except` | `except (OSError, json.JSONDecodeError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 361 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 368 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 388 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 400 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 441 | `except` | `except SessionBindingError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/plan_verbs.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 415 | `except` | `except MutationInvariantError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 418 | `except` | `except Exception as exc:  # StaleTailError / StaleEpochError / EventLogError / auth` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 458 | `except` | `except TaskPlanError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 494 | `except` | `except TaskPlanError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 523 | `except` | `except TaskPlanError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 575 | `except` | `except TaskPlanError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/run_audit.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 37 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 42 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 175 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 180 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 231 | `except` | `except (json.JSONDecodeError, OSError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 252 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 263 | `except` | `except (json.JSONDecodeError, OSError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 306 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 311 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 372 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 377 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 459 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 464 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 545 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 550 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 576 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 581 | `except` | `except KeyboardInterrupt:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 633 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 645 | `except` | `except (json.JSONDecodeError, OSError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 702 | `except` | `except (json.JSONDecodeError, OSError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 822 | `except` | `except (MutationInvariantError, Exception) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/run_gc.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 109 | `except` | `except (OSError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 147 | `except` | `except (OSError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 163 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 218 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 225 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 300 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/run_store.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 97 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 119 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 124 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 149 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 211 | `except` | `except (OSError, ValueError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 235 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 241 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 296 | `except` | `except SystemExit as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/session_discovery.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 29 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 71 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 153 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 168 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 183 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/task/validator.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 73 | `except` | `except TaskPlanError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 82 | `except` | `except TaskPlanError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 101 | `except` | `except TaskPlanError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 158 | `except` | `except TaskPlanError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 177 | `except` | `except TaskPlanError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/theme.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 66 | `except` | `except Exception as exc:  # noqa: BLE001` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/theme_schema.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 204 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 206 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/threads/attribute.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 144 | `except` | `except (OSError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 228 | `except` | `except (OSError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 279 | `except` | `except (OSError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 285 | `except` | `except (TypeError, ValueError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 299 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 367 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 375 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 390 | `except` | `except (TypeError, ValueError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 396 | `except` | `except ProcessLookupError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 398 | `except` | `except PermissionError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 420 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/threads/cli.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 118 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 209 | `except` | `except (OSError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 214 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/threads/index.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 77 | `except` | `except BlockingIOError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 91 | `except` | `except (OSError, json.JSONDecodeError, ValueError) as current_error:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 96 | `except` | `except (OSError, json.JSONDecodeError, ValueError) as backup_error:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 131 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 141 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/threads/provenance.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 45 | `except` | `except (OSError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 56 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 116 | `except` | `except (OSError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 141 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/threads/record.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 185 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 203 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 219 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 249 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 316 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/threads/schema.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 215 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/threads/variants.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 40 | `except` | `except (OSError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 51 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 168 | `except` | `except (OSError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 196 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 242 | `except` | `except json.JSONDecodeError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 270 | `except` | `except (OSError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 364 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 377 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/_edit_helpers.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 127 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 129 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/banodoco_schema.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 46 | `except` | `except ImportError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 538 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 611 | `except` | `except ImportError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/branch.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 166 | `except` | `except ProjectionError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 168 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 296 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 377 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/cli.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 41 | `except` | `except AstridArgumentError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 43 | `except` | `except (crud.TimelineCrudError, TimelineEditError, SessionBindingError, EventLogError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 45 | `except` | `except ErasedPayloadProjectionError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 47 | `except` | `except (ProjectionError, ValueError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 143 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/cli_backends.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 42 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 83 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 128 | `except` | `except (ValueError, ProjectionError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 164 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 205 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 271 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 280 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 331 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 369 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 409 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 443 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 491 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 527 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 569 | `except` | `except (ValueError, ProjectionError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 611 | `except` | `except (ValueError, ProjectionError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/cli_crud.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 290 | `except` | `except (EOFError, KeyboardInterrupt):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/cli_edits.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 60 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 111 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/cli_events.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 56 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 269 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 334 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 406 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 414 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 448 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 474 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 483 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 493 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 594 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 609 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 624 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 661 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/crud.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 15 | `except` | `except ImportError:  # pragma: no cover` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 176 | `except` | `except (TimelineValidationError, OSError, ValueError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 186 | `except` | `except (TimelineValidationError, OSError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 627 | `except` | `except (TimelineValidationError, OSError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/erasure.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 321 | `except` | `except AttributeError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 338 | `except` | `except ProjectionError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 340 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/eventlog/local_fs.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 74 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 126 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 166 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 188 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 244 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 270 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 275 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 288 | `except` | `except EventLogError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 324 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 326 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 344 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 401 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 403 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 405 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 450 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/eventlog/selector.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 372 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/eventlog/supabase.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 225 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/events/schema/types.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 297 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 800 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 1012 | `assert` | `assert isinstance(payload, dict)` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/integrity.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 59 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/inverses.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 828 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 945 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/migration.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 166 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 176 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 394 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 470 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 561 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/model.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 25 | `except` | `except ProjectPathError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 32 | `except` | `except ProjectPathError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 39 | `except` | `except ProjectPathError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 47 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/observability.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 97 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 148 | `except` | `except json.JSONDecodeError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 159 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 188 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 202 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/operations.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 283 | `except` | `except ProjectionError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 404 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/paths.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 108 | `except` | `except (ProjectJsonError, OSError, ValueError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 122 | `except` | `except (ProjectJsonError, OSError, ValueError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 142 | `except` | `except (ProjectJsonError, OSError, ValueError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 170 | `except` | `except (ProjectJsonError, OSError, ValueError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 176 | `except` | `except (ProjectJsonError, OSError, ValueError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 212 | `except` | `except TimelineValidationError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 227 | `except` | `except (ProjectJsonError, FileNotFoundError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 265 | `except` | `except (ProjectJsonError, FileNotFoundError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 269 | `except` | `except TimelineValidationError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 289 | `except` | `except (ErasedPayloadProjectionError, ProjectionError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 295 | `except` | `except TimelineValidationError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 297 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 305 | `except` | `except (ProjectJsonError, FileNotFoundError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 309 | `except` | `except TimelineValidationError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 315 | `except` | `except TimelineValidationError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/projection.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 169 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 260 | `except` | `except KeyError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 726 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 980 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/repair.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 158 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 193 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 195 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 243 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 289 | `except` | `except (FileNotFoundError, OSError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 300 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/transfer.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 287 | `except` | `except EventLogIdempotentError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 289 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 302 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/timeline/undo.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 193 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 285 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 307 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 343 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 366 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/update.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 57 | `except` | `except (KeyError, ValueError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/util/atomic_io.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 28 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 92 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 104 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 126 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 140 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 142 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 144 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/util/http.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 127 | `except` | `except HTTPError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 134 | `except` | `except URLError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 191 | `except` | `except HTTPError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 200 | `except` | `except URLError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/util/llm_clients.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 75 | `except` | `except TypeError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 77 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 131 | `except` | `except ValueError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 277 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 375 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 395 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/util/log_and_swallow.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 45 | `except` | `except exc_types as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/util/png_metadata.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 55 | `except` | `except ImportError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 92 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 102 | `except` | `except UnicodeEncodeError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/core/verify/checks.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 74 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 89 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 91 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 95 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 108 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 110 | `except` | `except json.JSONDecodeError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 112 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 175 | `except` | `except re.error as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 283 | `except` | `except (wave.Error, EOFError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 291 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 293 | `except` | `except subprocess.TimeoutExpired:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 295 | `except` | `except subprocess.CalledProcessError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 297 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 323 | `except` | `except FileNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 325 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 368 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/sdk/discovery.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 442 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 463 | `except` | `except KeyError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 488 | `except` | `except KeyError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 517 | `except` | `except ValueError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 529 | `except` | `except KeyError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 540 | `except` | `except KeyError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 568 | `except` | `except CapabilityNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 572 | `except` | `except CapabilityNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 583 | `except` | `except CapabilityNotFoundError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/sdk/events.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 69 | `except` | `except AstridSDKError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 71 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 96 | `except` | `except AstridSDKError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 98 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 116 | `except` | `except AstridSDKError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 118 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/sdk/generation.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 162 | `except` | `except KeyError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 207 | `except` | `except KeyError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 286 | `except` | `except KeyError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/sdk/invocation.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 309 | `except` | `except AstridSDKError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 311 | `except` | `except Exception as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/skills/__init__.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 347 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 417 | `except` | `except Exception:  # noqa: BLE001 - a flaky probe must not block the command` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 430 | `except` | `except Exception:  # noqa: BLE001 - never let auto-heal break the real command` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/skills/cli.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 32 | `except` | `except (KeyError, FileExistsError, ValueError, RuntimeError) as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/skills/discovery.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 69 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 103 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 175 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/skills/harnesses/base.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 73 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 141 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/skills/harnesses/claude.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 74 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/skills/harnesses/codex.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 95 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 113 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/skills/harnesses/hermes.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 109 | `except` | `except OSError as exc:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 129 | `except` | `except OSError:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 150 | `except` | `except ImportError:  # pragma: no cover` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 154 | `except` | `except Exception:` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
| 161 | `except` | `except ImportError:  # pragma: no cover` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |

### `astrid/skills/state.py`

| Line | Kind | Snippet | Status | Reason |
| ---: | --- | --- | --- | --- |
| 48 | `except` | `except (OSError, json.JSONDecodeError):` | `justified` | Reviewed non-pack runtime surface after core-layout cleanup. Existing assert/exception behavior is intentionally retained. |
