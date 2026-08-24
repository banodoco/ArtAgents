# Final cross-domain maker — live agent UX wave

Date: 2026-08-23 (Europe/Berlin)  
Verdict: **PASS with material UX friction**  
Overall agent-UX score: **8.1/10**

## Scope and operating constraints

This was a fresh end-user run in `/Users/peteromalley/Documents/reigh-workspace/Astrid`, using only the public Astrid skill, public docs, CLI help, SDK discovery, and SDK invocation. No source, tests, git history, prior QA reports, cloud generation, credentials, or paid services were used. The project root, cwd, HOME/preferences, backup, restore, and fixtures were disposable. Product code was not modified.

The initial census was useful and accurate: `projects`, `timelines`, `media`, `tasks`, `runs`, `serve`, `doctor`, and `backup`, with `timelines shots` and `media references` as nested mounts. SDK discovery found the relevant `rendering.render`, `rendering.timeline_visualize`, and generation capabilities.

## The creative journey

I made a titled 4-second audiovisual “Astrid field note” from a locally synthesized 640×360 H.264/AAC MP4 (solid blue field plus a sine-wave audio track). The project was `field-note`, display name `Astrid field note`; it was selected as the workspace project and its default timeline was `field-note` / “Astrid field note timeline”.

Reusable organization was real, not decorative:

- project id: `0c210997-bc85-50c3-812c-e5ab9cb1531b`
- timeline id: `98bd4627-e086-53f9-9633-c9019ff8c0e0`; timeline ULID `gh74r7d8047asz0wyc90wkt381`
- reference: `7132add4-1658-5c8a-882e-9b9fb69a9da0`, kind `object`, “Field note source”
- reusable shot: `ebcadc04-5831-5b6a-bdbc-f04bffc1db43`, “Opening field note”, with one ordered source item
- source media: `db0ec0f3-23df-5587-b836-d2867fc0d7f5`, SHA-256 `ad827be6b3b5bb2b3c10c27107210e6e8004c2f30870863e536512e391cd61b8`

The timeline had a source video clip, an audio clip, and a centered text clip. The first save created version 1. I rendered a real MP4 through the local Remotion backend. The first successful render was 4.053333 seconds, 1920×1080, H.264 video plus AAC audio, 183,437 bytes, with primary media id `01m0r1ckcbyvnhhhr99f54bdn2` and a managed provenance sidecar media id `01m0r1ckcgv46nmghxmwmd3c3y`. A decoded frame visibly showed “Astrid field note”.

The second edit changed the title to “Astrid field note — second edit”, saved with optimistic CAS as version 2, and rendered again. The second playable render was also 4.053333 seconds, 1920×1080, with primary media id `01m0r1ek8cv2njmjr44nxjs7pz`, SHA-256 `4f391f70c734ec48f4a2bd03c33f63cc7a8f6f521554a57a459121c05d44e175`, 187,038 bytes. A decoded frame visibly showed the second title. Its provenance sidecar was media id `01m0r1ek8fbeay7025xrpqymn3`.

The render provenance was substantive: schema version 2, `TimelineComposition`, Remotion engine, timeline and asset-registry paths, request digest, registry hash, resolved backend `rendering.remotion`, and a reasoned rejection of the incompatible ffmpeg candidate because the timeline had text, multiple visual concerns, and embedded audio.

## CAS, archive, and fresh-shell return

The second edit was saved at expected version 1 and returned version 2. A deliberate stale save at expected version 1 returned the typed `stale_version` error with `current_version: 2`, `expected_version: 1`, and explicitly stated that no write occurred. The timeline diff reported `clips` changed and `main` registry changed.

I archived the timeline and reference, then started a fresh shell with no remembered IDs. Inclusive discovery found the archived timeline by slug and reference by name. `timelines unarchive field-note` and `media references unarchive "Field note source"` restored both and preserved their event/media associations. The final timeline head advanced through lifecycle events to version 5 after the later relocation-registry save; content remained the second edit.

One recovery wrong turn exposed a bug: `media references show "Field note source"` produced the unstructured error “this is a bug” instead of resolving the documented name form. Retrying with the exact id succeeded. The name-based `unarchive` path itself worked as documented.

## Media identity, relocation, and dedupe

Importing the same source bytes into `managed_local` and `external_local` produced one source media id with two locations, not duplicate media rows. The external location was relocated to `relocated-source.mp4` without changing media identity; both external and managed locations verified successfully. The reference continued to point to the same source media id.

