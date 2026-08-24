# Replay: media, character reference, and shot state

Verdict: PASS (with a discoverability/framing caveat)

## Environment

Live CLI session only, with a fresh isolated root:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-replay-x1QXou
```

I began with `python3 -m astrid --help`. The census exposed the product and
operational families plus the nested mounts `timelines shots` and
`media references`. Mount-specific help was then used to discover their verbs.

## Commands exercised

```text
python3 -m astrid projects create character-board --name "Character Board" --json
python3 -m astrid projects show character-board --json
python3 -m astrid media import avatars/forager.png --project character-board --json
python3 -m astrid media import avatars/portrait.png --project character-board --json
python3 -m astrid timelines create primary --project character-board --name "Primary" --default --json
python3 -m astrid media references create --project character-board --kind character --name Hero --media <portrait-media-id> --json
python3 -m astrid media references associate <hero-ref-id> --project character-board --media <forager-media-id> --role canonical --ordinal 1 --json
python3 -m astrid timelines shots create --project character-board --name "Hero shot" --json
python3 -m astrid timelines shots add <shot-id> --project character-board --media <forager-media-id> --json
python3 -m astrid timelines shots add <shot-id> --project character-board --media <portrait-media-id> --json
python3 -m astrid timelines shots reorder <shot-id> --project character-board --items <portrait-item-id>,<forager-item-id> --json
python3 -m astrid timelines shots remove <shot-id> <forager-item-id> --project character-board --json
```

Imported media IDs:

```text
forager.png  5a856926-840d-51f5-b96b-05f40d113d30
portrait.png caf669c0-2ff2-5df7-ad2f-b81184e2b364
```

## Fresh final-state evidence

After mutation, I performed fresh reads (not mutation-response reuse):

```text
python3 -m astrid timelines shots show <shot-id> --project character-board --json
python3 -m astrid media references show <hero-ref-id> --project character-board --json
python3 -m astrid media list --project character-board --json
python3 -m astrid timelines list --project character-board --json
python3 -m astrid timelines show primary --project character-board --json
python3 -m astrid timelines shots list --project character-board --json
```

Final `Hero` reference (kind `character`): portrait is canonical, ordinal 0,
and `is_primary: true`; forager is canonical, ordinal 1, and
`is_primary: false`.

Final `Hero shot` (id `69fa9f88-b60a-5b61-8a82-1dba0a2c1993`) fresh `show`:

```text
position 0: portrait.png (media caf669c0-2ff2-5df7-ad2f-b81184e2b364)
```

The fresh shot read expanded the item into position, media ID, media name,
and managed-local path. Final shot contents are therefore reconstructible
without relying on old mutation responses.

Fresh `media list` still contained both forager.png and portrait.png, with
verified managed-local locations. Removing the shot item preserved forager in
the project media library.

Fresh timeline reads showed `primary` exists and `is_default: true`; fresh
shots list showed `Hero shot` exists.

## UX observations

- The workflow was complete and recoverable through the public CLI.
- `shots show` is strong: it expands each item into media name/path, making a
  fresh read sufficient to verify ordering and final contents.
- Nested help made exact item-ID operations clear after requesting mount help.
- Remaining friction is conceptual: `timelines create --default` and
  `timelines shots create` are separate surfaces, and help does not explain
  whether/how a project-level reusable shot belongs to a timeline. In this
  run, the default timeline remained an empty document while the shot existed
  in the project-level shots mount. If timeline-document membership is
  intended, help exposes neither that relationship nor an attachment command.

## Result

PASS for the requested observable final state and fresh-read verification.
Follow-up UX issue: clarify timeline-versus-project-level reusable-shot
semantics in top-level and nested help, or expose an explicit attachment
operation if membership is intended.
