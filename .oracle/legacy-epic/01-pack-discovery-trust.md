# Explore: pack discovery order and trust boundary

Project root: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. This is read-only exploration for a renderer-plugin epic. Do NOT edit files.

## What to establish

1. In `astrid/core/pack/discovery.py`, `loader.py`, and `store.py`: the exact
   precedence order among source / local / extra / environment / installed
   packs. Name the functions and constants that determine priority, and how
   "active installed revisions" are represented (which field in the installed
   store marks active vs inactive).
2. In `astrid/core/pack/install_local.py`, `install_trust.py`, and
   `validate.py`: how pack installation trust is decided today. Is there an
   explicit `trusted` field anywhere, or is trust implicit in the install
   path? What happens to a downloaded-but-not-installed pack — is it
   discoverable? Executable?
3. Where pack permissions are loaded (`pack/permissions.py`) and how a pack
   declares them in `pack.yaml` — list the permission vocabulary (network,
   subprocess, filesystem?) and how the runtime checks them.
4. How `discover_pack_metadata()` is called today and what its result shape
   is (fields: source kind, pack id, path, active?).

## Report format

Ranked findings, each with file:line evidence. Max 300 words. End with:
- Verified facts (bullets, file:line)
- Unknowns (bullets)
- Risks for a plugin system that must NOT execute untrusted packs
- Suggested approach (2-3 sentences)