Final media inventory was five rows: the one deduped source, two rendered MP4s, and two provenance JSON sidecars. There was no unexpected source duplication or duplicate render artifact for the two intended edits.

## Run/task evidence

Successful first render: run `00b5705287d77a3de78cea9d62`, task `52c0b6b2cd2a60b5e5fc2aa971`, succeeded with one child and two output media records.  
Successful second render: run `6f97b82af4ef33637f347295fb`, task `33d446e0c5fe1af3b6da09aa43`, succeeded with one child and two output media records. Task events showed the complete queued → claimed → started → completed chain, winning attempt, output hashes, and media ids. All intentionally failed render probes were terminal and visible in `runs list`; no task remained queued or running.

## Truthful failure probes

The following failures were safe and local:

1. `rendering.render` with an output name lacking `.mp4` failed fast with a clear `ValueError`.
2. A project-relative timeline input failed with a clear project-ownership error; correcting it to the actual project-owned file recovered.
3. A managed-media absolute path was rejected as outside the project root; adding an external-local project-owned location recovered.
4. Generation preflight with `execution: local`, an invalid model, and an invalid mode did not contact cloud services. SDK preflight raised a truthful unknown-model validation exception and listed available models, although it emitted a traceback rather than a JSON envelope.

I also probed `rendering.timeline_visualize`. Its public schema/help path was friction-heavy: a comma-separated format was rejected, `--timeline-slug` and `--all` were mutually exclusive, and the slug-based invocation then reported no timeline. These were terminal failed runs, not hidden or hanging work; the core render path and timeline evidence remained healthy.

## Backup and restore

`backup create` staged and validated the disposable root, reporting 5 media files and 116 SQLite pages. The source root doctor was green: accessible paths, managed-media resolution, external integrity, SQLite quick check, foreign-key integrity, and schema versions all passed.

`backup restore` into a second disposable projects root completed and restored 5 media files. Doctor was green there too, with the same six healthy checks. Inclusive reads in the restored root showed the same project slug/name, active default timeline slug and immutable timeline ids, active reference id/name, and the same source/render/provenance media ids and content hashes. The external locator remains an absolute path into the original disposable root; this is valid while that root exists but means a backup containing external-local media is not fully self-contained if the original root is removed.

## Friction and severity ranking

### P1 — reference show by name crashes instead of returning a typed not-found/addressing error

The public recovery story teaches human-readable reference names, and unarchive accepts the name, but `media references show <name>` crashed through an “unstructured” bug path. Exact-id recovery works. This is the clearest end-user correctness issue.

### P1 — external-local backup portability is incomplete

The restored database preserves the external locator exactly, but the external file is not copied into the second root. Doctor is green only because the original disposable root still exists. A portable backup should either stage external-local files or clearly mark/revalidate them as host dependencies.

### P2 — render ownership and filename constraints are late-discovered

The public timeline/render walkthrough does not make the project-root asset restriction or required `.mp4` suffix prominent. Both errors were recoverable, but they cost wrong turns before first output.

### P2 — generation preflight bypasses the normal SDK envelope on invalid model

The message is truthful and helpful, but a full traceback is poor agent UX and prevents uniform `ok/error/receipt` handling.

### P2 — timeline_visualize discovery/help and invocation contract are hard to reconcile

The SDK-discovered input shape omitted the CLI-required `out` and exposed a `formats` spelling that did not map directly to the executor’s singular `--format`; project/timeline addressing also failed in this disposable setup. Failures were terminal and explicit, but the capability was not a smooth “discover then use” path.

### P3 — run `--evidence` was empty for a successful render

The authoritative task events contained complete output evidence, so this did not compromise the artifact. Still, an agent asking `runs show --evidence` should see the output/provenance evidence without needing to know to pivot to task events and media show.

## Overall assessment

Astrid supported the full maker loop: fresh project and routing, synthetic local audiovisual input, reusable reference and shot organization, default timeline creation and versioning, real local render, visible title inspection, provenance, public media/run/task evidence, optimistic edit plus stale-save recovery, media verify/relocate/dedupe, reversible archive/recovery without remembered IDs, and doctor-green backup restore. The kernel’s identity and terminal lifecycle behavior were strong. The score is held below excellent by the reference-addressing crash, non-portable external backup locator, uneven preflight envelope behavior, and the difficult timeline-visualization contract.

Disposable fixture, cwd, preference, backup, and restore artifacts were cleaned after capture; the report is the only durable artifact from this wave.
