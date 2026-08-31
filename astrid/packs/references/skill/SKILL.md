---
name: references
description: >
  Create and manage reusable Astrid references for characters, places,
  objects, logos, clothing, styles, and layouts. Use when choosing canonical
  media, adding supporting depictions, recording generation lineage, or
  preparing consistent inputs for later image and video work.
---

# References

A reference is a stable creative concept. Media files are concrete examples of
that concept.

Keep four things separate:

- **Reference** — identity and intended use, such as a character or wordmark.
- **Primary media** — the best identity anchor, not necessarily the newest file.
- **Supporting media** — other approved views, composites, or inspirations.
- **Media lineage** — which files were derived from or used other files.

This lets a character, logo, and layout remain independently reusable while
still being linked as one project visual system.

## Choose the right reference boundary

Create a separate reference when something has an independently reusable
identity, not for every visual difference.

- Keep one character reference for the same person or creature across age,
  pose, expression, and camera angle. Tag supporting associations with metadata
  using the stable shape
  `{"schema":"astrid.reference-state/v1","state":{"life_stage":"young","view":"left_profile"}}`.
- Make a reusable garment or prop its own `clothing` or `object` reference. A
  red jumper can then be linked to the character with `wears` and used with
  other characters later.
- A composite image may be associated with every concept it depicts.
- Split a state into its own linked reference only when it must be selected or
  reused independently, for example an older version with a distinct design.

Canonical example: create one character reference for Aria; associate young,
older, front, and profile media with state metadata; create the red jumper as a
separate `clothing` reference; associate any image showing both with both
references as `depicts`; then link Aria to the jumper with `wears`.

The reference kinds, roles, links, primary uniqueness, and same-project rules
are database-enforced. `astrid.reference-state/v1` is the lightweight metadata
profile for consistent state naming; it remains extensible JSON.

## Create a reference kit

1. Inspect what already exists.

   ```bash
   python3 -m astrid media references list \
     --project <project> --include-archived --json
   ```

2. Reuse strong media first. Generate only missing views or guides, using the
   best existing media as inputs. Visually inspect generated assets; exact
   historic logos and text usually make safer primaries than regenerated ones.

3. Import each useful file through Astrid. Never write reference or media rows
   directly to SQLite.

   ```bash
   python3 -m astrid media import <path> --project <project> --json
   ```

4. Create the concept with its primary media.

   ```bash
   python3 -m astrid media references create \
     --project <project> \
     --kind <character|place|object|clothing|other> \
     --name "<name>" \
     --media <media-id> \
     --description "<identity and intended use>" \
     --metadata '{"schema":"astrid.reference-kit/v1"}' \
     --json
   ```

5. Add supporting media and file lineage.

   ```bash
   python3 -m astrid media references associate <reference-id> \
     --project <project> --media <media-id> --role depicts \
     --metadata '{"schema":"astrid.reference-state/v1","state":{"life_stage":"young","view":"left_profile"}}' --json

   python3 -m astrid media relate \
     --project <project> \
     --from <output-media-id> --to <input-media-id> \
     --kind derived_from --json
   ```

   Association roles:

   - `canonical` — another approved identity-defining depiction.
   - `depicts` — visibly contains the concept.
   - `inspired_by` — a looser style or layout source.
   - `used_as_input` — only when `--context-task` names the real same-project
     task that produced that media.

   For external or historical generation, use `media relate` instead of
   inventing a task. Use `uses_as_input` and `--ordinal` when an output combines
   ordered inputs, such as the frames of a video. Keep state facet names and
   values in `snake_case`; omit facets that are unknown rather than guessing.

6. Link concepts that should be discovered together.

   ```bash
   python3 -m astrid media references link \
     --project <project> \
     --from <reference-id> --to <reference-id> \
     --kind <associated_with|wears|belongs_to|located_in|related_to> --json
   ```

7. Verify the result through the public read model and the read-only doctor.

   ```bash
   python3 -m astrid media references show <reference-id> \
     --project <project> --json
   python3 -m astrid doctor --projects-root <projects-root> --json
   ```

Use stable `--idempotency-key` values for workflows that may be resumed.
