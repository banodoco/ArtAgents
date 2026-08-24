# Managed media rehydrate UX fix

Date: 2026-08-23  
Source wave: [`live-media-integrity-1.md`](../waves/live-media-integrity-1.md)  
Mode: live CLI proof plus narrow SDK regression guards

## Outcome

The two P1 media-integrity UX failures are fixed.

- A missing managed locator now returns `integrity_error` rather than
  `internal_error`. The error names the project-scoped media id and realm and
  includes the public recovery command with `--source <source-file>`.
- `media relocate --realm managed_local --source <regular-file>` now performs
  managed rehydration. The source is SHA-256 checked against the existing
  immutable media identity, copied through a same-directory temporary file to
  the canonical digest locator, and the location projection is updated only
  after that publication. The media id and content hash do not change.
- `external_local` keeps its existing reference-in-place behavior and uses
  `--locator` as before.
- The CLI help explains the two modes and shows both commands. Exactly one of
  `--locator` or `--source` is required at the CLI boundary.

## Live journey

Disposable root: `/tmp/astrid-live-media-rehydrate.IP4b90`

1. Created project `media-rehydrate` and imported the 69-byte tiny PNG.
2. Verified the managed copy, moved the canonical file to a held source path,
   and ran `media verify`. The command failed with exit 1 and this actionable
   shape:

   ```json
   {
     "code": "integrity_error",
     "details": {
       "media_id": "de19884e-fa6b-50e8-9b66-9178b0489917",
       "realm": "managed_local",
       "recovery": "python3 -m astrid media relocate de19884e-fa6b-50e8-9b66-9178b0489917 --project media-rehydrate --realm managed_local --source <source-file>"
     }
   }
   ```

3. Ran the documented recovery command with the held regular file. It
   succeeded, returned the original media id and hash, restored the canonical
   bytes, and `media verify --realm managed_local` passed.
4. `doctor --json` passed with accessible managed-media paths, SQLite quick
   check, foreign-key integrity, and all schema versions healthy.
5. Tried rehydration with a different file. It returned `integrity_error`,
   exit 1, and the canonical file SHA-256 was identical before and after the
   rejected command. The subsequent managed verify and doctor both passed.

## Guards and verification

The focused SDK/CLI suites pass:

```text
pytest -q tests/sdk/test_media.py tests/v10/test_domain_cli_media_references.py
71 passed

pytest -q tests/sdk/test_media.py
20 passed
```

The added regression guard covers missing-locator error details, successful
managed rehydration with identity preservation, and wrong-byte rejection with
no canonical-file mutation.
