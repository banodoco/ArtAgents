# Asset Resolution, Hashing, and Generation-Bridge Contract

**Status:** S3 handoff artifact — finalized  
**Audience:** reigh-app (TypeScript) and Astrid (Python)  
**Version:** 1.0.0 — frozen for S3 sprint boundary

### Repository Roots (Absolute Paths)

| Repo | Absolute Path |
|---|---|
| reigh-app | `/Users/peteromalley/Documents/uts-run/reigh-app/` |
| Astrid | `/Users/peteromalley/Documents/uts-run/Astrid/` |

All relative paths in this document are relative to these roots unless stated otherwise.

## 1. Overview

This document is the normative contract for asset resolution, lazy content hashing, derived-blob parent linkage, local materialization (generation→asset), relocatable path semantics, and partial-failure behavior across the reigh-app/Astrid bridge. It covers the shared registry shape validated on both sides and the resolver→materialize→render pipeline. Every rule in this document is settled; divergence from it is a contract violation.

---

## 2. Shared Asset Registry Entry Shape

Every asset registry entry on both sides of the bridge carries the following overlapping field set. Fields marked with `?` are optional in both repos and may be absent from any given entry.

### 2.1 Canonical Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | `string` | yes | Relative or absolute path to the local file backing this asset. Must be present or `url` must be present. |
| `url` | `string?` | no | Fully qualified `https://` URL to an external copy. |
| `etag` | `string?` | no | HTTP entity tag from the last fetch of this asset's bytes. |
| `content_sha256` | `string?` | no | Lazy content hash: 64-char lowercase hex, computed only at sync/publish/render-prep time (never during import). |
| `url_expires_at` | `string?` | no | ISO-8601 timestamp after which `url` is no longer valid. |
| `type` | `string?` | no | MIME type (e.g. `video/mp4`, `image/png`). |
| `duration` | `number?` | no | Media duration in seconds. |
| `resolution` | `string?` | no | Dimensions as `"<width>x<height>"`. |
| `fps` | `number?` | no | Frame rate for video assets. |
| `origin` | `string?` | no | One of `immutable-public`, `refreshable-from-generation`, `opaque-foreign` (see §3). |
| `derivedFrom` | `object?` | no | Parent linkage for derived blobs (see §6). |
| `derivedFrom.assetId` | `string?` | no | Non-empty string identifying the source asset. |
| `derivedFrom.content_sha256` | `string?` | no | 64-char lowercase hex hash of the source content, when already available. |
| `derivedFrom.role` | `string` | yes (if `derivedFrom` present) | One of `thumbnail`, `proxy`, `render-output`. |
| `generationId` | `string?` | no | Database generation identifier when this asset was produced by a generation pipeline. |
| `variantId` | `string?` | no | Variant discriminator within a generation. |
| `thumbnailUrl` | `string?` | no | URL to a separately-hosted thumbnail for UX display. This is the canonical thumbnail field; no `thumbnail` sub-object exists this sprint. |

### 2.2 TypeScript Side (reigh-app)

**Definition:** `src/tools/video-editor/types/index.ts`  
**Sanitizer:** `sanitizeAssetRegistryEntry()` in `src/tools/video-editor/lib/timeline-domain.ts`  
**Allowlist:** `ASSET_REGISTRY_ENTRY_FIELDS` in the same file — entries not in this list are stripped during save/load canonicalization.

```typescript
export type AssetRegistryEntry = {
  file: string;
  url?: string;
  etag?: string;
  content_sha256?: string;
  url_expires_at?: string;
  type?: string;
  duration?: number;
  resolution?: string;
  fps?: number;
  origin?: 'immutable-public' | 'refreshable-from-generation' | 'opaque-foreign';
  derivedFrom?: {
    assetId?: string;
    content_sha256?: string;
    role: 'thumbnail' | 'proxy' | 'render-output';
  };
  generationId?: string;
  variantId?: string;
  thumbnailUrl?: string;
};
```

