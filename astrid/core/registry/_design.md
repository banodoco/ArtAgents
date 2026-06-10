# CapabilityRegistry — kernel base contract

## 1. Overview

`CapabilityRegistry[K, T]` is the generic base class shared by the three layered
registries:

- `ExecutorRegistry`  (`astrid/core/executor/registry.py`)
- `OrchestratorRegistry` (`astrid/core/orchestrator/registry.py`)
- `ElementRegistry`  (`astrid/core/element/registry.py`)

Each subclass specialises in a single capability kind (executor, orchestrator,
element), but the storage shape, sort-then-pick-first winner strategy, and
public read surface are identical.  The kernel base captures that shared
contract without forcing every subclass into a single `register()` or `get()`
signature.

## 2. Storage: `_entries: dict[K, list[T]]`

Every registry stores a flat dictionary where each key maps to an **ordered
list** of definitions.  The order is the priority rank — index `[0]` is always
the winning definition; indices `[1:]` are shadowed.

| Registry | Key type `K` | Example key |
|---|---|---|
| Executor | `str` (executor id) | `"transcribe"` |
| Orchestrator | `str` (orchestrator id) | `"scenes"` |
| Element | `tuple[str, str]` (`(kind, element_id)`) | `("text_card", "default")` |

Sort discipline:

- **Executor / Orchestrator:** `int(d.metadata.get("priority", 30))` ascending.
  Lower numeric priority = higher precedence.
- **Element:** `(priority, source, str(root))` tuple ascending.
  Priority is a dataclass field, not metadata.

The base declares `_entries: dict[K, list[T]]` in `__init__` and relies on
subclass `register()` to maintain sort order.  No public mutator exists on the
base — callers iterate through `register()` on each subclass.

## 3. Public surface (provided by the base)

| Method | Returns | Description |
|---|---|---|
| `list(kind: Optional[str] = None)` | `tuple[T, ...]` | Winners only (index `[0]` of each entry), optionally filtered by `kind`, sorted by id.  Executor/Orchestrator validate `kind` ∈ `{"built_in", "external"}`; Element passes `kind` through `element_kind_registry.normalize()`. |
| `as_mapping()` | `MappingProxyType[K, T]` | Immutable key → winner mapping for fast lookups across the whole registry. |
| `conflicts()` | `tuple[Conflict, ...]` | Entries where `len(definitions) > 1`.  Returns winner + shadowed tuple.  Element returns `ElementConflict` (kind + id); Executor/Orchestrator will receive an analogous shape. |

### Intentional omissions

- **No public `register()` on the base.**  SD2: Each subclass accepts different
  input types:
  - Executor/Orchestrator: `Definition | dict[str, Any]` — validates inside
    `register()` via `validate_*_definition()`.
  - Element: `ElementDefinition` only (already validated at load time).
  A uniform base signature would force validation into a hook that doesn't fit
  element's pre-validated pipeline.

- **No public `get()` on the base.**  SD3: Override assembly lives in subclass
  `get()`.  The base provides a protected `_resolve_override_key()` helper,
  but each subclass decides how to annotate/return the resolved definition:
  - Executor/Orchestrator return the override target definition directly.
  - Element wraps the target with `dataclasses.replace(..., metadata={...,
    "override_target": target_id})` so callers can trace the remapping.

## 4. Protected helpers (provided by the base)

| Helper | Signature | Purpose |
|---|---|---|
| `_resolve_entry` | `(entry: list[T] \| T) -> T` | Return the winner.  Handles legacy scalar values (someone assigned directly to `_executors[id] = def`) by returning the scalar as-is. |
| `_iter_entries` | `(entry: list[T] \| T) -> Iterable[T]` | Yield every definition — winner + shadowed.  Used by `_iter_all()` and validation loops that need to inspect the full set. |
| `_winner_for` | `(key: K) -> T` | Shorthand for `_resolve_entry(self._entries[key])`.  DRY's up the `entries[key][0]` pattern. |
| `_resolve_override_key` | `(capability_kind: str, key: K) -> K \| None` | Consults `self.override_store` (if set) and returns the remapped key, or `None` if no override exists.  The returned key may be the same as the input (no-op override).  Used by subclass `get()`. |

### Helper that stays subclass-only

`_resolve_requested_id(capability_id: str) -> str` resolves an alias to a
canonical registry key via `self.alias_resolver`.  It raises `KeyError` when
the id (or its resolved target) is absent.  This logic is shared by Executor
and Orchestrator but does **not** fit Element (which keys on `(kind, id)`
tuples and delegates kind normalisation to `element_kind_registry`).  The base
must not assume alias resolution; subclasses that need it keep their own copy.

## 5. What each subclass brings

| Concern | Who owns it |
|---|---|
| Input validation (`validate_*_definition`) | Subclass `register()` |
| Type-specific key shape (`str` vs `tuple[str, str]`) | Subclass `__init__` |
| Alias resolution (`_resolve_requested_id`) | Executor/Orchestrator (not Element) |
| Override assembly / metadata annotation | Subclass `get()` |
| `fork()` | Subclass (deep fork, local pack plumbing) |
| `validate_all()` (graph refs, cycles, etc.) | Subclass (executor/orchestrator cross-references) |
| `to_dict()` / `to_json()` | Subclass (different top-level key names) |
| `_validate_child_*` / `_strict_child_type_check` | Orchestrator only |

## 6. Design rationale (decisions locked by SD1–SD3)

- **SD1** (`ModelRegistry` exempt): `ModelRegistry` uses a flat `dict[str,
  ModelEntry]` with no multi-source layering, no priority sort, no
  alias/override hooks.  It loads from a static YAML via `@classmethod` and
  never calls `register()`.  Forcing it onto the `dict[K, list[T]]` shape
  would add indirection for zero benefit.

- **SD2** (no public `register()` on base): Each subclass owns its validation.
  Executor/Orchestrator accept `Definition | dict`; Element accepts only
  `ElementDefinition`.  A shared `register()` would need a callback hook and
  would still differ in key construction.

- **SD3** (no public `get()` on base): Override resolution is per-subclass.
  Element annotates the returned definition with `override_target` metadata via
  `dataclasses.replace`; executor/orchestrator return targets directly.
  Lifting override assembly into the base would lose element's annotation
  behaviour.

## 7. Non-goals

- The base does **not** own `fork()` — it requires executor/orchestrator
  metadata fields (`content_root`, `executor_root`, `orchestrator_root`)
  that differ across subclasses.
- The base does **not** own alias discovery or pack loading —
  `load_default_registry()` is per-subclass module-level code.
- The base does **not** enforce a particular sort key — subclasses provide
  their own `key=` lambda inside `register()`.
