You're in `/Users/peteromalley/Documents/reigh-workspace/Astrid`. Your project is `$SLUG`. Use `--agent $AGENT_ID` for any `--agent` flag.

**Your job:** at `/tmp/example_comfy.json` you'll find a ComfyUI workflow JSON. It takes a positive prompt (currently `"a serene mountain lake at dawn"`) and produces an image. Wrap this workflow as a new Astrid executor so an agent can later say "give me an image of X" and have it route through this workflow.

The executor must:

- Take a `prompt` argument so the positive prompt is parameterized, not hard-coded.
- Take an `out` path argument for where the result image lands.
- Actually load `/tmp/example_comfy.json` (or a copy you stage inside the pack) at run-time and inject the prompt — don't bake the JSON into Python.
- Route through whatever existing Astrid surface already wraps ComfyUI, not a fresh HTTP client.

You pick the pack and the qualified id (`<pack>.<name>`).

## Rules

- Use the existing Astrid executor-authoring path.
- Don't actually execute the workflow end-to-end against a real ComfyUI server — scaffold quality is what's under test.
- Don't edit anything outside the pack you're authoring into.
- Cap at ~60 shell calls. Don't abort.
- **Do NOT invoke `python -m astrid.packs.*` directly.** The only canonical CLI surfaces are `astrid executors run <id> ...` and `astrid orchestrators run <id> ...`. Bypassing them disqualifies the run regardless of artifacts produced.

## Report (under 400 words, markdown with sections labeled 1, 2, 3, ...)

The report MUST be at least 30 non-blank lines. Each numbered section MUST have at least 2 substantive sentences.


1. **What did you build?** Qualified id, pack, file paths, args your executor accepts.
2. **Comfy wrapping path.** Which existing Astrid surface did you route through? How did you find it? If you rolled your own, why?
3. **Prompt parameterization.** How does the prompt flow from `--prompt` into the workflow JSON node (which key, which node id)?
4. **Workflow JSON handling.** Does your executor load `/tmp/example_comfy.json` at run-time, copy it into the pack, or embed it inline? Why that choice?
5. **Discovery friction.** What did you have to search for, read, or guess at to find the comfy wrapping path? Anything in the docs / `astrid executors search` that should have surfaced it sooner?
6. **One-line verdict on the comfy-wrap UX.** Blunt.

Honest reporting — confusion is data.
