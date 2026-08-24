# Live references + shots composite wave 3

Date: 2026-08-24 (Europe/Berlin)  
Surface: public `python3 -m astrid` CLI and `--help`; no private APIs or
programmatic product tests for the live workflow.

## Verdict

PASS, 9.5/10 after one P2 ergonomics fix. No P0 or P1 issues remain in this
wave. The reference and shot composites are usable end-to-end: typed
references preserve ordered media associations and links, shots preserve
ordered enriched media, removal is non-destructive, and ownership fences fail
closed.

## Fresh live fixture

The primary fixture used a fresh root and project:

- root: `/tmp/astrid-refshots-4jWuhC`
- project: `studio` (`d25c2c41-1568-5c40-940d-c0c4718b1c91`)
- managed media: red PNG `551d1cf4-afee-5c90-b625-37c28ce3c083`, blue MP4
  `1a2a3238-1a67-50b5-b06d-a665b6268a51`, WAV `f9ce4ba8-1a6b-5271-934a-a6c3fc9021d9`,
  and green PNG `5234ab64-2bb4-5066-a301-c98c929b9155`.

`doctor` reported a clean uninitialized root before bootstrap. All three
video/image/audio imports were admitted as managed media with verified bytes.

## References workflow

Created different named kinds, including two intentionally same-named
references to exercise recovery:

- character `Alex` (`76d1ba50-4fc8-50a0-8928-850ba13f1236`), initially red PNG;
- place `Alex` (`9b5d8178-dede-5330-b97f-6e3f5a8cf4dd`), blue MP4;
- clothing `Red Coat` (`0100fc49-9d1e-577a-8bd4-a1edc60fff32`).

The live commands successfully:

1. updated Alex's description and metadata;
2. associated the WAV as `inspired_by` with ordinal 2 and metadata;
3. linked Alex to Red Coat with typed `wears` and metadata;
4. associated the green PNG as a second `canonical` association;
5. promoted that association with `set-primary`, which reported both the
   previous and new primary IDs;
6. showed the full reference read model with ordered associations and the
   updated primary flag.

Archiving preserved events, media associations, and links. Inclusive listing
was required and clearly documented. Unarchive by exact ID/name worked and was
safe to repeat (`changed: false`). An ambiguous `unarchive Alex` failed closed
with both candidate IDs and a recovery command. Name-based `associate Alex`
likewise failed with candidate IDs.

## Shots workflow

Created shot `Arrival Sequence`
(`612a3fae-7641-5938-a26c-5918c2d81f0c`), then added image, video, and audio
items with positions, source frames, and metadata. `shots show` enriched each
item with media kind, MIME type, managed path, and name. Inserting audio at
position 1 shifted the prior item correctly.

`shots reorder` accepted the complete item permutation and returned both item
and media order. Removing the audio item returned the remaining two items;
`media show` immediately after removal proved the audio media row, managed
locator, and bytes remained intact. Thus shot removal is non-destructive.

Negative permutations (missing item and duplicate item IDs) failed before
mutation. Removing an unknown item returned `not_found`.

## Cross-project ownership

An `outsider` project received a separately imported, same-content MP4 with a
different media ID (`0b7fd28f-aa8b-59fd-9dff-d5ee7a4bec0a`). Attempts to use it
from the studio project were rejected before mutation:

- reference association: `validation_error`, reason `foreign_media`;
- shot add: `validation_error`, reason `foreign`;
- linking a studio reference to an outsider reference: `not_found`, reason
  `foreign`.

The errors included project/entity IDs and recovery guidance.

## Confirmed defect and fix

The first live update created Alex with metadata `{"age":30,"tag":"hero"}`
then sent `--metadata '{"age":31,"arc":"arrival"}'`. Despite help and the
repository contract calling this a metadata delta, the response silently
dropped `tag`. This was a safe high-value P2 data/UX defect.

The smallest fix makes non-empty metadata mappings shallow-merge into the
stored object while retaining the documented explicit-empty clear operation.
A focused guard was added in `tests/v10/test_reference_repository.py`; the
reference update subset passes: `13 passed`.

Fresh public CLI replay used root `/tmp/astrid-refshots-replay-fOSA03` and
reference `fd4e6690-8bae-5a96-af4a-d0f70260b3d5`:

- delta update returned `{"age":31,"arc":"arrival","tag":"hero"}`;
- explicit `{}` update returned `{}`.

## Remaining friction (P2 only)

- Associating media to an archived reference returns a generic
  `terminal_state` envelope with empty details; a recovery hint would reduce
  wrong turns.
- Invalid shot permutations return generic validation details, although help
  makes the whole-permutation requirement clear.
- A successful shot removal response echoes the removed item with its former
  position while also returning the remaining `item_ids`; an explicit
  `removed: true` or clearer result shape would be easier to read.

None of these caused data loss, cross-project leakage, or an unrecoverable
workflow stop, so no further product edits were made in this wave.
