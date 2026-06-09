# Fork and Update Workflow

How to scaffold a personal pack, fork capabilities, detect and review local
edits, and manage updates. Personal packs live alongside shipped packs but are
gitignored by convention — they're yours, not Astrid's.

## Scaffolding a Personal Pack

```bash
# Create a new local pack (gitignored by convention)
python3 -m astrid packs new my_tools

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

Copy any shipped capability into your pack for customization:

```bash
# Fork an executor into your local pack
python3 -m astrid executors fork rendering.render

# Fork an orchestrator
python3 -m astrid orchestrators fork video_editing.hype

# Fork an element
python3 -m astrid elements fork effects text-card
```

The forked copy lands in `astrid/packs/local/` with its id rewritten to
`local.<name>`. Provenance is tracked in `.astrid_fork_state.json` so you can
detect local edits later.

Use `--deep` on orchestrator forks to recursively copy all child executors and
orchestrators:

```bash
# Shallow fork — copy just this capability
python3 -m astrid executors fork rendering.render

# Deep fork — recursively fork all child executors/orchestrators too
python3 -m astrid executors fork generation.generate_image --deep
python3 -m astrid orchestrators fork video_editing.hype --deep

# Overwrite an existing fork
python3 -m astrid executors fork rendering.render --overwrite
```

### Fork Provenance

Each forked capability records in `.astrid_fork_state.json`:

- `forked_from` — the original canonical id
- `upstream_version` — the version at fork time
- `file_hashes` — SHA-256 hashes of all files at fork time

This provenance powers dirty detection (see below).

### Shallow vs Deep

- **Shallow** (`--deep` not set): Copy only the named capability. Its child
  references still point to the original builtin executors/orchestrators.
- **Deep** (`--deep`): Recursively fork all child executors and orchestrators
  referenced by an orchestrator's graph. Elements only support shallow forks.

## Overriding Without Editing Originals

Once you have a fork, you can redirect all consumers to use your version:

```bash
# Set the override
python3 -m astrid executors override set rendering.render local.render

# Route an element to a replacement
python3 -m astrid elements override set effects text-card effects my-text-card

# List active overrides
python3 -m astrid executors override list
python3 -m astrid orchestrators override list
python3 -m astrid elements override list

# Remove when done
python3 -m astrid executors override remove rendering.render
```

Now any code, orchestrator, or agent that asks for `rendering.render` (or its
legacy alias `builtin.render`) gets `local.render` instead. The original is
untouched.

Overrides are persisted in `astrid/packs/local/.overrides.json` and survive
restarts. The `OverrideStore` is thread-safe.

Override keys are the *canonical* capability id, not the alias. When a caller
requests `builtin.render` (a legacy alias), the registry first resolves it to
`rendering.render` (the canonical id), then checks the override store. One
override covers all aliases that point to the same canonical target.

## Common Pattern: Fork + Override

1. Fork the capability: `python3 -m astrid executors fork rendering.render`
2. Edit the local copy at `astrid/packs/local/executors/render/`
3. Set the override: `python3 -m astrid executors override set rendering.render local.render`

Now every consumer that references `rendering.render` (or its legacy alias
`builtin.render`) gets your customized version transparently.

## Detecting Local Edits (Dirty Check)

Astrid tracks whether a forked capability has been modified since fork time:

```bash
# Check one capability
python3 -m astrid executors dirty check local.render
python3 -m astrid orchestrators dirty check local.hype
python3 -m astrid elements dirty check effects my-text-card

# List all dirty capabilities
python3 -m astrid executors dirty list
python3 -m astrid orchestrators dirty list
python3 -m astrid elements dirty list
```

The inspect commands also expose edit state in the `_capability` block:

```bash
python3 -m astrid executors inspect local.render --json
# → "_capability": { "local_edit_state": "dirty", ... }
```

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
time. This file is written by the fork command and lives in the capability's
root directory.

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
happens), you can promote those edits to a proper fork:

```bash
# Fork the edited capability into your local pack, preserving changes
python3 -m astrid executors fork rendering.render --overwrite
```

The `--overwrite` flag replaces any existing fork. Without it, the fork command
refuses to overwrite.

**Better workflow:** Fork first, then edit the fork. This keeps the original
pristine and makes dirty detection meaningful.

## Workflow: Review Before Promote

```bash
# 1. Check what's dirty
python3 -m astrid executors dirty list

# 2. Inspect the changes
python3 -m astrid executors inspect local.render --json | python3 -m json.tool

# 3. If happy, set the override to make it the default
python3 -m astrid executors override set rendering.render local.render

# 4. Verify the override is active
python3 -m astrid executors override list
```

## Workflow: Revert a Dirty Fork

```bash
# 1. Remove the override (if set)
python3 -m astrid executors override remove rendering.render

# 2. Delete the fork directory
rm -rf astrid/packs/local/executors/render/

# 3. Re-fork from the original
python3 -m astrid executors fork rendering.render
```

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
  isolate its child capabilities from upstream changes unless you use `--deep`.
- **No semantic merge:** If upstream changes after you fork, there's no tooling
  to merge those changes into your fork. The `conflict` edit state exists in
  the schema but is not computed.
- **No upstream version tracking:** The `upstream_version` field in fork state
  is recorded but not compared against current upstream versions.