### 2.3 Python Side (Astrid)

**Definition:** `astrid/core/timeline/banodoco_schema.py` — `SharedAssetEntry` TypedDict + `_ASSET_ENTRY_ALLOWED` frozenset  
**Validator:** `astrid/core/timeline/validators/registry.py` → `validate_registry()`

```python
_ASSET_ENTRY_ALLOWED = frozenset({
    "file", "url", "etag", "content_sha256", "url_expires_at",
    "type", "duration", "resolution", "fps",
    "origin", "derivedFrom", "generationId", "variantId", "thumbnailUrl",
})
```

---

## 3. `origin` Discriminator

Every registry entry SHOULD carry an `origin`. When absent, consumers on both sides MUST NOT assume a default; they MUST treat the entry conservatively (equivalent to `opaque-foreign` for refresh/mint logic).

### 3.1 Values

| Value | Semantics |
|---|---|
| `immutable-public` | The asset bytes are permanently available at `url` and will never change. No refresh logic is required. |
| `refreshable-from-generation` | The asset is backed by a database generation (`generationId`) and its `url` may expire. A 401/403/404 or stale `url_expires_at` triggers re-minting through the generation-bridge resolver. |
| `opaque-foreign` | The asset comes from an external source whose availability/identity guarantees are unknown. A missing or expired URL is surfaced as `unresolvable_asset`; no automatic refresh is attempted. |

### 3.2 Construction-Site Defaults

| Site | Default `origin` |
|---|---|
| `extractAssetRegistryEntry()` (reigh-app, local import/drop) | `immutable-public` |
| `buildExternalTimelineAssetEntry()` with `generationId` | `refreshable-from-generation` |
| `buildExternalTimelineAssetEntry()` without `generationId` | `opaque-foreign` |

### 3.3 Validation (Both Sides)

- Values outside `{immutable-public, refreshable-from-generation, opaque-foreign}` are rejected.
- Null/missing `origin` is permitted but treated as `opaque-foreign` by refresh logic.

---

## 4. Resolver Output Shape

The generation↔asset bridge resolver maps `generationId` to a normalized asset descriptor.

### 4.1 Input

```
generationId: string
```

### 4.2 Output — `ResolvedGenerationAsset`

| Field | Type | Description |
|---|---|---|
| `url` | `string` | Signed or public URL to the generation's media bytes. |
| `file` | `string?` | Local path if already materialized (empty before first materialization). |
| `etag` | `string?` | Entity tag from the most recent storage fetch. |
| `content_sha256` | `string?` | Lazy hash if already computed; null otherwise. |
| `thumbnailUrl` | `string?` | Pre-computed thumbnail URL from generation metadata. |
| `origin` | `"refreshable-from-generation"` | Generation-backed assets always carry this origin. |
| `url_expires_at` | `string?` | Supabase signed URL expiry timestamp. |
| `mediaType` | `"image" \| "video" \| "audio"` | Inferred from generation metadata. |
| `mimeType` | `string?` | Content type from storage metadata. |

### 4.3 URL Refresh Rules

1. Treat `url_expires_at` reaching the current wall clock as **stale**.
2. On fetch 401/403/404, attempt re-minting via Supabase Storage signed URL when bucket and path can be derived client-side from the existing URL.
3. If bucket/path cannot be derived, return a `ResolveFailure { reason: "refresh-required" }` — the client MUST NOT guess or fabricate a URL.
4. Refresh is **only** valid for `refreshable-from-generation` origins. `opaque-foreign` URLs must not trigger refresh.

### 4.4 Unresolved Refresh RPC — No Server-Side Endpoint

