# Replay: capability discovery / quick-start truth (independent LIVE UX)

Date: 2026-08-23 (Europe/Berlin)  
Scope: fresh black-box replay from the public root help, `SKILL.md`, public
docs, capability `STAGE.md` files, and the public SDK. No source inspection,
tests, git history, or prior QA/finding reports were used. No paid/cloud call
was made.

## Verdict

**PARTIAL PASS — useful and mostly recoverable, but not a clean acceptance
pass.** The public capability registry is rich, typed, and fast enough for a
cold agent; the CLI census and SDK dispatch work; dry-run generation,
understanding, transcription, render, and hype routes are observable; and a
real local timeline render completed. Guarded runner protection and
pre-admission validation work. Three truth gaps materially reduce quick-start
reliability: the documented hype `inputs` are silently ignored, local image /
video dry-runs still preflight a missing optional package, and audio/transcribe
live API-key failures lose their actionable message in the returned SDK error.

## Disposable setup

All state was isolated under `/tmp/astrid-replay2.tz5XUh` with:

```bash
export ASTRID_PROJECTS_ROOT=/tmp/astrid-replay2.tz5XUh
python3 -m astrid projects create demo --name 'Replay Demo' --json
```

Fixtures were generated locally with ffmpeg: a 1-second MP4 with tone,
two PNG frames, and a WAV tone. The fixture timeline/assets were copied into
the project before the real render because project-scoped rendering correctly
enforces project ownership. No credentials were set or printed.

## Discovery and census

| Public action | Result | Time |
| --- | --- | ---: |
| `python3 -m astrid --help` | Eight families plus two nested mounts; exit 0 | 0.17 s |
| `python3 -m astrid doctor --json` on empty root | Honest failing checks for missing managed store; no write | 0.20 s |
| `projects create demo --name 'Replay Demo' --json` | Project, SQLite kernel, `plan.md`, five-key JSON envelope | 0.37 s |
| `projects list --json` | One project, five-key JSON envelope | 0.28 s |
| first `sdk.discover(include_installed=False)` | 93 capabilities: 66 executors, 12 orchestrators, 15 elements | 0.828 s |
| second discovery in same process | Same 93 capability inventory | 0.572 s |
| third discovery in same process | Same 93 capability inventory | 0.650 s |

Discovery on a second empty temporary root was checked before/after with
`find`; it created no files or `.astrid` store. Capability lookups were done
by qualified id and explicit kind. The selected public capability records
contained inputs, outputs, isolation/network declarations, and provenance.

Best public matches observed:

| Need | Public capability/kind | Relevant declared contract |
| --- | --- | --- |
| Local image | `generation.generate_image` / executor | `mode`, `model`, `execution`; image directory + manifest outputs; local backend requires VibeComfy/ComfyUI |
| FLF video | `generation.generate_video` / executor | `mode=flf`, `image_ref`, `image_end_ref`; `wan-2.2/cloud` or `ltx-2.3/local` wired |
| Audio understanding | `understanding.understand` / executor, or `understanding.audio_understand` / executor | dispatcher requires `mode=audio` + `audio`; underlying executor emits `analysis.json` + manifest |
| Transcription | `editorial.transcribe` / executor | audio input; transcript JSON/SRT/TXT/chunk plan/manifest outputs |
| Timeline render | `rendering.render` / executor | timeline (+ optional assets registry); video + provenance outputs |
| Multi-step editorial | `video_editing.hype` / orchestrator | transcribe → … → render → review → validate child pipeline |

## Literal public quick-start replay

All SDK calls used `kind=` and `project="demo"`; no direct runner was used
for these paths. `ASTRID_INTERNAL_INVOCATION=1` was set only as the documented
legitimate SDK-call guard context.

| STAGE quick-start | Safe mode and result | Time |
| --- | --- | ---: |
| `generation.generate_image` (`z-image`, `t2i`, `local`) | Rejected before execution because this environment lacks the optional `vibecomfy` package. Error gave an install/retry command; no network call. Cloud dry-run of the same text-to-image shape passed with normalized command. | 0.814 s local preflight; 1.309 s cloud dry-run |
| `generation.generate_video` FLF (`ltx-2.3`, `local`) | Rejected for the same missing VibeComfy package. `ltx-2.3/cloud/flf` correctly rejected as an unwired backend; `wan-2.2/cloud/flf` with both frame refs passed dry-run. | 0.703 s local preflight; 0.740 s wan cloud dry-run |
| `generation.generate_audio` (`stable-audio-3-medium`, music, cloud) | Dry-run passed; normalized command showed model/mode/backend/prompt and no network. | 0.695 s |
| `understanding.understand` (`mode=audio`, WAV) | Dry-run passed and forwarded `--mode audio --audio <fixture>`. | 0.525 s |
| `understanding.audio_understand` (WAV) | Dry-run passed; normalized command included audio and analysis output location. | 0.542 s |
| `editorial.transcribe` (WAV) | Dry-run passed; normalized command and transcript output contract were present. | 0.940 s |
| `rendering.render` (timeline) | Dry-run passed. Real project-owned render also passed locally using the fixture asset registry. | 0.558 s dry-run; 12.323 s real |
| `video_editing.hype` (video + brief) | Literal STAGE `inputs={video,brief}` dry-run passed but silently dropped both inputs. Replaying with public `orchestrator_args=(--video,…,--brief,…)` produced the expected command. | 0.575 s literal; 0.464 s corrected |

