# Aliases vs Forks vs Overrides

Three mechanisms for redirecting or customizing capability resolution. This
guide builds on the vocabulary in
[docs/megaplan/epics/pack-system/pack-contract.md](megaplan/epics/pack-system/pack-contract.md).

## Quick Decision Table

| You want to... | Use | Persistence | Scope |
|---|---|---|---|
| Give a capability a second public name | Alias | In pack manifest | All consumers |
| Make a local copy you can edit freely | Fork | On disk in local pack | Your project |
| Redirect a capability id to a replacement | Override | `.overrides.json` in local pack | Your project |
| Shadow a builtin with a local replacement | Override | `.overrides.json` in local pack | Your project |
| Maintain backward-compat after renaming | Alias | In pack manifest | All consumers |

---

## Aliases

**What:** A one-way mapping from a short public name (the alias) to a
fully-qualified canonical id.

**How it works:** The `AliasResolver` (in `astrid/core/alias_resolver.py`)
maintains a registry of `alias → canonical_id` mappings. Aliases are resolved
transitively — chains of aliases are flattened to the ultimate canonical
target. Cycle detection runs at registration time and rejects invalid graphs.

**Register an alias** in `pack.yaml`:

```yaml
aliases:
  generate-image: builtin.generate_image
  gen-img: builtin.generate_image
```

Multiple aliases can point to the same canonical id. Aliases can be marked
deprecated with a message shown to consumers.

**When to use:** You renamed a capability but old consumers still reference the
old id. Instead of breaking them, add an alias.

**When NOT to use:** You want to change behavior. Aliases are identity-only;
they don't alter execution. Use a fork or override for behavioral changes.

---

## Forks

**What:** A complete local copy of a capability that you own and can modify.

**How it works:** The fork command copies the capability's manifest, entrypoint,
and supporting files into your local pack. The forked copy gets a new qualified
id under the `local` pack namespace. Provenance metadata tracks the original
source.

### Fork Commands

```bash
# Shallow fork — copy just this capability
python3 -m astrid executors fork builtin.render
python3 -m astrid orchestrators fork builtin.hype
python3 -m astrid elements fork effects text-card

# Deep fork — recursively fork all child executors/orchestrators too
python3 -m astrid executors fork builtin.generate_image --deep
python3 -m astrid orchestrators fork builtin.hype --deep

# Overwrite an existing fork
python3 -m astrid executors fork builtin.render --overwrite
```

### Fork Provenance

Each forked capability records:
- `forked_from` — the original canonical id
- `upstream_version` — the version at fork time
- `file_hashes` — SHA-256 hashes of all files at fork time (stored in
  `.astrid_fork_state.json`)

This provenance powers dirty detection (see [update-workflow.md](update-workflow.md)).

### Shallow vs Deep

- **Shallow** (`--deep` not set): Copy only the named capability. Its child
  references still point to the original builtin executors/orchestrators.
- **Deep** (`--deep`): Recursively fork all child executors and orchestrators
  referenced by an orchestrator's graph. Elements only support shallow forks.

**When to use:** You want to customize a capability's behavior without affecting
the original. The fork becomes your copy — edit freely.

**When NOT to use:** You just want to use a different capability id. Use an
alias or override instead.

---

## Overrides

**What:** A redirection rule that says "when anything asks for capability X,
give it capability Y instead."

**How it works:** The `OverrideStore` (in `astrid/core/override.py`) maintains a
thread-safe in-memory mapping of `(type, id) → target_id`, persisted to
`astrid/packs/local/.overrides.json`. Overrides are checked at resolution time
— whenever a registry looks up a capability by id, the override store is
consulted first.

### Override Commands

```bash
# Route all requests for builtin.render to your local fork
python3 -m astrid executors override set builtin.render local.render

# Route an element to a replacement
python3 -m astrid elements override set effects text-card effects my-text-card

# List all active overrides
python3 -m astrid executors override list
python3 -m astrid orchestrators override list
python3 -m astrid elements override list

# Remove an override
python3 -m astrid executors override remove builtin.render
```

### Common Override Pattern: Fork + Override

1. Fork the capability: `python3 -m astrid executors fork builtin.render`
2. Edit the local copy at `astrid/packs/local/executors/render/`
3. Set the override: `python3 -m astrid executors override set builtin.render local.render`

Now every consumer that references `builtin.render` gets your customized version
transparently.

**When to use:** You have a fork (or another pack's capability) and want it to
be the default resolution for a given id.

**When NOT to use:** You want the original and your copy to coexist under
different ids. Just fork without setting an override.

---

## Interaction Between the Three

Resolution order when looking up a capability id:

1. **Override check** — is there an active override for this id? If yes, resolve
   to the target id and restart resolution.
2. **Alias resolution** — is the id an alias? If yes, resolve to the canonical
   id and restart resolution.
3. **Registry lookup** — find the capability by canonical id in the loaded
   registries.

This means overrides take priority over aliases, and both redirect before the
final registry lookup.
