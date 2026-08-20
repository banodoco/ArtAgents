# Debugging Astrid projects and renderers

Start with the project health and recovery checks below. The renderer notes
then cover the same failure-first approach for a local backend. Normative
renderer wire details live in [render-backend-v1.md](../contracts/render-backend-v1.md).

## 1. Project health and recovery

Use the read-only doctor first, with a disposable or explicit projects root:

```bash
python3 -m astrid doctor --json --projects-root ./projects
```

Treat `schema_versions: fail` as a migration or schema incompatibility, and
`unavailable` as a local service or owner-lock condition. Keep the original
project unchanged while selecting a compatible checkout or retrying after the
owner exits. A stale timeline save is expected to return
`timeline_version_conflict` over HTTP 409 or `stale_version` through the SDK;
reload the current version, merge the draft, and retry the compare-and-swap
save.

For media integrity failures, `media verify` is a read-only check. Missing or
mutated bytes are rejected consistently and currently surface as
`internal_error` in the public envelope; restore or re-import the exact bytes
instead of editing the digest path. For an interrupted restore, repeat the
restore command or restart the bridge. The durable restore journal is read
before writer construction, so recovery publishes only a complete old or new
state.

```bash
python3 -m astrid media verify M_01ABC --project demo \
  --realm managed_local --json
python3 -m astrid backup restore ./backup --projects-root ./projects
python3 -m astrid serve --projects-root ./projects --no-open-editor
```

## 2. Local renderer debugging

Keep renderer work local and deterministic. Validate the request and output
shape before investigating backend behavior, retain redacted logs, and never
publish a sidecar until the output exists, is non-empty, and matches its
declared hash/profile. A renderer failure is not a project save failure: keep
the timeline and its draft, inspect the failure record, and retry only after
the reported input or binary condition is corrected.

The structured renderer failure kinds are:

| kind | Meaning | Typical fix |
|---|---|---|
| `protocol` | Missing or malformed result | Re-read the request and result schema. |
| `unsupported` | The request is not supported | Choose a supported input or fallback. |
| `binary_missing` | A required local binary is absent | Install or configure that binary. |
| `timeout` | The deadline expired | Shorten the work or raise the explicit deadline. |
| `interrupted` | The host cancelled the run | Retry after the host is stable. |
| `invalid_artifact` | Output is missing, empty, escaping, or hash-mismatched | Fix the output path and digest. |
| `internal` | Unexpected backend failure | Preserve the redacted log and fix the backend. |

## 3. SDK-level diagnostics

A backend written against the rendering SDK can use `astrid.support(...)` for
a request-sensitive support report and `astrid.render(...)` for a local render.
`RenderContext.run(..., check=False)` returns a bounded subprocess result, and
`RenderContext.log`/`progress` keeps diagnostics redacted. The full SDK example
is in [reference/sdk.md](../reference/sdk.md).

For any project-facing failure, return to `doctor --json`, inspect the typed
error envelope, and preserve the old state until a complete replacement is
available.