Real render evidence: run `f80de305ae9aa8d4a9b9ca03e4`, status succeeded,
one child succeeded, local H.264/AAC MP4 was 1920x1080, 10.048 s, 467,425
bytes, with a provenance sidecar.

## Guard and validation checks

Direct module commands for image, video, understanding, transcribe, and
render were intentionally attempted without the internal marker. Every one
exited 2 with the bounded message that the pack is not meant to be invoked
directly and that callers should use the SDK; this is consistent with the
STAGE “internal runner command (not a public entrypoint)” labels.

Pre-admission SDK checks were exercised in dry-run mode:

- invalid understanding mode `banana` → `CapabilityValidationError` with
  bounded valid options `audio, image, video, visual` and recovery text;
- dispatcher `mode=audio` without audio → `CapabilityMissingInputError` with
  `provide --audio` recovery;
- dispatcher `mode=video` with only audio → `CapabilityMissingInputError`
  with `provide --video` recovery;
- image/video/audio unsupported modes returned model-specific available modes;
- missing audio on direct audio-understanding/transcribe returned typed
  missing-input errors;
- all pre-admission errors left `runs list --project demo` and `tasks list`
  empty at that point.

Lookup recovery behavior was mostly strong: typo
`generation.generate_imag` suggested three nearby qualified IDs; wrong-kind
lookup named the registered kind, gave `kind='executor'`, and bounded nearby
matches; bare `fade` returned two explicit element candidates. An exact
unknown `totally.unknown` returned only `unknown executor 'totally.unknown'`
with no suggestion, so “unknown” recovery is weaker than typo/wrong-kind
recovery.

## Network, key, input, and output truth

Registry inspection agreed that generation and understanding/transcription
capabilities declare network use; generation records expose `FAL_KEY` (and
audio generation also `WAVESPEED_API_KEY`) in metadata. Audio-understanding
and transcription STAGE files correctly say OpenAI API key + HTTP, and their
outputs are declared with concrete paths. The lower-level records, however,
reported `metadata.env=null` and `secrets_required=[]` for both, despite
`required_permissions=[network, environment]`.

No-key live-safe probes were made without network credentials:

- image/video/audio cloud paths failed with `FAL_KEY not found` before any
  paid request;
- audio understanding and transcription failed without an OpenAI key;
- failed runs were recorded in the local kernel as failed (expected lifecycle);
  no outputs were published.

The generation failures preserved the key cause and recovery in the returned
SDK error. Audio-understanding and transcription printed the actionable key
message to subprocess stderr, but their returned SDK `error` only said
`handler_failed`/`returncode`, omitting the key and recovery. This is a
material agent UX truth gap. The dispatcher metadata itself has no outputs,
which is defensible as a thin switch, but makes the underlying output contract
discoverability-dependent on a second lookup.

## Wrong turns and corrections

1. Literal local image/video dry-runs hit missing VibeComfy preflight. I did
   not install it or start ComfyUI; cloud dry-run / a wired cloud FLF cell were
   used instead, with no network.
2. `ltx-2.3/flf/cloud` was rejected as unavailable, matching STAGE’s wired-cell
   table. `wan-2.2/flf/cloud` was the safe cloud dry-run substitute.
3. Real render first rejected a fixture outside project ownership. Copying the
   fixture into `demo/` and retrying succeeded; this demonstrates the
   containment rule rather than bypassing it.
4. The literal hype SDK example accepted `inputs` but dropped video/brief.
   Passing the documented public `orchestrator_args` tuple preserved them in
   the normalized command.

## Acceptance summary

- Public census/discovery and cold/warm measurement: **PASS**.
- Best capability selection and explicit kind/project examples: **PASS**.
- Five-plus canonical STAGE quick-starts in dry-run/safe local/fake mode,
  including image, FLF video, audio understanding, transcribe, render, hype:
  **PASS with local-runtime and hype caveats**.
- No user-facing direct guarded runner invocation: **PASS**; direct runner
  guard rejection independently verified.
- Invalid mode/missing modality pre-admission rejection: **PASS**.
- Typo/unknown/wrong-kind bounded viable recovery: **PARTIAL** (exact unknown
  has no suggestion).
- Network/API-key/input/output metadata truthful: **PARTIAL** (key metadata
  and returned error propagation gaps for audio-understand/transcribe).
- Discovery side-effect-free: **PASS** on fresh empty root.

Overall: **PARTIAL PASS; report findings are UX/contract follow-ups, not a
blocking failure of the local CLI/SDK kernel or renderer.**
