# Astrid Bridge Contract v10 (repository-backed)

**Contract status:** frozen for milestone m1 (Sprint 1).

**Normative sources:** `unified-data-model-plan-v10-20260813.md` §4.2 (SDK and bridge) and §2.3 (timeline CAS); the checked-in server behavior in `astrid/core/integrations/reigh/local_bridge_server.py`; the m1 plan `m1-event-core-and-20260814-2340`.

**Scope:** the HTTP wire contract between the Reigh editor and the repository-backed Astrid bridge. This document is the single source of truth for every route, method, request/response field, status, error envelope, header, Range/HEAD behavior, and versioning rule. Internal repository details (receipts, events, sequences) never appear in any response.

**Backing store:** `${ASTRID_PROJECTS_ROOT}/.astrid/astrid.sqlite3` (see `docs/astrid-v10-implementation-decisions.md` §5). The bridge is repository-backed only; it has no fallback to file/JSONL/FSA/Supabase authorities and no supported route imports or calls them.

---

## 1. Routes and methods

| Route | Method(s) | Purpose |
|---|---|---|
| `/health` | `GET` | liveness + resolved projects root |
| `/routes` | `GET` | machine-readable route, payload, and ownership discovery |
| `/projects` | `GET` | sorted project list |
| `/projects/:slug/timelines` | `GET` | timeline discovery list for one project |
| `/projects/:slug/timelines/:ref` | `GET` | load one timeline (config + registry + version) |
| `/projects/:slug/timelines/:ref/save` | `POST` | whole-document CAS save |
| `/projects/:slug/timelines/:ref/assets/:key` | `GET`, `HEAD` | asset byte serving with Range support |
| any path | `OPTIONS` | CORS preflight (204) |

`:slug` is a validated project slug. `:ref` is a timeline address: canonical UUID, lowercase 26-character ULID, or immutable slug (see §8). `:key` is an asset key resolved from the persisted timeline asset registry.

Route grammar: exactly the segments above. Any other path returns 404 with the `not_found` envelope.

### 1.1 `GET /routes`

Returns a small machine-readable discovery document so an editor agent does
not need to guess route verbs, save payloads, or asset-key semantics. The
document includes the resolved `projects_root`, the exclusive database
ownership implication while `astrid serve` is running, the canonical routes,
and the whole-document save request shape. Asset URLs use the `{registry_key}`
under `registry.assets`; that key is not the entry's `media_id`.

## 2. Common behavior

### 2.1 JSON envelope

All JSON responses use `Content-Type: application/json`, `Cache-Control: no-store`, and UTF-8 bodies.

### 2.2 Error envelope

Every error response is a JSON object with exactly:

```json
{"error": "<code>", "detail": "<human-readable string>"}
```

Status-specific additions:

- `409 timeline_version_conflict` adds `"config_version": <integer current head>`.
- `422 schema_incompatible` adds `"issues": [{"pointer": "", "code": "schema_incompatible", "message": "<detail>"}]`.

Internal receipt fields — `txn_id`, `request_hash`, `idempotency_key`, `project_seq` range, `event_ids_json`, `result_json`, and any event or sequence data — are **never** serialized into any response (receipt secrecy, §7).

### 2.3 CORS

Only for an allowed `Origin` (exact match):

- Allowed origins: `http://localhost:2222`, `http://localhost:3000`, `http://localhost:5173`, `http://127.0.0.1:2222`, `http://127.0.0.1:3000`, `http://127.0.0.1:5173`.
- Response headers when the origin matches:
  - `Access-Control-Allow-Origin: <origin>`
  - `Access-Control-Allow-Methods: GET, HEAD, POST, OPTIONS`
  - `Access-Control-Allow-Headers: Content-Type, Range, If-None-Match, If-Modified-Since`
  - `Access-Control-Expose-Headers: Accept-Ranges, Content-Length, Content-Range, Content-Type, ETag, Last-Modified`
  - `Access-Control-Max-Age: 86400`
  - `Vary: Origin`
- Non-matching or absent `Origin`: no CORS headers are emitted.

### 2.4 Cache headers

- JSON routes: `Cache-Control: no-store` on every response (including errors).
- Asset routes: `Cache-Control: private, no-cache`.
- `304` responses carry `ETag`, `Last-Modified`, and `Cache-Control: private, no-cache`.

