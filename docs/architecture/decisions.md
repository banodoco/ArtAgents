# Sprint 0 Decisions

These decisions are part of the Sprint 0 operator contract. Later batches may
implement or test them, but should not introduce competing policies.

## DEC-001: V1 Pack Trust Boundary

V1 trusts only first-party, author-written packs in this repository. Loading a
pack can execute pack-supplied Python through runtime discovery paths, so
external or catalog-installed packs are out of scope until Astrid has a sandbox,
signing, or equivalent install-time trust story.

Implications:

- Builtin and local first-party packs may remain code-bearing capabilities.
- External/catalog pack install must not be documented as safe general input.
- Sprint 0 validation closes schema and manifest holes for first-party packs; it
  does not claim arbitrary third-party pack safety.

## DEC-002: Component Manifest Loading Policy

Component manifests are author-facing YAML/JSON documents. Runtime loaders,
direct JSON Schema validation, and pack validation must parse the same document
before and after builtin executor, orchestrator, or element `schema_version`
migrations land.

Policy:

- `.json` component manifests are strict JSON.
- `.yaml` and `.yml` component manifests are parsed with PyYAML `safe_load`.
- Runtime loaders for executors, orchestrators, and elements use the shared
  component manifest parser, not custom YAML subsets or JSON-only reads.
- Pack validation uses the same parser before validating component manifests
  against the v1 JSON Schemas.
- First-party builtin executor, orchestrator, and element manifests are
  explicitly schema-versioned with `schema_version: 1`.
- Component manifests without `schema_version` are not part of the checked
  builtin manifest set. Pack validation still selects the v1 schema for a
  missing component version only so the schema can report the same missing-field
  error that direct JSON Schema validation reports.

Parser parity is covered by glob-based tests that enumerate actual builtin
executor, orchestrator, and element manifest paths and load them through direct
schema validation, pack validation, runtime parsers, and runtime registries.
