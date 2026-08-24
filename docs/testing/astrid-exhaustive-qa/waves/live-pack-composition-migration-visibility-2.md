# Live pack-composition and migration-visibility replay 2

Date: 2026-08-24 (Europe/Berlin)  
Method: black-box live agent UX through public `python3 -m astrid` commands;
no source inspection, SDK scripting, test execution, database inspection/edit,
or product changes  
Verdict: **P1 NOT REPRODUCED in the current workspace.** Reference-first,
shot-first, and timeline-only roots all exposed the complete schema-pack set
and completed canonical visualization plus rendering.

## Question under test

The suspected P1 was that using one optional domain pack—especially
references—could initialize or recompose the kernel with only part of the
available schema-pack migration set. A later canonical timeline operation
could then fail because the timeline migration/table was not visible. The
replay intentionally varied the first optional-domain action and executed
every command in a new CLI process.

Acceptance checks:

| Check | Reference-first | Shot-first | Timeline-only control |
| --- | --- | --- | --- |
| Fresh project initializes | Pass | Pass | Pass |
| Doctor exposes `core=1` | Pass | Pass | Pass |
| Doctor exposes `references=1` | Pass | Pass | Pass |
| Doctor exposes `shots=1` | Pass | Pass | Pass |
| Doctor exposes `timeline=1` | Pass | Pass | Pass |
| Optional entity creates | Reference pass | Shot pass | N/A |
| Canonical timeline creates | Pass | Pass | Pass |
| Canonical visualization succeeds | Pass | Pass | Pass |
| Version-pinned render succeeds | Pass | Pass | Pass |
| Rendered media decodes | Pass | Pass | Pass |
| Optional entity remains unchanged | Pass | Pass | N/A |
| Timeline remains at version 1 | Pass | Pass | Pass |
| New-process exact retry changes result | No | Not needed | Not needed |

## Public pack and migration visibility

Only documented public surfaces were used to discover composition state:

```bash
python3 -m astrid media references --help
python3 -m astrid timelines shots --help
python3 -m astrid timelines visualize --help
python3 -m astrid timelines render --help
python3 -m astrid doctor --help
```

Help exposed both nested pack surfaces:

```text
astrid media references
  create update archive unarchive associate link set-primary list show

astrid timelines shots
  list show create add remove reorder
```

On a pristine root, public doctor returned `state:"uninitialized"` and no
schema versions, as expected. Immediately after the first project creation in
every lane, and again after reference/shot/timeline actions, doctor returned:

```text
state: ready
schema_versions: core=1, references=1, shots=1, timeline=1
sqlite_quick_check: quick_check ok
fk_integrity: no foreign key violations
```

This is the maximum migration visibility available through the public CLI. It
shows that project bootstrap in the current workspace composes all four schema
packs even when the next requested domain is only references, only shots, or
only timelines.

## Shared render fixture

A deterministic 64×64 purple PNG was created outside all projects only to
supply the reference's required media row:

```bash
ffmpeg -hide_banner -loglevel error \
  -f lavfi -i color=c=purple:s=64x64 -frames:v 1 \
  /private/tmp/astrid-pack-compose-reference.png -y
```

Every canonical timeline used one 1-second text clip, an authoritative 64×64
30-fps theme canvas, and an MP4 output declaration. All timeline and media
state was admitted only through Astrid's public CLI.

## Lane A: reference first

Disposable root:

```text
/private/tmp/astrid-pack-compose-reference.8Jd8xG
```

### Exact command ordering

