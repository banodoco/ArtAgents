# Standard composition guard cleanup

Date: 2026-08-24  
Scope: test/contract cleanup only  
Product composition changes: none

## Outcome

The stale standard-composition guard is corrected. Astrid still explicitly selects exactly `timeline`, `shots`, and `references` as its standard domain schema packs, in addition to `core`. The tracked optional `runaway/schema-pack.yaml` remains available in-tree but is not auto-discovered into the standard database composition.

The old test incorrectly equated these two claims:

1. standard composition must not dynamically discover schema packs; and
2. no other schema-pack manifest may exist in the package tree.

Only the first claim is the product contract. The second became false when the optional `runaway` schema pack was added.

## Guard changes

Updated `tests/v10/test_registry.py::test_standard_composition_has_no_discovery_beyond_in_tree_manifests` to prove the actual boundary:

- every explicitly selected standard manifest exists;
- `runaway` is a concrete optional in-tree manifest outside the standard allowlist;
- the pack-layer standard builder returns exactly `core + timeline + shots + references`;
- `runaway` is absent from that frozen registry.

This makes a future glob-based implementation fail observably without forbidding optional schema manifests from being shipped.

Added `test_pack_and_kernel_standard_registry_builders_have_exact_parity`. Astrid intentionally has two explicit standard builders at different dependency layers:

- `astrid.packs.build_standard_registry()`; and
- `astrid.core.schema_packs.standard.build_standard_registry()`.

The new guard compares:

- the explicit ordered pack tuple;
- registered pack manifests;
- table ownership;
- stream, event, and command vocabulary;
- repository declarations;
- CLI and bridge mounts;
- migration descriptors; and
- SHA-256 checksums of the exact migration resource bytes.

That catches either builder drifting to a different database contract while preserving the intentional no-discovery design.

## Verification

Focused composition slice:

```text
python3 -m pytest -q \
  tests/v10/test_registry.py::test_standard_composition_registers_exactly_three_packs \
  tests/v10/test_registry.py::test_standard_composition_declares_the_fixed_pack_order \
  tests/v10/test_registry.py::test_standard_composition_has_no_discovery_beyond_in_tree_manifests \
  tests/v10/test_registry.py::test_pack_and_kernel_standard_registry_builders_have_exact_parity \
  tests/v10/test_registry.py::test_standard_composition_derives_20_table_catalog \
  tests/v10/test_standard_application.py::test_composed_database_is_exactly_the_frozen_catalog \
  tests/v10/test_standard_application.py::test_composition_and_event_repository_do_no_dynamic_discovery \
  tests/v10/test_kernel_read_composition.py

8 passed in 0.35s
```

Full schema-registry test module:

```text
python3 -m pytest -q tests/v10/test_registry.py

64 passed in 0.50s
```

Final combined regression pass after lint cleanup:

```text
python3 -m pytest -q \
  tests/v10/test_registry.py \
  tests/v10/test_standard_application.py::test_composed_database_is_exactly_the_frozen_catalog \
  tests/v10/test_standard_application.py::test_composition_and_event_repository_do_no_dynamic_discovery \
  tests/v10/test_kernel_read_composition.py

67 passed in 0.83s
```

`python3 -m ruff check tests/v10/test_registry.py` also passed.

## Contract retained

- No standard builder was changed.
- No optional schema pack was auto-discovered.
- No migration validation was weakened.
- The standard composition remains exactly `core`, `references`, `shots`, and `timeline` when frozen (mapping order is deterministic); its explicit declaration order remains `timeline`, `shots`, `references`.
