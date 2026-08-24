# Live media-integrity UX wave 1

Date: 2026-08-23  
Mode: live CLI usage only (`python3 -m astrid`), no test runner or source inspection  
Disposable root: `/tmp/astrid-live-media-integrity-aKVXAG`

## Verdict

**Partial pass / fix required.** The media identity model, managed-copy integrity, relation isolation, and final doctor state behaved correctly. The live user journey is not fully reliable because managed-local `relocate` is effectively unusable and missing managed files surface as an opaque internal error. External-local relocation works end-to-end.

## Journey and evidence

- Started from `python3 -m astrid --help` and `astrid help`. The public census exposed the eight families, `media import/list/show/verify/relocate/relate`, the two realms (`managed_local`, `external_local`), and the frozen relation kinds (`derived_from`, `variant_of`, `uses_as_input`, `mask_for`, `audio_for`).
- Created `media-lab` and `other-lab`; both project `plan.md` skeletons were present and readable.
- Imported `tests/packs/builtin/generate_image/fixtures/tiny.png` twice into `media-lab` with the default realm. Both imports returned the same media ID `9faa0a10-0e77-5039-8687-28c0026fb41e`, hash `b1ff9c8e…a946640`, and 69-byte size. The second import did not create a second media row or duplicate managed location: duplicate bytes are one project-scoped identity.
- Imported `avatars/portrait.png` once. It became media ID `68e132b1-efd6-5ff2-9557-632936a32b2c`, hash `e470eefb…d348930`, 1,626,110 bytes. Managed copies were visible at the expected SHA-256 paths and had matching byte sizes.
- `media verify --realm managed_local` succeeded for tiny, portrait, and (later) the same tiny bytes in `other-lab`; each receipt advanced the project sequence and returned the complete read model.
- Moved the managed tiny file to a held path inside the disposable root. Verifying the now-unavailable managed locator returned exit 1 with `ok=false`, `code=internal_error`, `error_type=MediaPathError`, and message `prepared file must be a regular file: <path>`. `media show` and `media list` still showed the original identity/location and did not mutate any rows.
- Tried public `media relocate --realm managed_local` with the held regular file, a file under `.astrid/media`, a SHA-structured path, a `file://` URI, and the original path after restoration. Every attempt returned `validation_error` with empty details and `the request failed validation`; no state changed. This is the critical recovery gap.
- To exercise the supported public relocation path, imported tiny once as `external_local` (same media ID, adding an external location), copied the bytes to a disposable-root path, then ran `media relocate --realm external_local`. It succeeded with receipt command `core.media.replace_location`, preserved the media ID/hash, and `media verify --realm external_local` succeeded afterward.
- Restored the held managed file before finishing and re-verified it. No held file remained. A stray probe copy created while probing relocation was moved out of the managed tree, leaving canonical managed files intact.
- Related portrait to tiny with the supported direction/kind: `--from 68e132b1-… --to 9faa0a10-… --kind variant_of`. Both media read models showed the same single `variant_of` edge.
- Imported tiny into `other-lab`; it received a different project-scoped media ID `2759faee-fb3d-5194-a640-9d5cf488fc6e` despite the same content hash and managed locator path. Attempting to relate `media-lab` portrait to that `other-lab` ID under `--project media-lab` returned `not_found`. A before/after read proved no partial relation was written; `other-lab` remained relation-free.
- Final `media list`, managed verifies, external verify, and `doctor --json` were clean. Doctor reported accessible data paths, managed SHA-256 locators resolving, SQLite quick-check OK, no foreign-key violations, and all schema versions OK.

## Severity-ranked UX critique

### P1 — Managed-local relocation cannot recover a missing locator

The public help advertises `media relocate` for both realms, but managed-local relocation rejected every plausible regular-file destination with the same empty-details validation error. Once a managed file is unavailable, the user cannot use the advertised relocation path to repair it; only an out-of-band filesystem restore (or a separate re-import experiment) is apparent. This is a data-recovery workflow failure. Either support managed relocation with clear constraints, or remove/clarify the realm option and provide a documented recovery command.

### P1 — Missing managed files produce an internal error with no actionable path

`verify` on a missing locator returned `internal_error` / `MediaPathError` and redacted the path as `<path>`. A user needs a typed “locator missing” result naming the media ID and realm, with an explicit next action (`relocate`, restore, or re-import). The observed no-row-mutation behavior is good, but the error classification and message are not agent-usable.

### P2 — Realm policy is discoverable only by trial and error

The help lists both realms but does not explain that external relocation accepts an ordinary existing file while managed relocation rejects equivalent paths. A short example and constraints in `media relocate --help` would prevent the dead-end seen in this wave.

### P2 — Relation isolation and atomicity are strong, but the user must carry UUIDs

Cross-project relation attempts fail cleanly with `not_found` and leave both projects unchanged. However, `media relate` requires opaque UUIDs for both endpoints; there is no path/name lookup or readable choice surface. The import response does expose IDs, but a human or agent must manually shuttle them into later commands. A project-scoped name/search/read convenience would reduce friction without weakening identity semantics.

### P3 — Identity semantics are excellent but should be surfaced more explicitly

Repeated managed imports dedupe to one identity and one managed location, while the same bytes in another project get a different project-scoped ID. This is coherent and safe. The CLI could make the deduplication explicit in the import result (for example, `created=false` / `existing=true`) so the user does not have to infer it from repeated IDs and locations.

## Final assessment

**PASS:** content-hash identity/deduplication, managed-copy bytes, successful verify, supported `variant_of` relation, project isolation, no partial write on rejected cross-project relation, final filesystem/database health.  
**FAIL/P1:** advertised managed-local relocate/recovery path and actionable missing-locator error UX.  
**Recommended next fix:** make `managed_local` relocation either work atomically with documented destination rules or return a precise unsupported-operation error plus a supported rehydrate workflow; add a typed missing-locator error with recovery guidance.