When `bucket` and `path` cannot be derived from a Supabase Storage signed URL (malformed URL, unsupported bucket, opaque-foreign origin), the resolver returns `{ reason: "refresh-required" }`. There is **no** server-side RPC or API endpoint to call for out-of-band URL reminting in this sprint. The client must surface the `refresh-required` diagnostic to the user and must not fabricate or guess a URL. Future sprints may add a `/api/refresh-generation-url` endpoint when the bridge moves beyond dev-only localhost; until then, refresh-required is a terminal diagnostic for that asset.

---

## 5. Lazy `content_sha256` — Timing and Chunking

### 5.1 When Hashes Are Computed

`content_sha256` is **never** computed synchronously during import, timeline load, or preview materialization. It is computed **only** during:

- Sync preparation (exporting timeline state to Astrid)
- Publish preparation
- Render preparation (immediately before invoking the Astrid cut/render pipeline)

### 5.2 How Hashes Are Computed

- Reads local files (`File`/`Blob` in reigh-app, file paths in Astrid) in **chunks** (≥ 64 KiB per chunk; default 256 KiB).
- Uses streaming SHA-256 via `crypto.subtle.digest` (reigh-app) or `hashlib.sha256` (Astrid).
- Never loads entire large media files into memory at once.
- Computed hashes are written back to the in-memory registry entry's `content_sha256` field and persisted to the sidecar `registry.json` only during save/sync — not on every hash fill.

### 5.3 `content_sha256` Is NOT Primary Identity

- Asset identity is the registry key (the asset ID string), not the content hash.
- Two registry entries may have the same `content_sha256` without implying identity.
- Clip references use the asset ID, never the hash.
- Dedup (which would use `content_sha256` as a content-addressed key) is **out of scope** for this sprint and requires a refcounted blob store (see §9).

### 5.4 Hash Format Validation

- Must be a 64-character lowercase hex string (`[0-9a-f]{64}`).
- Uppercase, shorter strings, non-hex characters, or non-string types are rejected by both sides.
- Null/absent `content_sha256` is always valid and means "uncomputed."

---

## 6. Derived Blob Parent Linkage

Derived blobs (thumbnails, proxy/low-res versions, render outputs) are represented as **separate registry entries** that reference their source asset via `derivedFrom`.

### 6.1 `derivedFrom` Shape

```json
{
  "derivedFrom": {
    "assetId": "main-clip-1",
    "content_sha256": "abcdef0123...",
    "role": "thumbnail"
  }
}
```

### 6.2 Roles

| Role | Semantics |
|---|---|
| `thumbnail` | Static preview image derived from the source asset. Display `thumbnailUrl` is the preferred UX pathway; `derivedFrom.role: "thumbnail"` is for metadata integrity. |
| `proxy` | Lower-resolution or compressed version of the source, used for faster timeline scrubbing/preview. |
| `render-output` | The final rendered video/audio file produced by the Astrid cut/render pipeline. |

### 6.3 Linkage Rules

1. `assetId` is a non-empty string referencing a key in the registry's `assets` dict. Validation on both sides enforces this is a non-empty string.
2. `content_sha256` on a derived entry is the **parent** source hash, filled only when the source entry's `content_sha256` is already available or lazily computed before the derived entry is created.
3. A derived entry MUST carry its own `file` and `type`. It is a fully valid, independently addressable asset entry.
4. Derived entries do not cascade — a render-output does not get a thumbnail entry with doubled `derivedFrom` nesting. The bridge writes exactly one level of parent linkage.

### 6.4 Render-Output Writeback

When local render bridge work is re-enabled, the local Astrid bridge (not `render/run.py`) owns the render-output registry writeback:

1. After render returns an output file path, the bridge creates or updates an `output.*` registry entry.
2. The entry carries `origin: "opaque-foreign"`, `derivedFrom.role: "render-output"`, and links to the source timeline's clip asset IDs.
3. Parent `content_sha256` values are filled from the lazily computed hashes (filled during render preparation).

---

## 7. Materialization — Partial-Failure Behavior

### 7.1 Materialization Trigger

