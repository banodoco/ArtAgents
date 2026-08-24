# Live UX wave: media, character reference, and shot

Date: 2026-08-23  
Mode: live CLI usage as a fresh agent (no tests or source inspection)  
Isolated root: `/private/tmp/astrid-live-media-1ZuKnw/projects`

## User goal

Create `character-board`; import `avatars/forager.png` and
`avatars/portrait.png`; create character reference `Hero` using both, with
portrait primary; create a default timeline and a shot containing both images;
put portrait first; remove forager from the shot; verify forager remains in the
project media library and report the final reference/shot state.

## Chronological live actions and evidence

1. Ran `python3 -m astrid --help`, then `help`, and family/mount help for
   projects, media, media references, timelines, and timeline shots. The
   census was useful and clearly exposed the nested mounts. Subcommand help
   exposed the key semantics: reference create takes one primary `--media`,
   `associate` takes a reference id plus `--role`, `set-primary` takes an
   association id, shot insertion is 0-based `--position`, and shot removal
   takes a shot-item id rather than a media id.
2. Ran `doctor --json`: all checks passed (`schema_versions` core=1,
   references=1, shots=1, timeline=1; SQLite quick check and FK integrity OK).
3. Created project `character-board` named `Character Board`.
   Project id: `541d8e50-886a-5023-9d39-5ed166155555`.
4. Imported `avatars/forager.png` as managed media. Media id:
   `479259e2-4d16-5287-b344-4378ee4eba35`; import reported image/png,
   1,851,202 bytes, and a managed-local content-addressed location.
5. Imported `avatars/portrait.png` as managed media. Media id:
   `6ec44fb3-3e75-5c7e-b0d7-08a29f44164c`; import reported image/png,
   1,626,110 bytes.
6. Listed media and confirmed exactly those two rows in the project.
7. Created timeline slug `default`, name `Default`, with `--default`.
   Timeline id: `951b6cc5-9e58-5369-9fb4-ec115de141e7`; `is_default: true`.
8. Created reference `Hero` with `--kind character` and portrait as the
   required initial `--media`. Reference id:
   `53e94d00-5f89-532e-96a3-bcb6c0978bca`. The response explicitly showed a
   canonical portrait association, ordinal 0, `is_primary: true`.
9. Associated forager to Hero with `--role canonical --ordinal 1`.
   Association id: `01m0qm4nv4z8nm5drffk67shtn`; response showed
   `is_primary: false`. The original portrait association id is
   `01m0qm4dh0cw5jf0z30xemv002`, so no `set-primary` call was needed: portrait
   was already primary. The final reference read confirmed both media, both
   canonical, ordinals 0/1, and portrait primary.
10. First tried to create the shot as `--name Hero shot` without shell quotes.
    The CLI returned argparse's `unrecognized arguments: shot` (exit 2).
    Retried correctly as one quoted name.
11. Created shot `Hero shot`. Shot id:
    `a45018c4-7133-5ad0-85af-411d1933835c`.
12. Added forager first (append/default position 0). Shot-item id:
    `94921a7d-ac60-55c3-976a-009f0048bfd8`.
13. Added portrait with `--position 0`. Shot-item id:
    `06e4281b-06f2-50c2-a433-9cac4b10c324`. The mutation response gave the
    ordered item ids `[portrait-item, forager-item]`, proving portrait first.
14. Removed forager using the shot-item id (not its media id). The response
    gave final `item_ids: [06e4281b-06f2-50c2-a433-9cac4b10c324]`, proving the
    shot contains portrait only. It also returned the removed item with its
    media id, making the operation auditable.
15. Final `media show` for forager succeeded: the original media id and
    managed-local location remained intact, with no destructive side effect.
    Final `media references show` succeeded: Hero still has portrait primary
    plus forager canonical/non-primary. Final `timelines shots list` showed
    `Hero shot` updated, and final `timelines show default` still showed
    `is_default: true`.

