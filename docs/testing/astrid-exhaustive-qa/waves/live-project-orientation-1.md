# Live project orientation/lifecycle — wave 1

Date: 2026-08-23 (UTC)

## Verdict

**Overall: PASS with P1 UX/documentation friction and P2 error-quality friction.**

The clean-machine project lifecycle is usable end-to-end through public CLI
surfaces: `doctor` explains that an empty root is expected, `projects create`
bootstraps the store and creates a readable `plan.md`, project ids and slugs
both address records, metadata/settings updates are receipted and idempotent,
the display name can change without changing the slug, and a default timeline
is correctly routed to the intended project. A fresh shell can rediscover the
renamed project from `projects list` and continue through the timeline API.

The main friction is that the promised `projects select` preference is not a
current-project resolver: it returns the project row but exposes no
preference/read-back state, and product commands still require an explicit
`--project`. Human names are not accepted as project identifiers, and duplicate
names are allowed, so an agent must manually map a name to a slug from list
output. Typed errors have stable codes and the five-key JSON envelope, but
usually have empty `details`, so they do not explain the conflicting field or
the candidate records.

Severity-ranked findings:

1. **P1 — selection is not operational routing / weak orientation contract.**
   Help calls `select` a “non-authoritative default preference”; the command
   returns the selected project DTO, but there is no public read-back or
   `--project` defaulting. `timelines list --json` still exits 2 because
   `--project` is required. This is safe and documented, but a user who expects
   “current project” behavior must retain/rediscover the slug manually.
2. **P2 — identity and conflict errors are underspecified.** `projects show
   "North Star"` returns `validation_error` with `{}` details instead of
   saying “use slug/id”; duplicate slug and wrong-project failures return
   `conflict`/`not_found` with `{}` details. The codes are machine-usable, but
   not especially recovery-oriented for a new agent.
3. **P2 — project path is implicit.** Project create/show returns id and slug,
   but no path. Reading the generated plan required manually deriving
   `$ASTRID_PROJECTS_ROOT/<slug>/plan.md`; the plan is a useful empty scaffold
   but does not contain display name, settings, selected state, or timeline
   pointers.

No product code, tests, source files, SQLite files, prior QA reports, or
implementation notes were inspected or modified. The only file written was
this report; all product writes went to the disposable root
`/tmp/astrid-live-project-orientation-n3sTTQ`, which was removed after capture.

## Journey setup and timing

- Start: approximately 2026-08-23 17:51 UTC (first `doctor` probe).
- End: approximately 2026-08-23 17:54 UTC.
- Wall-clock duration: about 3 minutes.
- Product command attempts: 30-ish, including help, success, idempotent
  repeats, parse errors, typed errors, and final read-back. No blind retries.
- Root: `ASTRID_PROJECTS_ROOT=/tmp/astrid-live-project-orientation-n3sTTQ`.
- Primary intended project: slug `north-star-final`, id
  `f8ba0764-1595-5d89-bd0d-0cf3cdfcc6aa`.
- Comparison project: slug `north-star`, id
  `c7c5a69b-588a-5dcd-8be7-800b87358e7e`.
- Duplicate-name probe project: slug `south-star`, id
  `66080e32-578d-52dc-92af-c6de3b6044ff`.

## What a new agent discovered

Public `--help`, `help`, `projects --help`, the getting-started guide, and the
CLI journeys guide consistently pointed to:

```text
python3 -m astrid doctor --json
python3 -m astrid projects create <slug> --name <Name> --json
python3 -m astrid projects list --json
```

The initial read-only doctor on the empty root exited 1 and reported the
missing `.astrid` directory/database as expected, including the actionable
hint to run `astrid projects create <slug> --name <Name>`. This is a good
clean-machine first action pair: diagnose, then create.

Creation of two deliberately confusable records succeeded:

```text
north-star       -> name “North Star”
north-star-final -> name “North Star”
```

The create result clearly included `id`, immutable-looking `slug`, `name`,
`settings`, timestamps, and a receipt with command kind, project id, sequence,
and idempotency key. `projects list --json` intentionally returned only
`name`/`slug`, sorted by slug. That is enough for normal rediscovery but not
enough to disambiguate duplicate human names without another heuristic.

## Identity, path, and plan.md evidence

`projects show` accepted both the slug and the UUID for each project and
returned the same row. It rejected the human name `North Star` with a typed
`validation_error`, because names are not identifiers. After renaming the
primary project to “North Star Final Cut”, its slug and UUID remained stable.

Each create generated an empty, readable plan at the slug-derived path:

```text
$ASTRID_PROJECTS_ROOT/north-star/plan.md
$ASTRID_PROJECTS_ROOT/north-star-final/plan.md
$ASTRID_PROJECTS_ROOT/south-star/plan.md
```

The plan skeletons were:

```markdown
# <slug> — Plan
_Live working notes for this project. Read on attach; keep updated as the plan evolves._
## Current focus
## Open threads
## Key decisions
## Notes
```

This is useful as a stable human/agent notes landing place and confirms the
slug/path relationship, but it is empty and does not reflect the project
display name or state. No direct database/file inspection was used for
rediscovery; the plan was read only because the public Astrid skill explicitly
requires reading it after create/show.

## Metadata, settings, selection, and rename

The following update succeeded using a caller-supplied idempotency key:

```bash
python3 -m astrid projects update north-star-final \
  --name 'North Star Final Cut' \
  --settings '{"client":"live-ux","current_stage":"orientation"}' \
  --idempotency-key live-project-update-1 --json
```

