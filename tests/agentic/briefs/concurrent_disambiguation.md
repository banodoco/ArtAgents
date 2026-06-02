You're in `/Users/peteromalley/Documents/reigh-workspace/Astrid`. Your project is `${SLUG}`. Other agents are running concurrently against OTHER projects in the same workspace — that's the test.

**Your job:** complete `builtin.agent_probe` on `${SLUG}` end-to-end.

## Two important behaviors to watch for

1. **Cross-project binding leakage**: when you run `python3 -m astrid next` with NO flags after `astrid attach ${SLUG}`, the system should bind to YOUR project (`${SLUG}`), not some other concurrent agent's project. If you see a different slug than `${SLUG}` in `astrid next` output, that's a bug — flag it.

2. **Auto-resolution warning**: when `astrid next` auto-resolves your session via `.astrid-session` file, it should print on stderr: `(auto-resolved session for project '<slug>' via .astrid-session; pass --project explicitly to override)`. If you see this and the slug is wrong, OR if you see it bind silently without printing, flag it.

## Setup

- Use `--agent ${AGENT_ID}` for any `--agent` flag.
- Pass `--project ${SLUG}` explicitly when in doubt.
- Use `astrid next` as the universal port-of-call.

## Rules

- Don't edit anything outside `produces/` dirs.
- Don't abort.
- Cap ~30 calls.
- **Do NOT invoke `python -m astrid.packs.*` directly.** The only canonical CLI surfaces are `astrid executors run <id> ...` and `astrid orchestrators run <id> ...`. Bypassing them disqualifies the run regardless of artifacts produced.

## Report (under 300 words, markdown, numbered sections)

Each numbered section MUST have at least 2 substantive sentences.


1. **Did the run reach "Run complete"?**
2. **Cross-project binding**: did you EVER see `astrid next` (or `status`) bind to a different project than `${SLUG}`? Specifically:
   - Did you see the auto-resolve warning?
   - When you saw it, was the resolved slug correct (`${SLUG}`)?
   - Did you ever have to pass `--project ${SLUG}` explicitly to recover from a wrong auto-resolution?
3. **Compared to the v7 probe** (where agents reported "session kept resolving to different project slugs"), was THIS run cleaner?
4. **Friction points.**
5. **Was the concurrency disambiguation visible to you, or invisible?**

Honest reporting. Run tag: `${RUN_TAG}`.