## Severity-ranked UX critique

### S1 — Shot membership is not readable from the final read surface

`timelines shots list` returns shot metadata only; it omits `items` and their
media. `timelines show default` also does not expose the shot. The only way to
verify the final shot contents in this run was to retain the mutation response
and infer state from `item_ids` returned by add/remove. A fresh agent auditing
later cannot reliably view the shot state with the advertised read commands.

Astrid should provide `timelines shots show <shot> --project ...` (or include
items/media filenames in `shots list`) and make the timeline-to-shot
relationship explicit. The read response should show ordered position, item
id, media id, and a friendly media basename.

### S1 — A “timeline with a shot” is not represented in the visible command contract

Timeline creation is project-scoped, and shot creation is also project-scoped;
no shot command accepts a timeline id/slug. The default timeline and `Hero
shot` therefore cannot be visibly linked through the public CLI. This is a
major ambiguity for the requested task: the command names imply nesting under
timelines, but the required project argument and responses expose no timeline
association.

Astrid should either require `--timeline default` on shot create/list/show or
explicitly explain that shots are project-level and how they participate in a
timeline document.

### S2 — Reference creation is asymmetric and requires manual ID shuttling

Creating a reference requires one exact media id; adding the second requires a
separate association call. Promoting a later image requires yet another
association-id-based `set-primary` call. This is workable but forces the agent
to shuttle project id, reference id, media ids, and association ids between
commands. Help says “primary canonical media” but does not show the natural
multi-image recipe.

Astrid should support repeated `--media` (with an explicit order/primary flag)
or print a short next-step hint after create, e.g. “To add another image use
`associate ... --role canonical`; use the returned association id with
`set-primary`.”

### S2 — Shot removal uses an opaque item id rather than the media id the user knows

The user asks to remove “forager,” but `remove` needs the generated item id.
Help does say “item id,” and the add response exposes it, yet a user who only
has a media id must first recover the item mapping. A show/read command would
resolve this. Error guidance for accidentally passing a media id should name
the expected shot-item id and suggest the lookup command.

### S3 — Shell quoting is ordinary but the failure gives no task-level recovery

The unquoted multiword shot name produced a standard argparse error. This was
recoverable immediately, but the CLI could make the example/help convention
clearer (`--name "Hero shot"`) and avoid burying the useful command context in
generic parser output.

### S3 — The roles/kinds vocabulary is frozen but under-explained

The choices were discoverable (`character`, etc.; `canonical`, `depicts`,
`used_as_input`, `inspired_by`), but help did not explain when a reference
image should be `canonical` versus another role. For this task, canonical was
the right inference because the reference is made from visual identity images.
One-line definitions and an example for a multi-image character reference
would reduce uncertainty.

## What worked well

- The top-level census and nested mounts were discoverable.
- JSON envelopes were consistent and receipts made mutations auditable.
- IDs were stable and exact project scoping prevented cross-project ambiguity.
- 0-based insertion worked exactly as documented: adding portrait at position 0
  produced portrait before forager.
- Removing a shot item preserved the underlying media; final `media show`
  verified forager safely remained in the managed project library.
- The reference read model clearly exposed primary status, role, and ordinal.

## Final state

- Project: `character-board` (`541d8e50-886a-5023-9d39-5ed166155555`).
- Default timeline: `default`, default=true (`951b6cc5-9e58-5369-9fb4-ec115de141e7`).
- Reference: Hero, kind=character (`53e94d00-5f89-532e-96a3-bcb6c0978bca`).
  Portrait is canonical, ordinal 0, primary; forager is canonical, ordinal 1,
  non-primary.
- Shot: `Hero shot` (`a45018c4-7133-5ad0-85af-411d1933835c`). Final ordered
  item ids contain portrait only: `[06e4281b-06f2-50c2-a433-9cac4b10c324]`.
- Forager remains in project media: `479259e2-4d16-5287-b344-4378ee4eba35`,
  managed-local location intact.