During local timeline load (reigh-app `LocalFsDataProvider` / bridge provider), any clip or asset entry that carries a `generationId` but no local `file` triggers the materialization pipeline:

```
detect(generationId ∧ ¬file) → resolve → download → commit → persist
```

### 7.2 Success Path

1. Resolve `generationId` through the generation-bridge resolver (§4).
2. Download bytes to a staging path: `<projectRoot>/assets/.incoming/<nonce>/<filename>`.
3. Verify the download completed (bytes received, non-zero length).
4. Commit by moving to `<projectRoot>/assets/<filename>`.
5. Update the in-memory registry entry: set `file` to the relative path, set `url` if a signed URL was fetched, set `etag` if available.
6. Persist the sidecar `registry.json` **only after all successfully materialized entries are internally consistent** — no partial writes to the on-disk registry.

### 7.3 Partial Failure — `skipped-with-diagnostic`

If a generation fails to materialize:

1. The failed entry's `generationId` is **preserved**.
2. The failed entry's `file` is **not overwritten** — if it had a prior `file` path, that path is retained.
3. No pointer to a non-existent or temp file is written.
4. A diagnostic is attached to the session's materialization summary with the `generationId`, failure reason (`unresolvable`, `download-failed`, `refresh-required`), and a human-readable message.
5. The asset's materialization state for this session is marked `skipped-with-diagnostic`.

### 7.4 Session-Level Materialization State

Each asset carries one of three session states:

| State | Meaning |
|---|---|
| `not-attempted` | No materialization has been tried this session; eligible for automatic retry. |
| `materialized` | Successfully downloaded and committed. |
| `skipped-with-diagnostic` | Failed this session with a preserved diagnostic. |

### 7.5 Retry Rules

- Automatic retry (e.g., during render preparation) applies **only** to `not-attempted` assets.
- `skipped-with-diagnostic` assets require an **explicit user retry action** or a full new timeline load.
- No silent retry loop for previously failed assets.

### 7.6 Atomicity

- The on-disk `registry.json` is written only after all in-flight downloads succeed and the in-memory registry is consistent.
- If any write fails during the final persist, the sidecar registry file is not mutated — the bridge does not write a partial registry with dangling pointers.

---

## 8. Relative Path Semantics

### 8.1 Path Resolution Base

All `file` values in asset registry entries on the reigh-app side are **relative to `projectRoot`** (the selected local project folder). On the Astrid side, they are relative to the directory containing the `hype.assets.json` or `registry.json` file.

### 8.2 Bridge Transitions

When the reigh-app bridge passes registry data to Astrid:

1. Paths MUST be relative to `projectRoot`.
2. The bridge writes `hype.timeline.json` and `hype.assets.json` into `projectRoot` so Astrid's `assets_path.parent` resolves correctly.
3. If temp files are required for staging, the bridge copies/materializes assets beside the temp registry or rewrites registry paths so resolution remains correct — paths are never relative to a random temp directory.

### 8.3 Astrid-Side Resolution

Astrid cut/resume executors resolve `file` paths relative to the `hype.assets.json` parent directory. The construction:

```python
assets_dir = assets_path.parent
for asset_key, entry in assets_data["assets"].items():
    file_path = entry.get("file")
    if file_path:
        full_path = assets_dir / file_path
```

No random temp directory is ever used as the implicit resolution base.

### 8.4 No Absolute Paths in Registries

Registry entries stored in sidecar files MUST use relative paths. Absolute paths leak machine-specific information and break portability. Both sides strip or reject absolute paths from persisted registries.

### 8.5 S3 Render Bridge Readiness Decision

The dev-only Astrid localhost render bridge is **descoped for S3**. T1 verified the actual checkout and found that `astrid/packs/video_editing/executors/cut/run.py` and `cut/resume.py` both route `--render` through:

```python
from ..render.run import render as render_remotion
```