Repeating the exact command/key returned the identical DTO and receipt
(including the same receipt id and project sequence); no second event was
visible in `event_head_seq`. A subsequent show by slug and UUID confirmed the
updated name/settings. The old human name was not an address, while the slug
`north-star-final` and UUID remained valid. This is the desired rename
behavior.

`projects select north-star-final --scope workspace --cwd
$ASTRID_PROJECTS_ROOT --json` and the equivalent UUID/user-scope calls returned
the selected project DTO, with no receipt (consistent with the documented
file-side preference). Repeating selection was harmless. There is no public
selection read-back in this surface, and omitting `--project` from
`timelines list` produced argparse exit 2, so selection does not route future
commands.

## Timeline routing proof

The intended project received one tiny default timeline:

```bash
python3 -m astrid timelines create orientation-proof \
  --project north-star-final --name 'Orientation Proof' \
  --config '{"width":320,"height":180,"duration":1}' \
  --registry '{"assets":{}}' --default \
  --idempotency-key timeline-create-1 --json
```

The response returned timeline slug, UUID, ULID, config version 1, and
`is_default: true`. Repeating the exact create/key returned the identical
receipt/result. `projects show north-star-final` then showed
`settings.default_timeline_id` pointing to the timeline, and both
`timelines list --project north-star-final` and listing by the project UUID
returned exactly that one default timeline.

Cross-project misuse was probed without creating any accidental data:

- `timelines show --project north-star orientation-proof --json` -> exit 1,
  `not_found`.
- `timelines show --project north-star <intended timeline UUID> --json` -> exit
  1, `not_found`.
- `timelines save --project north-star orientation-proof ...` -> exit 1,
  `not_found`, with no receipt.
- Final `timelines list` for both `north-star` and `south-star` was `[]`.

Thus no timeline or default pointer landed in another project. The intended
project had one timeline; both comparison projects had zero.

## Fresh-shell rediscovery

In a new `zsh` with only `PATH`, `ASTRID_PROJECTS_ROOT`, and the repository
working directory, the only remembered fact was the human name “North Star
Final Cut”. The shell ran public `projects list --json`, selected the exact
matching name with `jq` to obtain `north-star-final`, then ran `projects show`
and `timelines list --project north-star-final`. It rediscovered the correct
project and the expected timeline without reading SQLite or project files.

The same exercise with the duplicate human name “North Star” would be
ambiguous: list returns both `north-star` and `south-star`, and `projects show
'North Star'` fails. Agents need a unique human name or an explicit slug/id.

## Failure and idempotency probes

| Probe | Observed result | Assessment |
|---|---|---|
| Duplicate project slug `north-star` | exit 1, `conflict`, `{}` details | Correct rejection; poor recovery detail |
| Duplicate project name “North Star” under `south-star` | success | Names are not unique; documented nowhere in the CLI result |
| Nonexistent project `does-not-exist` show/update | exit 1, `not_found`, `{}` details | Stable typed error; no candidate/help detail |
| Human name as project ref | exit 1, `validation_error`, `{}` details | Correctly rejects unsupported identifier, but opaque |
| Duplicate timeline slug in same project | exit 1, `conflict`, `{}` details | Correct rejection |
| Invalid JSON `--settings '{bad'` | argparse usage error, exit 2 | Clear enough; not a five-key JSON envelope because parse failed |
| Exact repeated project update | same receipt/result, no new state | Strong idempotency |
| Exact repeated timeline create | same receipt/result, no duplicate | Strong idempotency |
| Wrong-project timeline show/save | exit 1, `not_found`, no receipt | Correct isolation/no mutation |

All JSON-mode responses observed had the documented five top-level keys
`ok`, `data`, `error`, `receipt`, and `idempotency_key`; reads had null
receipts and mutations had receipts, except selection which intentionally has
no receipt.

## Final public-state verification

Final `doctor --json` was healthy: `ok: true`, data paths accessible, SQLite
quick-check clean, no foreign-key violations, and all four schema-version
families reported (`core=1, references=1, shots=1, timeline=1`). Public final
reads showed:

```text
projects list:
  North Star          / north-star
  North Star Final Cut / north-star-final
  North Star          / south-star

north-star-final show:
  name = North Star Final Cut
  settings = {client: live-ux, current_stage: orientation,
              default_timeline_id: 00dbe260-44aa-56c8-895d-784e8ec697cd}

timelines north-star-final: [orientation-proof, is_default=true]
timelines north-star:       []
timelines south-star:       []
```

The disposable root was then cleaned. No product or repository runtime data
was changed.

## Friction classification

- **Discoverability:** good for the first command and family census; the
  create hint from doctor is especially actionable.
- **Identity:** good machine identity (UUID + immutable slug); weak human
  identity because duplicate names are accepted and names cannot be used as
  refs.
- **State comprehension:** good project/timeline DTOs and receipts; plan.md
  is a useful but empty scaffold and path must be derived manually.
- **Safe mutation:** strong. Updates and timeline creation are receipted and
  exactly repeatable with explicit idempotency keys; rename preserves
  addressability.
- **Routing/isolation:** strong when explicit `--project` is supplied; wrong
  project refs fail closed and final lists prove no cross-project mutation.
- **Recovery:** typed exit codes and five-key JSON are consistent; empty error
  details make recovery less agent-friendly.
- **Selection/current project:** safe but limited to a preference. It does not
  establish an implicit current project for product commands.
