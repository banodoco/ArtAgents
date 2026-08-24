# Replay: managed-media integrity and recovery

## Verdict

**PASS.** Live CLI usage in a fresh root exercised import, verify, managed-media loss, help-guided recovery, typed wrong-byte rejection, atomicity, identity/hash/locator preservation, and doctor health.

## Evidence

- Fresh root: `/tmp/astrid-replay-media-y508sc`; project: `media-lab`.
- Imported `tiny.png` (`known-good.png` was an independent source copy). Astrid returned media id `af8d189b-db9b-5b0c-ae87-8877c677b3a0`, byte size `18945`, and SHA-256 `38037bcf18c7f9b950da2e1a2d8800d38fb27637ccda293d38368a3704b67f18`.
- Initial `media verify ... --realm managed_local --json` succeeded.
- Removed the canonical managed locator, then verified. The typed `integrity_error` named the media id and `managed_local`, said “locator is unavailable; no write occurred”, and supplied the exact recovery command using `media relocate ... --realm managed_local --source <source-file>`.
- `media relocate --help` clearly documented managed recovery, canonical SHA-256 destination, source hash verification, and no database/file state change on mismatch. It also showed the understandable `external_local --locator` form.
- Recovery from `known-good.png` succeeded atomically. A subsequent verify returned the same media id, byte size, content hash, and canonical locator.
- Deleted the canonical file again and attempted recovery from `wrong.png` (one extra byte). Astrid returned typed `integrity_error` with expected and source SHA-256 values and “no write occurred”; the canonical file remained absent (`FILE_EXISTS_AFTER_WRONG=no`). `media show` retained the same identity/hash/locator metadata and prior verification timestamp, with no new location mutation.
- Recovered again from `known-good.png`; final verify succeeded. `doctor --json` returned `ok: true` for data paths, managed media paths, SQLite quick check, foreign keys, and schema versions.

## UX observations

The missing-locator error is actionable without private knowledge: it identifies the affected realm/media and prints a copyable recovery command. The wrong-byte response is especially strong for agent UX because it exposes both hashes and explicitly states that no write occurred. The help text makes the managed-versus-external relocation distinction discoverable.

