# Final live acceptance 7

Date: 2026-08-24 (Europe/Berlin)  
Surface: public `python3 -m astrid` gateway and public `--help` only  
Verdict: **PASS — 9.3/10; no P0 or P1 findings.**

This was a fresh black-box journey with no source, test, SDK, or product edits:

- source root: `/tmp/astrid-final7-src-OwRxZX`
- backup: `/tmp/astrid-final7-backup-7YhQ3M`
- restored root: `/tmp/astrid-final7-dst-MSYyrj`
- project: `final7`; canonical timeline: `main`

## Journey and evidence

1. Public census/help exposed the eight families and nested mounts. `doctor`
   correctly reported a brand-new root as uninitialized; after
   `projects create`, it became fully green: data paths, managed media,
   SQLite quick check, foreign keys, and all schema versions.
2. Imported valid managed MP4, WAV, and PNG media. Admission probed the MP4
   and WAV as decodable video/audio and stored all three as `managed_local`.
   Hashes were respectively:
   `b08946deaa076ae1c618472ed6e001d0560f92a107fadf33c997516c64c7f6fb`,
   `b9fb5441efa264d9cbba0d7e036ff76471d8ec351b3014d35de246d82503723e`, and
   `ea5ac73d069ebe7fe83d53b17b7f0cee0b13210af3d541a5ee7d0355548b2db5`.
3. Created `main`, then saved version 2 with video/audio/text clips and a
   registry for all three media. `timelines show`, `history`, and `diff`
   exposed the expected CAS save (`clips/theme/tracks` added; video/audio/
   image registry entries added).
4. `timelines visualize main --format png,md --filmstrip off` succeeded and
   published a durable evidence pack. All three assets were
   `verified_original`; diagnostics contained only the expected
   `KERNEL_AUTHORITY` and `SHOT_GROUPS_ABSENT` warnings—no
   `MEDIA_MISSING`, `UNSUPPORTED_MEDIA`, or registry/hash warnings.
5. A version-pinned canonical render with `clipType: "video"`, audio, text,
   backend `rendering.remotion`, and the documented strict JSON profile
   succeeded with strict JSON stdout. Source run
   `e408091c4dcd3dcc38126d629e`, task `a30085b6a6cd64907ff2c3ab52` produced
   MP4 hash `a739f2f15c8895cf28b78b613a2f2bfe9b18dfb93bf0f838d75eaadc19422463`
   and provenance hash
   `602556fba084808856ad775c0162b00b6be9309cc754c0909f7c5f25e5fc937d`.
   `ffprobe` confirmed H.264/AAC, 1920×1080, 60 video frames, 96 audio
   frames, and 2.048 seconds; decoding a mid-stream frame succeeded.
6. Invalid draft/profile pre-admission checks were zero-mutation. Rendering
   the empty `draft` failed validation with null run/task/attempt ids; the
   run count stayed 3. A malformed `--profile '{"width":320}'` likewise
   returned validation with null kernel ids; run count stayed 3 and managed
   media file count stayed 18. No invalid output or provenance artifact was
   created.
7. Archived `main`, confirmed it disappeared from the active list but remained
   in `--include-archived`, then unarchived it. Repeating unarchive returned
   `changed: false`. Canonical content remained intact; lifecycle advanced to
   version 4.
8. Created a self-contained backup and restored it into the fresh destination.
   Restore reported 18 managed media files and 18 rebased managed locators.
   Immediate destination visualization succeeded with all three assets
   `verified_original` and no media/registry warnings. Immediate pinned
   destination render succeeded as run `614932a6fd6264e249b3c84a1d`, task
   `3ce8bd541a7c914879a6c97d9e`, producing the same MP4 hash and restored
   provenance hash
   `9f18d120d61f68f959af0e6896f1f5c01e2589d105cbf8a7c4a4f8c75b5db577`.
9. Public `runs show --evidence`, `runs events`, `tasks show`, and `tasks
   events` exposed kernel authority, config version 4, task/run linkage,
   successful lifecycle, output media, canonical registry hash
   `a942566523d33b9309a0c2c0a82968f584ef2137a95785e9c6f4b222051af2c7`, and
   destination materialized registry hash
   `08d24dd13f65b7928f1c54a0eda6e454995a928bca8b807f36c14eb435de7e3c`.
   Source materialized hash was distinct (`47a1eac24e1efcfbb77e70d75a6121b27e49c3bace829abf528b68fb34565f1f`), as expected.

Source and destination `timelines show` and `timelines history` data compared
equal before and after rendering. The source-root absolute locators remained
the immutable canonical payload; only derived materialized registries used
destination CAS paths. No `assembly.jsonl` exists in either root.

## Friction and remaining risk

- **P2 ergonomics:** a fresh-root `doctor` is red until the first bootstrap
  command. The message is actionable, but a first-run “not initialized yet”
  status could be less alarming.
- **P2 validation timing:** a 320×180 profile was accepted far enough to
  create an invocation, then Remotion rejected it because this backend
  currently requires 1920×1080. The documented 1920×1080 profile succeeded;
  capability-specific profile validation should ideally happen before
  admission and state the supported dimensions.
- Invalid-draft validation is correct but returns a very verbose JSON-schema
  diagnostic, which is harder to scan than the concise profile error.

No P0/P1 blocker remains in this acceptance. The restored
show/history → visualize → version-pinned render → run/task/provenance path is
portable, immutable, and playable end to end.
