# Live serve/editor bridge UX wave 1

Date: 2026-08-23 (Europe/Berlin)

## Scope and boundary

This was a live-agent usage pass, not a programmatic test. I started from the
public CLI census and `serve --help`, used ordinary CLI commands and `curl`,
did not open a browser, did not run pytest, and did not inspect application
source or tests. The run used a fresh isolated root:

`ASTRID_PROJECTS_ROOT=/tmp/astrid-live-serve-editor-1.SKE8Sy`

The bridge used `127.0.0.1:49994`. It was a separate process from any shared
Astrid server and was stopped with Ctrl-C; it exited 0 and printed
`Shutting down...`.

## User goal attempted

1. Created project `editor-demo` (display name `Editor Demo`).
2. Imported `tests/packs/builtin/generate_image/fixtures/tiny.png` through
   `media import`; Astrid returned media id
   `75b0a2dc-9d46-5865-a9ff-5fea61c3de44`, 69 bytes, `image/png`, with a
   managed-local locator.
3. Created default timeline `primary` with a registry entry
   `assets.source.media_id` pointing at that media id.
4. Started the editor bridge headlessly with `serve --no-open-editor`.
5. Read health, project list, and timeline list/show over HTTP.
6. Saved a small config change, deliberately sent a stale-version save, then
   recovered with the current version.
7. Fetched the registered asset normally, with a byte range, and with ETag
   validation.
8. Shut down the bridge and read the state back through the CLI.

## Live evidence and friction

### P0/P1 — no live correctness blocker found

The core flow completed. HTTP reads returned 200 JSON, save returned the
updated document, the stale write did not mutate state, recovery reached
version 3, and the CLI/doctor read-back agreed. Asset bytes matched the
imported SHA-256 (`b1ff9c8e...a946640`).

### P1 — family help can touch the store and fail before showing help

Running `python3 -m astrid projects --help` without the isolated-root
environment (the natural follow-up after the top-level census) produced:

`unstructured - this is a bug.`

`database contains applied migrations for pack 'runaway', which is not
registered in this composition`

The same happened for `timelines --help` and `media --help`. With the isolated
root explicitly set, all three help commands worked. Help should be
side-effect-free and should not require opening the database; at minimum it
should explain the selected root before failing. This also makes a stale
default checkout migration look like a CLI syntax problem.

### P1 — CLI and live bridge cannot concurrently own the database

While the bridge was running, `timelines save --help` failed before displaying
help with `database is already owned by another process`, wrapped as
`unstructured - this is a bug`. HTTP continued to work, and CLI commands
worked after clean shutdown. A user/agent inspecting CLI help or doing a
parallel read during an editor session gets an opaque internal error rather
than an actionable “bridge owns the project store; use HTTP or stop it”.

### P2 — HTTP route and payload discovery is undocumented from the public help

The serve help only documents process flags; it does not list HTTP routes or
JSON shapes. Starting from ordinary guesses took these discoveries:

* `/health` worked; `/` returned a useful JSON 404, while `/api/health`,
  `/v1/health` did not.
* `/projects` worked; the project detail route
  `/projects/editor-demo` did not.
* `/projects/editor-demo/timelines` and
  `/projects/editor-demo/timelines/primary` worked.
* Timeline mutation was found at
  `POST /projects/editor-demo/timelines/primary/save`; the empty payload
  returned `config must be a JSON object`, which helped recover. The working
  shape was `{config, registry, expected_version}`.
* The registered asset route was found at
  `GET /projects/editor-demo/timelines/primary/assets/source`.

Once found, these endpoints were coherent, but an editor agent has to guess
the singular route structure, mutation verb/path, and whole-document payload.
The bridge should expose a small machine-readable route/schema document (or
include the routes in `serve --help`) and return `Allow`/route hints on 404s.

### P2 — timeline version naming is consistent but has a small conceptual trap

The read model calls the field `config_version`; save requires
`expected_version`, and the HTTP response increments `config_version` from 1
to 2 to 3. The 409 response was unusually good and actionable:

`timeline save rejected: expected version 1, current version 2; no write
occurred. Recovery: show the current timeline, merge your changes into it,
then save with its config_version as --expected-version...`

The one improvement would be to document the read-field/write-field mapping
in the HTTP contract or use one name consistently.

### P2 — asset lookup is reliable after registry semantics are known

The registry reference `assets.source.media_id` resolved successfully to
bytes. Normal delivery returned `200`, `Content-Length: 69`,
`Accept-Ranges: bytes`, `ETag: "18ce7c09b77f20fd-45"`, and
`Cache-Control: private, no-cache`. `Range: bytes=0-3` returned `206` with
`Content-Range: bytes 0-3/69` and the expected PNG signature. Repeating with
`If-None-Match` returned `304` with no body. This is strong editor-facing
behavior.

The burden is that the registry stores a media id while the serving URL takes
the registry key (`source`), not the media id. The 404 for using the media id
did say `asset_not_found` and named the timeline, but it did not explain that
the URL expects the registry asset key. Include the resolved asset URL (or a
registry listing) in timeline show/read responses for agents.

## What Astrid should have told me

After `serve --no-open-editor`, Astrid should have printed something like:

```text
Bridge ready at http://127.0.0.1:49994
GET  /health
GET  /projects
GET  /projects/{project}/timelines
GET  /projects/{project}/timelines/{timeline}
POST /projects/{project}/timelines/{timeline}/save
GET  /projects/{project}/timelines/{timeline}/assets/{registry_key}
Save JSON: {"config": object, "registry": object, "expected_version": integer}
The project database is exclusively owned by this bridge until shutdown.
```

It should also have surfaced the current project root and offered a
machine-readable schema/route document. The current readiness line (“bridge
at ...; editor: not opened”) is enough to know that the process is ready, but
not enough to make an agent productive without route guessing.

## Final CLI agreement

After shutdown:

* `projects show editor-demo` reported the default timeline id and event head
  sequence 6.
* `timelines show primary --project editor-demo` reported
  `is_default: true`, `config.ui.zoom: 1.5`, `config_version: 3`, and the
  registry media id.
* `media show ... --project editor-demo` reported the imported 69-byte PNG
  and managed locator.
* `doctor --json` returned `ok: true`, quick-check ok, no foreign-key
  violations, and schema versions `core=1, references=1, shots=1, timeline=1`.

Overall: **PASS with P1/P2 UX findings**. The bridge’s CAS and HTTP byte
serving are solid; discoverability and the exclusive-store error experience
are the main ergonomic gaps.
