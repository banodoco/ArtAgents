# Schema Version Parser Policy

## Purpose

`dataset-config.schema.json` is a strict schema that requires `schema_version: 1`. However, the parser must handle three real-world scenarios that cannot all be encoded in a single static JSON Schema file. This document defines the parser behavior for each scenario.

## Parser Behavior by Scenario

### 1. Valid v1 Config (`schema_version: 1` present)

**Example:** `contracts/fixtures/dataset-config.valid.json`

1. Parse JSON.
2. Validate against `dataset-config.schema.json`.
3. If validation passes → proceed.
4. If validation fails → report parseable validation error with field path and reason.

### 2. Missing `schema_version` (Legacy Compatibility)

**Example:** `contracts/fixtures/dataset-config.missing-schema-version.json`

1. Parse JSON.
2. Detect absence of `schema_version` field.
3. Emit deprecation warning: `"schema_version is missing; treating as v1. This is deprecated and will be removed in a future release."`
4. Treat all other fields as v1 semantics.
5. Validate remaining fields against v1 schema (ignoring the `schema_version` constraint for this parse only).
6. Record in run state: `"schema_version_source": "deprecated_inferred_v1"`.

### 3. Future Schema Version

**Example:** `contracts/fixtures/dataset-config.future-version.json`

1. Parse JSON.
2. Read `schema_version`.
3. If `schema_version > 1`:
   - Fail with parseable validation error: `"unsupported schema_version N; max supported: 1"`
   - Exit with non-zero status.
   - Do NOT attempt to parse as v1.
   - Do NOT attempt heuristic compatibility.

### 4. Unknown Top-Level Keys

1. Parse JSON.
2. Check all top-level keys against known v1 keys.
3. If any unknown key is present and is NOT under the `extensions` object:
   - Fail with: `"unknown config key: 'X'; valid keys: [...]. Use 'extensions' object for experimental fields."`
4. Keys under `extensions` are silently accepted and passed through.

## Implementation Guidance

The parser policy is implemented as a pre-validation step before JSON Schema validation:

```
load_json() -> detect_schema_version() -> parser_policy_check() -> json_schema_validate()
```

If `schema_version` is missing, the parser inserts `schema_version: 1` into the in-memory document before passing it to JSON Schema validation, and records the deprecation warning.

## Fixture Vectors

| Fixture | Expected Parser Behavior |
|---|---|
| `dataset-config.valid.json` | Passes strict schema validation. |
| `dataset-config.missing-schema-version.json` | Passes with deprecation warning. |
| `dataset-config.future-version.json` | Fails with `"unsupported schema_version 99"`. |
