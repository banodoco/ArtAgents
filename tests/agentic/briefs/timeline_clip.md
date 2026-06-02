# Brief: exercise timeline clip edit verbs

You are agent `${AGENT_ID}` working in project `${SLUG}` (run tag `${RUN_TAG}`).

## The ask

Exercise the timeline clip edit verbs (`clip.added`, `clip.removed`, `clip.moved`)
through the canonical `astrid timelines` CLI surface.

## Bind a session FIRST (required)

Every `astrid timelines ...` command needs a session bound to your shell. The
binding lives in the `ASTRID_SESSION_ID` environment variable, and it does NOT
persist across separate shell invocations. So you must bind it and run your
timeline commands **in the same shell call**, by `eval`-ing the export line that
`astrid attach` prints:

```bash
# Bind the session for THIS shell, then run timeline commands together:
eval "$(python3 -m astrid attach ${SLUG} --as agent:${AGENT_ID} | grep '^export')"
echo "bound session: $ASTRID_SESSION_ID"   # sanity check — must be non-empty
python3 -m astrid timelines create clip-test --name "Clip Test"
python3 -m astrid timelines track add clip-test --kind visual --track-id visual --label Visual
python3 -m astrid timelines clip add clip-test --kind video --asset a1 --track visual
python3 -m astrid timelines clip remove clip-test --clip-id a1
python3 -m astrid timelines show clip-test
```

If you split these across separate shell calls, the session will be lost and you
will see `no session bound` / `A timeline command requires a bound session`. Keep
the `eval "$(... attach ...)"` and the timeline commands in one shell block.

## Steps

1. Bind a session (see above): `eval "$(python3 -m astrid attach ${SLUG} --as agent:${AGENT_ID} | grep '^export')"`
2. Create a timeline: `astrid timelines create clip-test --name "Clip Test"`
3. Add a visual track: `astrid timelines track add clip-test --kind visual --track-id visual --label Visual`
4. Add a clip: `astrid timelines clip add clip-test --kind video --asset a1 --track visual`
   (clip `--kind` is one of `video|image|audio|text|effect|opaque`; the *track*
   kind is `visual`, but a clip on a visual track is `--kind video`.)
5. Remove the clip: `astrid timelines clip remove clip-test --clip-id a1`
6. Verify the `assembly.jsonl` event log contains `clip.added` and `clip.removed` events.
7. Confirm that running `astrid timelines show clip-test` (read-only) does NOT add new events.

## Constraints

- Use only `python3 -m astrid timelines ...` CLI commands. Do NOT use `python -m astrid.packs.*`.
- The event log is at `<project>/timelines/<ulid>/assembly.jsonl`.

## Report back

When done, write a narrative report with these sections:

1. **What you did** — commands run, in order.
2. **Event log content** — what events appeared in `assembly.jsonl`.
3. **Read-only verification** — whether `astrid timelines show` mutated the event log.
4. **Biggest UX gap** — one thing that would make timeline clip editing easier.
