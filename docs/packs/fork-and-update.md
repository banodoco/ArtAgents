# Fork and Update Workflow

How to scaffold a personal pack, fork capabilities, detect and review local
edits, and manage updates. Personal packs live alongside shipped packs but are
gitignored by convention — they're yours, not Astrid's.

## Scaffolding a Personal Pack

```bash
# Create a new local pack (gitignored by convention)
python3 -m astrid.core.pack.cli new my_tools

# The pack is created at astrid/packs/my_tools/ with:
#   pack.yaml          — pack manifest
#   executors/          — your executors go here
#   orchestrators/      — your orchestrators go here
#   elements/           — your elements go here
#   skill/SKILL.md / README.md  — documentation stubs
```

The `astrid/packs/local/` pack is pre-shipped as the conventional scratch space
and is already in `.gitignore`. Use it for one-off experiments, or create a
named personal pack for organized collections.

## Forking Capabilities Into Your Personal Pack

Copy any shipped capability into your pack for customization. Forking copies
the capability's manifest, entrypoint, and supporting files into the local
pack — executors and orchestrators fork into `astrid/packs/local/` under
their kind directory, elements fork under their kind as well. The forked copy
lands with its id rewritten to `local.<name>`. Provenance is tracked in
`.astrid_fork_state.json` so you can detect local edits later.

Use a deep fork on orchestrators to recursively copy all child executors and
orchestrators:

- **Shallow fork** — copy just the named capability. Its child references
  still point to the original shipped executors/orchestrators.
- **Deep fork** — recursively fork all child executors and orchestrators
  referenced by an orchestrator's graph. Elements only support shallow forks.
- **Overwrite** — re-fork over an existing fork, replacing it.

### Fork Provenance

Each forked capability records in `.astrid_fork_state.json`:

- `forked_from` — the original canonical id
- `upstream_version` — the version at fork time
- `file_hashes` — SHA-256 hashes of all files at fork time

This provenance powers dirty detection (see below).

## Overriding Without Editing Originals

Once you have a fork, you can redirect all consumers to use your version.
Overrides are managed by editing `astrid/packs/local/.overrides.json`:

- Set the override — route all requests for `rendering.render` to your local
  fork with `{"executor": {"rendering.render": "local.render"}}`.
- Route an element to a replacement — add an entry under the element kind
  key, mapping the element id to its replacement (e.g.
  `{"effects": {"text-card": "my-text-card"}}`).
- List active overrides — read the same file.
- Remove when done — delete the entry.

Now any code, orchestrator, or agent that asks for `rendering.render` (or its
legacy alias `legacy.render`) gets `local.render` instead. The original is
untouched.

Overrides are persisted in `astrid/packs/local/.overrides.json` and survive
restarts. The `OverrideStore` is thread-safe.

Override keys are the *canonical* capability id, not the alias. When a caller
requests `legacy.render` (a legacy alias), the registry first resolves it to
`rendering.render` (the canonical id), then checks the override store. One
override covers all aliases that point to the same canonical target.

## Common Pattern: Fork + Override

1. Fork the capability into the local pack (see Forking above).
2. Edit the local copy at `astrid/packs/local/executors/render/`.
3. Add the override to `astrid/packs/local/.overrides.json`:
   `{"executor": {"rendering.render": "local.render"}}`.

Now every consumer that references `rendering.render` (or its legacy alias
`legacy.render`) gets your customized version transparently.

## Detecting Local Edits (Dirty Check)

Astrid tracks whether a forked capability has been modified since fork time.
Local edit state is computed per capability: any forked copy whose files
differ from the fork-time snapshot reports as dirty, and all dirty
capabilities can be listed in one pass. The inspect output also exposes edit
state in the `_capability` block — for example, JSON inspection of a local
fork shows `"_capability": { "local_edit_state": "dirty", ... }`.

## Clean vs Dirty vs Forked States

| State | What it means | How to reach it |
|---|---|---|
| **Clean (original)** | Shipped with Astrid, never forked | Default for builtin-shipped capabilities |
| **Clean (fork)** | Forked but unmodified since fork time | Fork, then don't edit |
| **Dirty** | Forked and modified locally | Fork, then edit files |
| **Conflict** | Forked, upstream has a newer version | Not yet implemented (deferred) |

A capability with empty `forked_from` (never forked) always reports `"clean"`.

## How Detection Works

Implemented in `astrid/core/dirty.py`. Two strategies, tried in order:

### 1. Git-Backed Detection (Preferred)

If the capability directory lives inside a git worktree, Astrid runs
`git status --porcelain` scoped to that directory. Any uncommitted changes
(modified, added, deleted files) make the capability dirty.

- **Pros:** Fast, respects `.gitignore`, handles renames, accurate
- **Cons:** Only works inside git repos

### 2. Hash-Based Fallback

If git is not available (or fails), Astrid falls back to comparing current
file SHA-256 hashes against those stored in `.astrid_fork_state.json` at fork
time. This file is written when a capability is forked and lives in the
capability's root directory.

The fallback:
- Walks all regular files in the capability directory (excluding `.git` and
  `.astrid_fork_state.json` itself)
- Computes SHA-256 for each file
- Compares against stored hashes
- Any mismatch → dirty

If no `.astrid_fork_state.json` exists (e.g., the capability was created
manually, not via fork), the state defaults to `"clean"`.

## Promoting In-Place Edits to Forks

If you've edited a shipped capability in place (not recommended, but it
happens), you can promote those edits to a proper fork: re-fork the edited
capability into your local pack with overwrite semantics, which copies the
current state — edits included — into the fork and replaces any existing
fork. Without overwrite, the re-fork refuses to replace an existing fork.

**Better workflow:** Fork first, then edit the fork. This keeps the original
pristine and makes dirty detection meaningful.

## Workflow: Review Before Promote

1. Check which forked capabilities are dirty (see Detecting Local Edits).
2. Inspect the changes — review the edited files in the fork directory (or
   the fork's `_capability.local_edit_state` in inspect output).
3. If happy, add the override to `astrid/packs/local/.overrides.json` to make
   your fork the default resolution for the id.
4. Verify the override is active by reading `.overrides.json` (or resolving
   the id again and confirming it returns the fork).

## Workflow: Revert a Dirty Fork

1. Remove the override entry (if set) from `astrid/packs/local/.overrides.json`.
2. Delete the fork directory: `rm -rf astrid/packs/local/executors/render/`.
3. Re-fork from the original — copy the shipped capability into the local
   pack again.

## Convention: Gitignore

The `astrid/packs/local/` directory is gitignored by default. If you create
additional personal packs (e.g., `astrid/packs/my_tools/`), add them to
`.gitignore`:

```gitignore
astrid/packs/local/
astrid/packs/my_tools/
```

This keeps your experiments out of version control while Astrid discovers them
at runtime.

## Interaction with Updates

When Astrid updates and a shipped capability changes, your forks are unaffected
— they're separate copies. The dirty check helps you identify which forks
diverge from their originals.

## Deferred Work

The following are not yet implemented:

- **No remote registry:** Fork state is local-only. No sharing or syncing of
  forks between machines.
- **No dependency isolation:** Forking an orchestrator does not automatically
  isolate its child capabilities from upstream changes unless you deep-fork it.
- **No semantic merge:** If upstream changes after you fork, there's no tooling
  to merge those changes into your fork. The `conflict` edit state exists in
  the schema but is not computed.
- **No upstream version tracking:** The `upstream_version` field in fork state
  is recorded but not compared against current upstream versions.
