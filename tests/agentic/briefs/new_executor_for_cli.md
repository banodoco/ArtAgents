You're in `/Users/peteromalley/Documents/reigh-workspace/Astrid`. Your project is `$SLUG`. Use `--agent $AGENT_ID` for any `--agent` flag.

**Your job:** wrap this ffmpeg one-liner as a new Astrid executor called `clip_extract`:

```
ffmpeg -i {input} -ss {start} -t {dur} -c copy {output}
```

Inputs: a source video (`input` path), a start time in seconds (`start`), a duration in seconds (`dur`).
Output: a clipped video file (`output` path).

You pick the pack. The executor id must be qualified as `<pack>.clip_extract`. The result must be runnable through the standard Astrid executor surface, not a one-off Python script.

## Rules

- Use the existing executor-authoring path. Don't reinvent the folder layout.
- Don't shell-execute the executor against a real video — wiring + scaffold quality is what's under test, not ffmpeg.
- `executor.yaml` should declare `inputs`, `outputs`, and a `command.argv` that points at your `run.py`.
- `run.py` should parse the expected args and shell out to `ffmpeg` correctly (you can defer actual invocation behind a check, but the argv parsing must be real).
- Don't edit anything outside the pack you're authoring into.
- Cap at ~60 shell calls. Don't abort.
- **Do NOT invoke `python -m astrid.packs.*` directly.** The only canonical CLI surfaces are `astrid executors run <id> ...` and `astrid orchestrators run <id> ...`. Bypassing them disqualifies the run regardless of artifacts produced.

## Report (under 400 words, markdown with sections labeled 1, 2, 3, ...)

Each numbered section MUST have at least 2 substantive sentences.


1. **What did you build?** Qualified id, pack, file paths created.
2. **Authoring surface.** Which CLI verb scaffolded the executor (or did you copy a template by hand)? Did `astrid executors inspect <id>` work after?
3. **`executor.yaml` shape.** What did you put in `inputs`, `outputs`, `command.argv`? Anything unclear about the schema?
4. **`run.py` shape.** How do you parse args (argparse? sys.argv?)? How do you invoke ffmpeg? Did you guard against missing inputs?
5. **Discovery friction.** What did you have to read to figure out the authoring path? Anything you had to guess at?
6. **Did you ever confuse this with orchestrator authoring** (e.g., reach for `@orchestrator`, the DSL, `astrid author new`)? If so, what redirected you?
7. **One-line verdict on the executor-authoring UX.** Blunt.

Honest reporting — confusion is data.
