# Replay: audio/video preflight 2

## Verdict

PASS for the requested pre-admission safety boundary on a fresh isolated
project. Both dry and live typed calls rejected before admission; the fresh
project ended with zero runs, tasks, and media, and no output/staging files.

## Live usage

Fresh root: `/tmp/astrid-replay-audio-video-preflight-9AuK8U`

Project: `motion-sound-lab`

Local fixtures:

- `assets/tiny.png`
- `assets/portrait.png`
- `assets/water-splash-2s.mp3`

Calls were made through the typed facade (`astrid.generate.video` and the new
`astrid.generate.audio`), each once with `dry_run=True` and once with
`dry_run=False`.

### Missing end frame

`ltx-2.3`, mode `flf`, execution `local`, with `start_frame=tiny.png` and no
end frame:

```text
CapabilityPreconditionError
Local generation is not ready: local generation requires the 'vibecomfy'
Python package; it is not installed in the Python environment Astrid is
using. Next: /Users/peteromalley/.pyenv/versions/3.11.11/bin/python3 -m pip
install vibecomfy && /Users/peteromalley/.pyenv/versions/3.11.11/bin/python3
-m vibecomfy --help
```

The same typed error and guidance appeared in dry and live mode. It rejected
before admission. Note: because the local-runtime precondition is evaluated
first on this host, the missing-end-frame-specific message was not reached.

### Complete local video

`ltx-2.3`, mode `flf`, execution `local`, between `tiny.png` and
`portrait.png`, produced the identical typed `CapabilityPreconditionError`
and actionable VibeComfy installation guidance in dry and live mode. No run
was admitted.

### Typed local audio

The typed audio facade was discoverable and callable. `ace-step`, mode
`music`, execution `local`, prompt “a 2 second water splash”, duration `2`
rejected identically in dry and live mode:

```text
CapabilityValidationError
Execution 'local' is not available for model 'ace-step' mode 'music'.
Available: cloud
```

### Cloud-only audio/local pair

`minimax-music-3`, mode `music`, execution `local`, with a supplied
`lyrics_prompt`, rejected identically in dry and live mode:

```text
CapabilityValidationError
Execution 'local' is not available for model 'minimax-music-3' mode 'music'.
Available: cloud
```

No cloud or paid fallback was attempted.

## Fresh-state checks

Immediately after all calls, the CLI reported:

- `runs list --project motion-sound-lab`: `data=[]`
- `tasks list --project motion-sound-lab`: `data=[]`
- `media list --project motion-sound-lab`: `data=[]`
- no generated outputs or staging directories; only the SQLite kernel files,
  project metadata, and the three local fixtures existed.