```bash
python3 -m astrid doctor \
  --projects-root /private/tmp/astrid-pack-compose-reference.8Jd8xG --json

ASTRID_PROJECTS_ROOT=/private/tmp/astrid-pack-compose-reference.8Jd8xG \
python3 -m astrid projects create reference-lab \
  --name 'Reference Lab' --json

python3 -m astrid doctor \
  --projects-root /private/tmp/astrid-pack-compose-reference.8Jd8xG --json

ASTRID_PROJECTS_ROOT=/private/tmp/astrid-pack-compose-reference.8Jd8xG \
python3 -m astrid media import \
  /private/tmp/astrid-pack-compose-reference.png \
  --project reference-lab --json

ASTRID_PROJECTS_ROOT=/private/tmp/astrid-pack-compose-reference.8Jd8xG \
python3 -m astrid media references create \
  --project reference-lab --kind object --name 'Purple Tile' \
  --media bf710e79-50ea-50fc-ad8f-3cb1834d7539 \
  --description 'Pack composition probe' --json

python3 -m astrid doctor \
  --projects-root /private/tmp/astrid-pack-compose-reference.8Jd8xG --json

ASTRID_PROJECTS_ROOT=/private/tmp/astrid-pack-compose-reference.8Jd8xG \
python3 -m astrid timelines create main \
  --project reference-lab --name Main --default \
  --config '<64x64 one-second text timeline>' \
  --registry '{"assets":{}}' --json

ASTRID_PROJECTS_ROOT=/private/tmp/astrid-pack-compose-reference.8Jd8xG \
python3 -m astrid timelines visualize \
  --project reference-lab --timeline-slug main \
  --layout linear --format md --filmstrip off --json

ASTRID_PROJECTS_ROOT=/private/tmp/astrid-pack-compose-reference.8Jd8xG \
python3 -m astrid timelines render main \
  --project reference-lab --expected-version 1 \
  --output-name reference-main.mp4 --json
```

### IDs and outcomes

```text
project:            f4d30079-a986-5bc1-a450-c0c9ab5fc644
media:              bf710e79-50ea-50fc-ad8f-3cb1834d7539
reference:          24475305-57dc-56a5-8372-716854978d58
timeline UUID:      c0f1ea04-c0ca-5b28-8586-9a7b87a42143
timeline ULID:      zw02q184dd78r1cs9y1w3d4f74
visualize run:      d4dd3754d367dbeb5ea7ddd3fc
visualize task:     7e8cb26863d92484f27c5d7855
visualize attempt:  01m0ssz93fzad0bjjkm3s5trth
render run:         a8c14eed60c28a173780e88545
render task:        c61beb186f18879db01e405700
render attempt:     01m0sszj3afxha4z7vaj3mm42m
```

Every JSON envelope had `ok:true` and `error:null`. The visualize manifest was
published to managed CAS. Render published both `reference-main.mp4` and its
provenance sidecar.

### Independent-process restart replay

Every command above was already a fresh Python process. To make process
restart behavior explicit, the exact visualize and render commands were
issued again later from two more processes.

Both returned the same durable identities:

```json
{
  "restart_visualize_same_run_task_attempt": true,
  "restart_render_same_run_task_attempt": true,
  "run_count_before_and_after_retries": 2
}
```

The visualize retry completed in about 2 seconds and the render retry in about
1 second; neither admitted a duplicate run or re-rendered output. Restarting
the CLI process did not reveal or cure a composition problem because the
first attempt was already healthy.

### No unintended mutation

After reference creation, visualization, rendering, and exact retries:

- `media references show` returned the original reference ID, name, primary
  media, metadata, timestamps, and `event_head_seq:1`;
- `timelines show` returned the original config and `config_version:1`;
- `timelines history` contained exactly one version-1 `timeline.created`
  event;
- `runs list` contained exactly the two expected successful runs.

There was no error transaction whose mutation needed rollback; all expected
product state remained stable across the cross-pack operations.

## Lane B: shot first

Disposable root:

```text
/private/tmp/astrid-pack-compose-shot.goQ0la
```

### Exact command ordering

```bash
python3 -m astrid doctor \
  --projects-root /private/tmp/astrid-pack-compose-shot.goQ0la --json

ASTRID_PROJECTS_ROOT=/private/tmp/astrid-pack-compose-shot.goQ0la \
python3 -m astrid projects create shot-lab --name 'Shot Lab' --json

ASTRID_PROJECTS_ROOT=/private/tmp/astrid-pack-compose-shot.goQ0la \
python3 -m astrid timelines shots create \
  --project shot-lab --name 'Empty Probe Shot' \
  --metadata '{"purpose":"pack-composition"}' --json

python3 -m astrid doctor \
  --projects-root /private/tmp/astrid-pack-compose-shot.goQ0la --json

ASTRID_PROJECTS_ROOT=/private/tmp/astrid-pack-compose-shot.goQ0la \
python3 -m astrid timelines create main \
  --project shot-lab --name Main --default \
  --config '<64x64 one-second text timeline>' \
  --registry '{"assets":{}}' --json

ASTRID_PROJECTS_ROOT=/private/tmp/astrid-pack-compose-shot.goQ0la \
python3 -m astrid timelines visualize \
  --project shot-lab --timeline-slug main \
  --layout linear --format md --filmstrip off --json

ASTRID_PROJECTS_ROOT=/private/tmp/astrid-pack-compose-shot.goQ0la \
python3 -m astrid timelines render main \
  --project shot-lab --expected-version 1 \
  --output-name shot-main.mp4 --json
```

