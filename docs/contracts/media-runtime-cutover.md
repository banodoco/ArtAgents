# Live media input contract

Live Astrid media is identified by a neutral-runtime, project-scoped
`object_id` and its lowercase SHA-256 `digest`. The generic pack host fetches
and verifies those bytes, then passes an attempt-local materialization to a
renderer.

URL references, `file`/`path`/`locator` values, path fingerprints, URL caches,
CAS-locator rebasing, and `external_local` realms are not live inputs. They are
accepted only by the explicitly offline `tools.astrid_migrate` boundary. A
renderer must fail closed before opening any such locator, and may stage only
bytes supplied by the runtime materialization handoff.