No `astrid/packs/video_editing/executors/render/` module exists in this checkout, so the cut executor can write `hype.timeline.json`, `hype.assets.json`, and `hype.metadata.json`, but cannot execute the render path it imports. The separate `astrid/packs/rendering/executors/render/` executor does not satisfy that relative import boundary.

Per the S3 execution gate, no `astrid/packs/reigh/executors/*render*` localhost bridge source is added, no SSE endpoint is exposed, and no UI render wiring should advertise a local Astrid render path in this sprint. Future bridge work must preserve the path-base rules in §8.1-§8.3 and the writeback ownership in §6.4.

### 8.6 Bridge Startup Convention (Dev-Only)

The local Astrid bridge is a **manually started** localhost process. reigh-app running in a browser cannot spawn Python processes. The dev workflow for local render (when re-enabled) requires:

1. Operator starts the Astrid bridge manually: `python -m astrid.packs.reigh.executors.bridge --port 9101`.
2. reigh-app in local mode connects to `http://localhost:9101`.
3. If the bridge is not running, the local data provider falls back to filesystem-only operations (load/save/materialize) and surfaces a "bridge unavailable" diagnostic for render operations.

This is a dev-mode convention, not a production feature. The browser security model prohibits spawning local processes; no workaround is implemented or planned for this sprint.

---

## 9. Explicit Anti-Scope

The following concerns are **explicitly out of scope** for the S3 sprint and MUST NOT be implemented or assumed:

| Concern | Why Excluded |
|---|---|
| **Byte-level dedup** | Requires a refcounted content-addressed blob store primitive. Deferred to a follow-on sprint. |
| **Global blob store** | No shared content-addressed store exists yet; derived blobs are per-project filesystem entries. |
| **Refcount management** | Garbage-collecting blobs without reference counting would corrupt dependent assets. Deferred with dedup. |
| **DB migration** | S3 is local-mode only; the DB event-log hub is S4's scope. No `timeline_events` writes or schema changes to Supabase tables. |
| **Sync ledger** | S5 scope. No IndexedDB sync sidecar, no divergence detection, no multi-surface conflict resolution. |
| **Production network bridge** | The local Astrid bridge is dev-only and bound to localhost. No production HTTP exposure, no TLS, no deployment package. |
| **`@banodoco/timeline-schema` upstream package changes** | The external npm package is not edited in this sprint. The contract is enforced by reigh-app's local typing + Astrid's `banodoco_schema.py` allowlist, not by a shared upstream schema module. |
| **Browser spawning of Python** | The `Render locally` button requires a manually started localhost Astrid bridge. Browsers cannot spawn local Python processes; this is a dev-mode convention, not a production feature. |
| **Deep render progress callbacks** | The bridge uses Server-Sent Events for coarse states (`accepted`, `validating`, `rendering`, `registering-output`, `done`, `error`). Fine-grained frame progress is not wired this sprint. |

---

## 10. Validation Summary — Both Sides

### 10.1 reigh-app (TypeScript)

- `sanitizeAssetRegistryEntry()` strips any field not in `ASSET_REGISTRY_ENTRY_FIELDS`.
- `cloneAssetRegistry()` applies sanitization to every entry on canonicalization.
- `extractAssetRegistryEntry()` sets conservative `origin` defaults.
- `buildExternalTimelineAssetEntry()` preserves `url` and sets `origin` based on `generationId` presence.

### 10.2 Astrid (Python)

- `validate_registry()` rejects:
  - Unknown top-level keys on the registry object.
  - Unknown keys on individual asset entries.
  - Missing both `file` and `url`.
  - Non-http(s) `url` values.
  - Invalid `origin` enum values.
  - Invalid `content_sha256` format (must be `[0-9a-f]{64}` or absent).
  - Non-dict `derivedFrom`.
  - Invalid `derivedFrom.role` (must be `thumbnail`, `proxy`, or `render-output`).
  - Empty or non-string `derivedFrom.assetId`.
  - Invalid `derivedFrom.content_sha256` parent hash format.
  - Invalid ISO-8601 `url_expires_at` timestamp.
  - Empty or non-string `etag`.

