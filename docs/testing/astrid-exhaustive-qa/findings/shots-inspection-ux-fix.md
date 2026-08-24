# Shot inspection UX fix

Date: 2026-08-23  
Mode: live CLI usage followed by narrow implementation checks

## Failure reproduced

In an isolated root, a fresh process could run `timelines shots list`, but the
public nested parser rejected `timelines shots show <shot>`. The list read model
contained only shot metadata, so an agent auditing state later had to retain an
add/remove mutation response and opaque shot-item ids.

## Durable fix

- Added `python3 -m astrid timelines shots show <shot> --project <project> [--json]`.
  It is one public SDK call to the existing sanctioned `ShotsService.show()`.
- The standard application wires the existing media repository into the shot
  service. Show best-effort enriches each item with `media.id`, imported
  relative `name`, current replaceable `path`, `realm`, `media_kind`, and
  `mime_type`, while preserving the existing item `id`, `media_id`, and
  `position` fields. Missing legacy media detail never hides a valid shot.
- Help and journey/contract docs explicitly describe shots as project-level
  reusable records. The `timelines shots` nesting is a CLI mount only; there is
  no invented implicit timeline association or new `--timeline` argument. A
  timeline document may reference a shot in its own config if it chooses to.

## Live proof

Isolated root: `/tmp/astrid-shot-live-fixed.OPhJPP/projects`

1. Created project `live-shot-fixed`.
2. Imported `first.png` and `second.jpg` as two project media records.
3. Created shot `Reference Shot`.
4. Added `first.png`, then added `second.jpg` at position `0`.
5. Removed the first item's generated shot-item id.
6. Started a fresh CLI read and ran:

   ```text
   python3 -m astrid timelines shots show cf848e81-48b6-5b95-9222-e6e9a58bf096 \
     --project live-shot-fixed --json
   ```

   The response showed the remaining item at `position: 0`, with item id
   `d5256cfc-8939-5624-b42f-aaf3b81c62a5`, media id
   `db54cd9d-339e-548b-882c-9ff046834ff2`, and friendly media name `second.jpg`
   plus its managed path.
7. A separate fresh `media show` confirmed removed media id
   `c8a20bed-0577-5143-98ae-84f3da9fffdd` remained present with `first.png` and
   its managed locator.

## Verification

- `python3 -m astrid timelines shots --help` lists `show` and explains the
  project-level/reusable semantics.
- `python3 -m astrid timelines shots show --help` exposes the required shot
  positional, `--project`, and `--json` options.
- Targeted modules compile successfully with `python3 -m compileall`.