## 3. `GET /health`

- `200`:

```json
{"ok": true, "projects_root": "<resolved absolute projects root>"}
```

## 4. `GET /projects`

- `200`:

```json
{"projects": [{"slug": "<slug>", "name": "<name>"}]}
```

- Rows are sorted by `slug` ascending; a root with no projects returns `{"projects": []}`.

## 5. Project and timeline reads

### 5.1 `GET /projects/:slug/timelines`

- `200`:

```json
{"timelines": [{"timeline_id": "<uuid>", "timeline_ulid": "<ulid>", "slug": "<slug>", "name": "<name>", "is_default": <bool>}]}
```

- Rows are sorted deterministically; a project with no timelines returns `{"timelines": []}`.
- `400 invalid_project` — `:slug` fails slug validation.
- `404 project_not_found` — the project does not exist (never an empty authority-dependent view).

### 5.2 `GET /projects/:slug/timelines/:ref`

- `200` — the full load payload:

```json
{
  "timeline_id": "<uuid>",
  "timeline_ulid": "<ulid>",
  "slug": "<slug>",
  "name": "<name>",
  "is_default": <bool>,
  "config": { "...": "loose editor config object" },
  "registry": { "assets": { "...": "asset registry entries" } },
  "config_version": <integer>
}
```

- `config_version` is the numeric timeline stream head (see §6). `config` is a loose object (the editor's config is a superset); `registry.assets` is an object.
- `400 invalid_project`, `400 invalid_timeline` — invalid `:slug` or `:ref` grammar.
- `404 project_not_found`, `404 timeline_not_found` — missing project or timeline.

## 6. `POST /projects/:slug/timelines/:ref/save`

### 6.1 Request body

```json
{
  "config": { "...": "object" },
  "registry": { "...": "object" },
  "expected_version": <integer>
}
```

- `config` must be a JSON **object**; `registry` must be a JSON **object**; `expected_version` must be a JSON **integer**.
- **Numeric version rule:** `expected_version` is integer-only. JSON booleans are rejected (a boolean is not a version). The integer is opaque to the editor, but on the server it equals the timeline stream head (`event_streams.head_seq`); a successful save advances the head by exactly one and returns the new head as `config_version`.
- No `idempotency_key` field exists on this route. The bridge derives an internal idempotency key from timeline identity, `expected_version`, and the canonical save payload, and commits the normal internal receipt; no new receipt field is returned (receipt secrecy, §7).

### 6.2 Responses

- `200` — the committed payload, same shape as the load payload (§5.2) with the **new** `config_version`.
- `400 invalid_body` — body is not valid JSON or not an object.
- `400 invalid_config` — `config` missing or not an object.
- `400 invalid_registry` — `registry` missing or not an object.
- `400 invalid_expected_version` — `expected_version` missing or not an integer.
- `400 invalid_project` / `400 invalid_timeline` — invalid `:slug` / `:ref` grammar.
- `404 project_not_found` — project missing.
- `404 timeline_not_found` — timeline missing.
- `409 timeline_version_conflict` — `expected_version` is stale; response adds `"config_version": <current head>`. Zero database mutation occurs (document, registry, events, heads, receipts all unchanged).
- `422 schema_incompatible` — config/registry validation fails; response adds `issues[]` (see §2.2). A schema rejection is a typed 422, never a connection-close 500.

### 6.3 Atomicity

A successful save atomically updates `document_json` + `asset_registry_json`, appends one `timeline.saved` event, advances the timeline stream head (and project head), and writes the internal receipt in one `BEGIN IMMEDIATE` transaction (v10 §2.3). Concurrent saves from one expected head yield exactly one success and one `409`; no SQLite busy error or losing receipt is exposed.

## 7. Receipt secrecy

Internal command receipts are never exposed on any route:

- Not in save responses (which return only the frozen load shape), not in error bodies, not in headers, not in `OPTIONS`.
- Prohibited in responses: `txn_id`, `request_hash`, `idempotency_key`, `first_project_seq`, `last_project_seq`, `event_ids_json`, `result_json`, and any event/stream sequence data.
- Explicit keys and receipts are CLI/SDK behavior only (v10 §4.2).

## 8. Timeline addresses

`:ref` accepts, in order of validation:

1. canonical lowercase UUID (`8-4-4-4-12` hex groups),
2. lowercase 26-character Crockford ULID,
3. immutable project-scoped slug.

Resolution is repository-driven (UUID/ULID/slug within the project); a `:ref` matching none of the forms yields `400 invalid_timeline`.

## 9. Asset serving: `GET`/`HEAD /projects/:slug/timelines/:ref/assets/:key`

Asset keys resolve **only** from the persisted timeline asset registry; a locator is a locator, never media identity. Local paths are served only after safe-path checks.

### 9.1 Headers

Every asset response (200/206/304/416) emits CORS headers when allowed, plus:

- `Content-Type` (from the file, defaulting to `application/octet-stream`),
- `Accept-Ranges: bytes`,
- `Cache-Control: private, no-cache`,
- `ETag` and `Last-Modified` derived from file identity.

### 9.2 Status codes

| Condition | Status | Notes |
|---|---|---|
| No `Range`; full body ≤ limit | `200` | full body with `Content-Length` |
| No `Range`; `If-None-Match` matches ETag | `304` | no body; ETag/Last-Modified/Cache-Control present |
| No `Range`; full body > limit | `206` | initial chunked range with `Content-Range` |
| Single valid `Range` | `206` | `Content-Range: bytes <start>-<end>/<total>`; single range only |
| Malformed `Range` header | `400` | `text/plain` body (`invalid Range header` / `empty Range`), no CORS promise |
| Unsatisfiable range (start ≥ size, end < start, suffix ≤ 0) | `416` | `Content-Range: bytes */<size>`, `Content-Length: 0` |
| Missing registry key, missing file, or HTTP-only asset | `404` | `asset_not_found` (missing/unresolvable) or `asset_not_local` (HTTP-only) |

### 9.3 Range grammar

- Single range only: `bytes=<start>-<end>`, `bytes=<start>-` (open-ended), `bytes=-<N>` (suffix, last N bytes).
- `end` values beyond the file size clamp to `file_size - 1`.
- Multiple ranges, non-`bytes` units, and empty ranges are malformed → `400`.
- `HEAD` behaves exactly like `GET` for status and headers, with no response body.

## 10. `OPTIONS`

- `204` with CORS headers (§2.3) and `Content-Length: 0`; no body.

## 11. Reserved route — `POST /projects/:slug/timelines/:ref/copy` (planned m6, NOT implemented in m4)

**Status: reserved contract only.** The save-as-copy route is documented in m4
(`docs/astrid-v10-implementation-decisions.md` §16, CF-08C82BBD608F2CCF8A7E /
CF-F0DB9D4F2A612C886B3B) and **implemented in m6**. In m4:

- The route is **not registered**. `POST /projects/:slug/timelines/:ref/copy`
  resolves through the existing route grammar in §1: "any other path returns
  404 with the `not_found` envelope" (and `POST` falls under the same rule —
  "unknown POST route → 404").
- No `timelines copy` CLI verb is registered.

**Planned m6 semantics (frozen now, implemented later):**

- **Request body:** optional target name (object; may be empty/absent).
- **Idempotency key:** deterministic derived key from source timeline identity
  + source head + canonical copy payload.
- **CAS on the source head:** a stale source head returns
  `409 timeline_version_conflict` with the current head and zero database
  mutation.
- **Response:** the new timeline row — fresh id, `config_version` 0, and
  `copied_from` recorded in the `timeline.created` event payload.
- **Error mapping:** 404/409/422 per the frozen bridge error vocabulary
  (§2.2).
- **Receipt secrecy:** the response never exposes a receipt or idempotency key
  (§7).

## 12. In-tree provider-contract client — m1 substitute

- m1 ships an in-tree, field-for-field client matching the recorded `AstridBridgeDataProvider` list/load/save/reload contract, including stale-save `409` observation and save retention across HTTP server and database restart.
- The in-tree client is an **m1 substitute**, not editor-source parity. The real out-of-tree TypeScript `AstridBridgeDataProvider` suite is a hard named follow-up gate (NSA-1; `docs/astrid-v10-implementation-decisions.md` §3, §11, and §14). Nothing in this contract claims browser or provider-source parity for the substitute.