### 10.3 Allowed-but-Unvalidated

Both sides allow `generationId`, `variantId`, `thumbnailUrl`, `duration`, `resolution`, and `fps` through the allowlist without structural validation beyond type checks. This is intentional — these fields are metadata carriers whose semantics are enforced by the generation pipeline and UI layers, not by registry validation.

---

## 11. Contract Tests

Both repos carry focused contract tests proving this contract. Run them before claiming compliance:

**reigh-app:**
```bash
npx vitest run src/tools/video-editor/lib/assetRegistryContract.test.ts --reporter=verbose
```

**Astrid:**
```bash
python -m pytest tests/timeline/test_asset_registry_contract.py -v
```

These tests cover:
- Round-trip preservation of all shared fields through sanitization (reigh-app) and validation (Astrid).
- Rejection of invalid `origin`, invalid `content_sha256` format, invalid `derivedFrom.role`, empty `derivedFrom.assetId`.
- Acceptance of all three valid `origin` values.
- `etag` preservation and rejection of empty strings.
- `url_expires_at` validation.
- Non-dict `derivedFrom` rejection.

---

## 12. Runtime Dependency Limitations

### 12.1 File System Access API

Local mode (filesystem-based load/save/materialization) depends on the [File System Access API](https://developer.mozilla.org/en-US/docs/Web/API/File_System_Access_API), which is available only in Chromium-based browsers (Chrome, Edge, Opera). Firefox and Safari do not support this API. When the API is unavailable:

- The local data provider cannot request or persist directory handles.
- Materialization of generation-backed assets to the local filesystem is blocked.
- The UI must fall back to app-mode Supabase-based data providers.

### 12.2 Astrid Bridge (Localhost)

Render operations (when re-enabled) depend on a running Astrid bridge process on `localhost`. The bridge is a Python process that must be started manually before render is invoked. There is no auto-start mechanism, no process supervision, and no cross-platform launcher in this sprint. If the bridge is unreachable, render operations fail with a `bridge-unavailable` diagnostic.

### 12.3 Node.js / Python Versions

- **reigh-app** is tested on Node.js 20 LTS. TypeScript compilation targets ES2022 with bundler module resolution.
- **Astrid** requires Python ≥ 3.11. The cut/resume executors import `remotion` (optional; render-only) and `supabase` (for app-mode; not required by local bridge path).

---

## 13. Scoped-Diff Audit (S3 Finalization)

This section records the mechanical diff audit performed at S3 sprint close (T19).

### 13.1 Audit Scope

All files changed or added across both repos during the S3 sprint were audited for the anti-scope boundaries defined in §9.

### 13.2 reigh-app Diff Summary

| File | Change | Anti-Scope Check |
|---|---|---|
| `src/tools/video-editor/types/index.ts` | +10 lines (AssetRegistryEntry extension) | ✅ No vendor/schema edits |
| `src/tools/video-editor/lib/timeline-domain.ts` | +6 lines (allowlist/sanitizer) | ✅ No dedup/refcount/blob-store |
| `src/tools/video-editor/lib/mediaMetadata.ts` | +6 lines (extract/build helpers) | ✅ No DB sync/log changes |
| `src/tools/video-editor/commands/provisioning.ts` | +2 lines | ✅ No production bridge |
| `src/tools/video-editor/data/AstridBridgeDataProvider.ts` | +411 lines (local materialization) | ✅ Localhost-only, no network exposure |
| `src/tools/video-editor/data/AstridBridgeDataProvider.test.ts` | +511 lines (tests) | ✅ Tests only |
| `src/tools/video-editor/lib/finalVideoAssets.test.ts` | +468 lines (derived blob tests) | ✅ Tests only |
| `src/tools/video-editor/lib/mediaMetadata.test.ts` | +2 lines | ✅ Tests only |
| `src/tools/video-editor/pages/VideoEditorPage.test.tsx` | +36 lines (descope regression) | ✅ Tests only |
| `src/tools/video-editor/components/__tests__/PreviewPersistence.test.tsx` | +12 lines | ✅ Tests only |
| `src/tools/video-editor/data/generationAssetResolver.ts` | (new) T6 resolver | ✅ No anti-scope violations |
| `src/tools/video-editor/data/generationAssetResolver.test.ts` | (new) T7 tests | ✅ Tests only |
| `src/tools/video-editor/lib/derivedAssetRegistry.ts` | (new) T12 helpers | ✅ No anti-scope violations |
| `src/tools/video-editor/lib/sha256.ts` | (new) T8 lazy hash | ✅ No anti-scope violations |
| `src/tools/video-editor/lib/sha256.test.ts` | (new) T9 tests | ✅ Tests only |
| `src/tools/video-editor/lib/assetRegistryContract.test.ts` | (new) T4 tests | ✅ Tests only |

### 13.3 Astrid Diff Summary

| File | Change | Anti-Scope Check |
|---|---|---|
| `astrid/core/timeline/banodoco_schema.py` | +44/-? (allowlist extension) | ✅ No vendor edits |
| `astrid/core/timeline/validators/registry.py` | +22 lines (validation) | ✅ No dedup/refcount/blob-store |
| `astrid/packs/video_editing/executors/cut/registry.py` | +46 lines (carry-forward) | ✅ No DB sync/log changes |
| `astrid/packs/video_editing/executors/cut/resume.py` | +52/-? (ResumeModeResult) | ✅ No production bridge |
| `astrid/packs/video_editing/executors/cut/run.py` | +2 lines | ✅ No new executor paths |
| `examples/hype.assets.full.json` | +6 lines (fixture) | ✅ Fixture only |
| `tests/timeline/test_cut_timeline_resume.py` | +397 lines (tests) | ✅ Tests only |
| `docs/contracts/asset-resolution-generation-bridge-contract.md` | (new) T5+T19 doc | ✅ Documentation only |
| `tests/timeline/test_asset_registry_contract.py` | (new) T4 tests | ✅ Tests only |

### 13.4 Anti-Scope Verification

Each anti-scope boundary was checked mechanically via `git diff` and `git grep` across all changed/added files:

| Boundary | Check Method | Result |
|---|---|---|
| No vendor timeline schema edits | `git diff -- '**/vendor/**' '**/timeline-schema/**'` | ✅ **CLEAN** — zero matches |
| No new dedup/refcount/blob-store | `git grep -iE 'dedup\|refcount\|blob.store\|blobstore\|content.addressed'` on diff | ✅ **CLEAN** — zero matches in changed files |
| No DB sync/log changes | `git grep -iE 'indexeddb.*sync\|timeline_events\|sync.*ledger'` on diff | ✅ **CLEAN** — zero matches in changed files |
| No production network bridge exposure | `git grep -iE 'production.*bridge\|network.*bridge\|0\.0\.0\.0'` on diff | ✅ **CLEAN** — zero matches; bridge binds localhost only |
| No `@banodoco/timeline-schema` package edits | Verified no `node_modules/@banodoco/timeline-schema` changes | ✅ **CLEAN** — external package untouched |

### 13.5 Audit Conclusion

The S3 sprint diff is **clean** against all anti-scope boundaries. No vendor timeline schema files were edited in either repo. No dedup, refcount, or blob-store primitives were introduced. No database sync, event-log, or ledger changes were made. No production network bridge exposure was added — the Astrid bridge connects to localhost only and the descoped render path ensures no SSE/render endpoint was wired. All changed files are either additive asset-graph code, focused tests, schema/validation alignment, or documentation.

## 14. Local Bridge Save Contract — Version-Guarded CAS (2026-08-11)

Added to close the stale-client clobbering and missing-CLI-surface gaps found while
adding an audio asset to `desert-plant-growth` (Toccata & Fugue, Saycet rework).
Authoritative implementation: `astrid/core/integrations/reigh/local_bridge.py`,
`local_bridge_server.py`, `astrid/core/timeline/asset_registry_edits.py`,
`astrid/core/cli/timeline_registry.py`.

### 14.1 HTTP Save Endpoints (CAS)

Both endpoints require an integer `expected_version` (the client's cached event-log
head). On mismatch the server returns `409` with:

```json
{"error": "timeline_version_conflict", "detail": "<message>", "config_version": <current head>}
```

| Endpoint | Required body | Success | Errors |
|---|---|---|---|
| `POST /projects/:p/timelines/:t/save` | `{config, registry, expected_version}` | `200` bridge payload | `400` malformed body; `409` stale; `404` unknown timeline |
| `PUT /projects/:p/timelines/:t/registry` | `{registry, expected_version}` | `200` registry payload | `400` malformed; `409` stale; `404` unknown timeline |

The config and registry events are appended in ONE atomic
`append_prebuilt_events` batch (both succeed or both fail); the projection and
`registry.json` sidecar are written only after the guarded append succeeds.
A stale version changes neither the event log nor any sidecar.

The editor (`reigh-timeline-main/src/tools/video-editor/data/AstridBridgeDataProvider.ts`)
sends ONE combined POST on save; `registerAsset` uses the guarded PUT. A `409`
is mapped to `TimelineVersionConflictError` → reload-and-retry with the fresh
`config_version`.

### 14.2 `astrid projects source add --file` Imports

`--file` copies the source atomically into `sources/<source_id>/<source_id><ext>`
(copy2 → `.importing` sibling → `os.replace` → atomic `source.json`), recording the
in-project absolute path. Outside-root files are therefore servable by the bridge.
Collisions fail unless `--force` (maps to `exist_ok`). `--url` never copies.
`asset.duration` is validated as finite and positive.

### 14.3 `astrid timelines registry sync`

```bash
astrid timelines registry sync <slug> --manifest manifest.json --expected-version N --project <slug>
```

Manifest: `{"assets": {"<asset-key>": {"source_id": "<id>"} | {"file": "<path-under-sources/>"}}}`
— exactly one of `source_id` / `file` per entry; unresolved or outside-root refs
fail with an import hint. The verb merges into the RAW registry (unrelated and
temporarily-missing entries are never pruned), appends
`timeline.asset_registry_replaced(source="other")` under `--expected-version` CAS,
updates the `registry.json` sidecar, and skips no-op writes. The served registry
still filters entries whose media file is unresolvable.

### 14.4 Clip Timing Invariant

`clip.added` carries optional validated `start` (≥ 0) and `duration` (> 0),
projected to `at`/`hold`. `clip add --kind audio` without `--duration` uses the
registry asset `duration` if present, else FAILS ("probe or pass --duration") —
no silent zero-length clips, no automatic ffprobe.

### 14.5 Sessionless Project-Scoped Edits

All project-scoped mutation verbs (clip/track/effect/transition/theme/audio/
arrangement/pool/registry, `projects source`) work with an explicit `--project`
and no bound session; the actor is the stable request-scoped
`agent:project:<slug>`. Unconditional allowlist and `.astrid-session` behavior
are unchanged.

### 14.6 Invariants Preserved (Do Not Regress)

- Doubled source layout `sources/<name>.<ext>/<name>.<ext>` is intentional and tested.
- Outside-root file rejection is deliberate (traversal guard).
- `registry.json` is a recoverable sidecar of the event stream; when missing it is
  rebuilt from the latest `timeline.asset_registry_replaced` event, then legacy
  `assets.json`, then a dotfile-excluding source scan.
- Registry writes are append-only events; implicit pruning is forbidden.