### IDs and outcomes

```text
project:        157a7aa3-3b4e-53cf-b13e-374bc71adda6
shot:           b6ea612e-38fc-5269-bf18-bf3e1c624be8
timeline:       de016e83-3855-52d4-b199-16091e29ba2d
visualize run:  da43c690015398e26f7f305e28
render run:     7444b11b6a46ad759da229d463
```

Again every envelope had `ok:true` and `error:null`. Final `shots show`
returned the original empty shot with the same ID, metadata, timestamps, and
`event_head_seq:1`. Timeline history remained exactly one version-1 create
event, and runs contained only the successful visualization and render.

## Lane C: timeline-only control

Disposable root:

```text
/private/tmp/astrid-pack-compose-control.8Xj5s6
```

Exact order:

```bash
python3 -m astrid doctor \
  --projects-root /private/tmp/astrid-pack-compose-control.8Xj5s6 --json
ASTRID_PROJECTS_ROOT=/private/tmp/astrid-pack-compose-control.8Xj5s6 \
python3 -m astrid projects create control-lab --name 'Control Lab' --json
ASTRID_PROJECTS_ROOT=/private/tmp/astrid-pack-compose-control.8Xj5s6 \
python3 -m astrid timelines create main \
  --project control-lab --name Main --default \
  --config '<64x64 one-second text timeline>' \
  --registry '{"assets":{}}' --json
python3 -m astrid doctor \
  --projects-root /private/tmp/astrid-pack-compose-control.8Xj5s6 --json
ASTRID_PROJECTS_ROOT=/private/tmp/astrid-pack-compose-control.8Xj5s6 \
python3 -m astrid timelines visualize \
  --project control-lab --timeline-slug main \
  --layout linear --format md --filmstrip off --json
ASTRID_PROJECTS_ROOT=/private/tmp/astrid-pack-compose-control.8Xj5s6 \
python3 -m astrid timelines render main \
  --project control-lab --expected-version 1 \
  --output-name control-main.mp4 --json
```

Results:

```text
project:        c7e31f03-b785-5ea3-b138-e57594a3b6a0
timeline:       840e3085-96c5-59c6-bf83-9b491a7b96b9
visualize run:  28a0153b16e9e99880356fbd01
render run:     804d3a407dcb27569ffa6899d7
doctor:         core=1, references=1, shots=1, timeline=1
```

The control behaved identically to both optional-pack lanes.

## Render verification

Each managed render artifact was independently probed with public `ffprobe`:

```bash
ffprobe -v error \
  -show_entries stream=codec_name,width,height,pix_fmt \
  -show_entries format=duration -of json '<managed artifact>'
```

All three reported:

```json
{
  "video": {
    "codec_name": "h264",
    "width": 64,
    "height": 64,
    "pix_fmt": "yuvj420p"
  },
  "audio": {"codec_name": "aac"},
  "duration": "1.045333"
}
```

This rules out a superficial success envelope with missing or undecodable
render output.

## Verdict and bounded hypothesis

The reported pack-composition P1 is **not reproducible against the current
workspace through the public one-shot CLI**. The evidence is stronger than a
single happy path:

- all three fresh roots initialized with the complete visible migration set;
- references and shots each preceded canonical timeline creation in separate
  lanes;
- visualization and rendering both exercised admitted executor subprocesses;
- every operation ran in a separate Python process;
- exact post-restart retries reused immutable successful results;
- extension rows and canonical history remained intact.

Without source inspection, the remaining hypotheses are:

1. the P1 was observed against an earlier or intermediate shared-worktree
   composition state and has already disappeared from the current checkout;
2. it requires a long-lived in-process client whose pack registry is composed
   incrementally, a lifecycle not exposed by the public one-shot CLI used in
   this assignment;
3. it depends on an additional pack-selection/environment input absent from
   the documented default CLI surface.

Public doctor gives no per-migration row detail beyond the four schema-version
pairs, and public help exposes command mounts rather than the internal pack
composition graph. Therefore this replay cannot identify the earlier internal
cause, only falsify the current public reproduction under the requested
orders.

Severity for the current CLI build: **no live defect observed**. Keep the
original P1 open only if another lane can provide an exact failing command,
environment variable set, or long-lived process sequence; replay that exact
surface before changing product code.
