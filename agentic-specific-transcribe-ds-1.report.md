# Agentic Transcribe Report — agentic-specific-transcribe-ds-1 (v10)

## 1. What you did

Attached to project `agentic-specific-transcribe-ds-1` via `astrid attach` to bind
the session. Confirmed `/tmp/audio_example.mp3` already existed (it was a 1-second
silent clip synthesized in a prior run). Searched for the transcribe executor with
`astrid executors search transcribe`, which returned exactly one hit —
`builtin.transcribe` at a strong relevance score of 36.75. Inspected the executor
definition with `astrid executors inspect builtin.transcribe` to confirm its
inputs (`audio`, required file) and outputs (`transcript`, create_or_replace).

Discovered the executor's metadata references the hype pipeline as its
`command_builder`. Ran `astrid executors run builtin.transcribe --input
audio=/tmp/audio_example.mp3 --out /tmp/transcribe_output`. The initial attempt
failed because the hype pipeline module (`astrid.packs.builtin.hype.run`) has a
module-level `guard_canonical_entrypoint` check that requires
`ASTRID_INTERNAL_INVOCATION=1` in the parent process environment. This guard fires
at import time — before any subprocess is spawned — because the executor runner
imports `hype/run.py` to resolve the pipeline step's build command.

Reran with `ASTRID_INTERNAL_INVOCATION=1` prefixed. The runner succeeded: it
printed the constructed command (`python3 -m astrid.packs.builtin.transcribe.run
--audio ... --out ...`), invoked the transcribe subprocess (which inherited the
env var and thus passed its own guard), and produced three output artifacts —
`transcript.json`, `transcript.srt`, and `transcript.txt` — in
`/tmp/transcribe_output/`. The silent clip yielded a single hallucinated segment
("you"), which is expected for near-silent input; the executor exercised the full
Whisper API path end-to-end.

## 2. What tools you discovered

The single tool surfaced was **`builtin.transcribe`**, a built-in executor with id
`builtin.transcribe`. I discovered it through two commands:

- `python3 -m astrid executors search transcribe` — returned the executor with a
  relevance score of 36.75, the short description "Transcribe source audio to
  transcript.json via Whisper," and keywords including "whisper", "audio",
  "transcribe", "text", "speech", "transcript". This search was unambiguous: only
  one result, and the id matches the task verbatim.

- `python3 -m astrid executors inspect builtin.transcribe` — yielded the full
  executor definition: inputs (`audio: file, required`), outputs (`transcript:
  file, create_or_replace` with path template `{out}/transcript.json`), cache mode
  (`sentinel` on `transcript.json`), and the pipeline step metadata that routes it
  through the hype orchestrator's `build_pool_steps()` command builder.

Additionally, `python3 -m astrid executors list` surfaced all 50+ executors
alphabetically, where `builtin.transcribe` appeared between `builtin.tile_video`
and `builtin.triage`. The list display includes the short description, making it
scannable even without the search subcommand.

No orchestrator was involved — this was a single-executor invocation through the
canonical `astrid executors run` CLI surface. The executor's STAGE doc at
`astrid/packs/builtin/transcribe/STAGE.md` was a 3-line stub identifying it as a
"Built-in Astrid executor for the `transcribe` pipeline stage." This is minimal
but sufficient given the inspect output.

## 3. Discoverability notes

The executor name was **obvious** — `builtin.transcribe` matches the verb
"transcribe" from the task description exactly. `executors search transcribe`
surfaced it cleanly as the sole result with a strong relevance score. A broader
search like `executors list` would also reveal it in alphabetical order, though
with 50+ executors a human might need to scan. The keywords metadata
(`whisper`, `audio`, `transcribe`, `text`, `speech`, `transcript`) is rich and
would match many natural-language queries.

The `executors inspect` output was sufficient to determine the required input
(`audio`, a file path), the output format, and the example invocation pattern.
The short description — "Transcribe source audio to transcript.json via
Whisper" — clearly communicates that it uses OpenAI's Whisper API, which implies
an API key requirement (confirmed by reading `run.py`, which sources
`OPENAI_API_KEY` from environment or `.env` files).

The STAGE doc (`astrid/packs/builtin/transcribe/STAGE.md`) is a 3-line stub that
does not add materially to the inspect output. It lacks parameter documentation,
an end-to-end example with actual file paths, and any mention of the
`ASTRID_INTERNAL_INVOCATION` requirement. An agent relying solely on the STAGE
doc would not know how to invoke the executor without also running `inspect`.
There is no `astrid executors doc` subcommand — the canonical way to get
documentation is `inspect`, which combines the YAML schema with the CLI-facing
example. This works but means the STAGE doc is effectively dead weight for
discovery.

## 4. Biggest UX gap

The single change that would most reduce "would the next agent find this in one
shot?" friction is **making `ASTRID_INTERNAL_INVOCATION=1` the default for the
`astrid` CLI process itself**, rather than requiring it only in subprocess
environments. Currently the `guard_canonical_entrypoint` check lives at module
level in `astrid/packs/builtin/hype/run.py` (line 9), and the CLI does not set
this variable before importing executor modules. This means **every
`pipeline_step` executor run** — including `builtin.transcribe`, `builtin.scenes`,
`builtin.shots`, and the dozen others wired through
`hype.run.build_pool_steps()` — fails on first attempt with a misleading error
message that names `builtin.hype` instead of the executor the user actually
invoked.

The fix could be as simple as adding `os.environ.setdefault("ASTRID_INTERNAL_INVOCATION", "1")`
early in `astrid/pipeline.py:main()` or in `astrid/__main__.py`, before any
subcommand dispatch. This would make the guard transparent to CLI users while
still blocking direct `python -m astrid.packs.builtin.*.run` invocations. Without
this, every agent (and human) attempting `astrid executors run builtin.transcribe`
hits a confusing "this pack (builtin.hype) is not meant to be invoked directly"
error that requires debugging into the runner internals to discover the env-var
workaround. For a task as straightforward as "transcribe this file," that is a
10× friction multiplier on what should be a one-command operation.
