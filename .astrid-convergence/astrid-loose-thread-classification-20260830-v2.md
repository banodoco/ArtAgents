# Astrid loose-thread classification v2 — 2026-08-30

**Audit mode:** read-only inventory followed by one evidence-only report commit.
No Astrid source, product file, dirty checkout, lock, process, database,
remote, merge, deletion, or cleanup action was performed.

## Canonical identity and verdict

Canonical Astrid `main` and `origin/main` both resolve to:

```text
21a379f24ca2411f5b5222821bf05c447e4ab69f
```

Required convergence tips are contained by that commit:

| Required tip | Exact SHA | Result |
|---|---|---|
| Storyboard | `aa09089f473e5278057521ef1cd449a8e5290757` | ancestor of canonical main; merged/pushed |
| FFmpeg | `e983b0061ed94fc0c4e8e64dd0150d5f55506c2d` | ancestor of canonical main; merged/pushed |

The convergence slice is present, but the stronger claim that all Astrid code
is merged (or intentionally left/deleted) is **not proven**. Dirty source
checkouts, selected unreviewed patches, foreign Arnold integration, archived
runtime data, historical execution refs, and the unfinished Stage 1 T0–T6
gates remain.

For same-repository rows below, `behind/ahead` is relative to canonical Astrid
`main`. A zero ahead count means the committed tip is contained by main; it
does not classify dirty files in that checkout.

## Registered Astrid worktrees

| Exact path | Branch / HEAD | Base and relation | Dirty/unique content | Provisional disposition |
|---|---|---|---|---|
| `/Users/peteromalley/Documents/reigh-workspace/Astrid` | `codex/live-ux-pre-phase-b-20260824` / `7ac50c12e8e4d90988fee603ffdb9896e5628792` | Base `44bfda77fccafd6170711a2208f7b15a0be959ca`; 233 behind / 5 ahead | 550 tracked changes + 2 untracked. 547 deletions are `.oracle` evidence. Product edits: `remotion/src/Root.tsx`, `remotion/src/fonts.ts`, `storyboards/astrid-intro.storyboard.json`; untracked `remotion/src/fonts-local.ts`, `package-lock.json`. Unique commits: `43fb607df9c3073dc15a1ae92fe80fec91d13c25`, `b15976c949d7c5b8c5f23b11fe18cd92a46fc064`, `e12ba289ef272e53b617c519003fde27d244542c`, `d78df0183c86048d0022bbb252fd630b42ee86ed`, `7ac50c12e8e4d90988fee603ffdb9896e5628792`. | `MUST-INTEGRATE-BEFORE-STAGE1` for a manually rebuilt, reviewed local-font subset; whole checkout `ACTIVE-FOREIGN-PROTECT`. Never cherry-pick, clean, reset, or discard wholesale. |
| `/Users/peteromalley/Documents/reigh-workspace/Astrid-unified-oracle` | `oracle-unified-execution` / `96ad5021e4f120dbb55b7da58b8be903118f7015` | HEAD is merge-base; 233 behind / 0 ahead | 18 modified tracked files + 5 untracked. Repository contracts, user paths, schema/core vocabulary, event/import-cycle repairs, CLI/bridge changes, and tests. `git diff --check`: blank line at `astrid/core/events/registry.py:437`. | Selected neutral contract/cycle pieces `MUST-INTEGRATE-BEFORE-STAGE1` after clean extraction and focused tests; whole tree `ACTIVE-FOREIGN-PROTECT`. |
| `/Users/peteromalley/Documents/Astrid-oracle` | `oracle-run` / `b04ed2c7d5e89d82d428cb222413f9c9b3aac251` | Base `0b69557bfcca417bc32a3f0edff0753bac67712a`; 233 behind / 1 ahead | Unique commit `b04ed2c7d5e89d82d428cb222413f9c9b3aac251` (`feat: astrid resident — gateway-domain bot on the arnold custom-agent platform`). Untracked `.agentbox/astrid.env` and `arnold-brand-store/` (9 files below those entries). | `ACTIVE-FOREIGN-PROTECT`; Arnold/Discord resident integration is outside the neutral Stage 1 boundary. |
| `/Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle` | `oracle-packification` / `0c93fd8a661efa3601471c10b1e3304b17dccf61` | Base `dc296c3efd184832bde26770891f2161560d24c6`; 347 behind / 6 ahead | Clean planning/evidence commits: `3d78760c343ead1e31f297f94cb910254a52af9d`, `793bcb4e36f4abc6887f8320c72a1dfa730589fa`, `01b680815d61e14401161c18af3fdf68412a3492`, `8978e9ad66c792ecb8dc49667236e6331328620e`, `2da328fe058b03dc2d9b206b37de55b88957b493`, `0c93fd8a661efa3601471c10b1e3304b17dccf61`. | `ARCHIVE-PRESERVE`; planning provenance, not product code to merge. |
| `/private/tmp/astrid-gallery-projection` | detached / `02d187129d9294bc20d939840194bfd336648c50` | Base `85e0e5c7559a6667802f88740de5ff337f74e978`; 58 behind / 1 ahead | Clean; `git cherry main HEAD` is `-`; patch-equivalent to main. | `SUPERSEDED-DELETE-AFTER-HASH`; archive/hash and obtain owner confirmation first. |
| `/private/tmp/astrid-main-validation.TlNXR4` | detached / `b39a538daf3a74a5a3bef0a89d208a8e27d142a8` | 48 behind / 0 ahead | Clean old validation baseline. | `SUPERSEDED-DELETE-AFTER-HASH`. |
| `/private/tmp/astrid-parity-diagnostics.otCs9Y` | `codex/luna-renderer-parity-diagnostics` / `dc8fb287acb4748edf979e908ef43623b199347c` | Base `89c522e3a35b2fde366a4ec16b1c4b1c89217157`; 61 behind / 1 ahead | Clean; patch-equivalent to main. | `SUPERSEDED-DELETE-AFTER-HASH`. |
| `/private/tmp/astrid-schema-fix.cMghkd` | detached commit `00ba959dee2f80c50b849d29c7c925f2d60cb2ac` | Parent `daeb99639a7f61ff7ba7aab87980380237b12d9c`; checkout has no usable `.git` metadata and is registered prunable | Source tree is approximately 44 MB. Commit is patch-equivalent to main. | `SUPERSEDED-DELETE-AFTER-HASH`, but archive/hash source before any prune. |
| `/private/tmp/astrid-ulid-investigate.ogcV8B` | detached / `c8f840174a66f3bbdb2e809b8287eb38dc72d5cc` | Base `25dae25ce19f347c21767e7a559c63314b790bcb`; 59 behind / 1 ahead | Clean; patch-equivalent to main. | `SUPERSEDED-DELETE-AFTER-HASH`. |
| `/private/tmp/astrid-ulid-parent.BTsqRx` | detached / `d3a8294909aba625c9a58b0110eda77e2e6b5aef` | 60 behind / 0 ahead | Clean baseline. | `SUPERSEDED-DELETE-AFTER-HASH`. |
| `/private/tmp/astrid-uppercase-ulid-fix` | `codex/luna-uppercase-ulid-fix` / `c6a31ad1785d24fd454c4b4efbd2c54260548313` | Base `d3a8294909aba625c9a58b0110eda77e2e6b5aef`; 60 behind / 1 ahead | Clean; patch-equivalent to main. | `SUPERSEDED-DELETE-AFTER-HASH`. |
| `/Users/peteromalley/Documents/reigh-workspace/Astrid-live-main` | `main` / `21a379f24ca2411f5b5222821bf05c447e4ab69f` | canonical main | Clean. | Canonical source. |
| `/Users/peteromalley/Documents/reigh-workspace/Astrid-beta-convergence` | `integration/astrid-beta-convergence` / `21a379f24ca2411f5b5222821bf05c447e4ab69f` | 0 behind / 0 ahead | Clean; this report is the only new commit planned on this branch. | Convergence evidence branch. |
| `/Users/peteromalley/Documents/reigh-workspace/Astrid-stage1-beta` | `megado/astrid-stage1-beta` / `21a379f24ca2411f5b5222821bf05c447e4ab69f` | 0 behind / 0 ahead | Clean exact main. | Planning branch only; Stage 1 implementation remains open. |
| `/Users/peteromalley/Documents/reigh-workspace/Astrid-ffmpeg-oracle` | `megado/oracle-run-ffmpeg-text` / `e983b0061ed94fc0c4e8e64dd0150d5f55506c2d` | Required tip; ancestor of main | Clean. | Required tip merged/pushed. |
| `/Users/peteromalley/Documents/reigh-workspace/Astrid-megado` | `megado/oracle-run-storyboard` / `aa09089f473e5278057521ef1cd449a8e5290757` | Required tip; ancestor of main | Clean. | Required tip merged/pushed. |
| `/Users/peteromalley/Documents/reigh-workspace/Astrid-editor-bridge-integration` | `codex/editor-bridge-integration` / `97314ccee7caa7adfe04004e6854d7a8ba6b6dfd` | 227 behind / 0 ahead | Clean ancestor of main. | Merged/retained. |
| `/Users/peteromalley/Documents/reigh-workspace/Astrid-main-mypy-audit` | detached / `b2e54aa2c3fb780105d3012bfce31d282e98c360` | 150 behind / 0 ahead | Clean ancestor of main. | Merged/retained. |

## Local branches without separate worktrees

All of these committed tips were verified ancestors of canonical main and
have no outstanding checkout state of their own:

| Branch | Exact tip | Disposition |
|---|---|---|
| `codex/astrid-main-extension-merge` | `caa7472b5b75fd39f52903c04037832cd61b9113` | merged/retained |
| `codex/bridge-negative-cases` | `7c7429d701d9d8626734caf3c7d99f4b5c1809e5` | merged/retained |
| `codex/extension-ship-astrid` | `fb152312d3cb9b7bed5f637bfdf6845e7d638739` | merged/retained |
| `codex/extension-ship-astrid-integration` | `92cc19d53b3fdfc3720f2d625e6e39e1278d0f85` | merged/retained |
| `codex/extension-ship-project-data` | `878960f314e06b6145ce65e35762abd05183dfe1` | merged/retained |
| `codex/phase-b-live-ux-integration` | `487bd8a8e6923d0d5a5594ac37d0566b613f4e32` | merged/retained |

Remote-only execution refs with unique commits are historical receipts, not
direct product merge sources:

| Remote ref | Exact tip | Relation to main | Disposition |
|---|---|---|---|
| `origin/exec-goal`, `origin/exec-goal-20260822` | `a55f4661d3387896c12e93eeae2004d9ef0983c5` | 268 behind / 10 ahead | `ARCHIVE-PRESERVE` |
| `origin/exec-goal-s-20260822` | `727ad1a5e1b1710bb67eecbc71e2f91d27f00d3e` | 857 behind / 25 ahead | `ARCHIVE-PRESERVE` |
| `origin/exec-sqlite-20260823` | `7bcd37b34deb332e5e5edac1f8eb123bbfff1746` | 268 behind / 73 ahead | `ARCHIVE-PRESERVE` |
| `origin/exec-sqlite-s-20260823` | `7a839b105193cb10f0b5099a57fe4bbfeba86f08` | 857 behind / 29 ahead | `ARCHIVE-PRESERVE` |

Remote `phase-b`, `megaplan/astrid-first/m1`, `/m4`, `/m8`, editor-bridge,
convergence, storyboard, and FFmpeg refs are ancestors of main. The remote
`origin/oracle-run` points to `0b69557b...`; the local Arnold resident commit
`b04ed2c7...` is not present in that remote pointer. `origin/oracle-unified-
execution` points to historical `659c3dc...` and is not a replacement for the
dirty local unified-oracle custody tree.

## Other Astrid-related repositories and data

| Path | Exact identity/state | Disposition |
|---|---|---|
| `/Users/peteromalley/Documents/reigh-workspace/banodoco-workspace-runtime` | `main` / `ba511c4f79bb09d53072c6f1bbef2e2d986aa9ce`; clean independent-runtime seed | `MUST-INTEGRATE-BEFORE-STAGE1`; not a completed T1 runtime. |
| `/Users/peteromalley/Documents/reigh-workspace/banodoco-workspace-runtime-oracle` | `megado/astrid-stage1-beta` / same `ba511c4...`; one untracked `.oracle` tree with 613 files and 19 PID files | `ARCHIVE-PRESERVE`; evidence/planning only. |
| `/Users/peteromalley/Documents/reigh-workspace/reigh-app` | `main` / `62518e9dda5076b42f126bae6a78f7f237d6ba37`; six modified roadmap documents | Target-plan custody; not completion evidence. |
| `/Users/peteromalley/Documents/reigh-workspace/reigh-app-stage1-beta` | `megado/astrid-stage1-beta` / `6f1e906919f8232cbeb8dc784099dfa6d67507a5`; clean | Planning branch; target document matches current `reigh-app`. |
| `/Users/peteromalley/Documents/reigh-workspace` | `docs/vibecomfy-post-chain-qwen-proof` / `5477afc205564babc01d15a358ab52be2d6d831f`; 1 tracked and 78 untracked entries, including nested worktrees/evidence | `ARCHIVE-PRESERVE` parent custody workspace. |
| `/Users/peteromalley/Documents/reigh-workspace-oracle` | `oracle-run` / `14ce95858d8e0c26470759ca591e5ec7c03da0ad`; clean historical parent workspace | `ARCHIVE-PRESERVE`; not an independent Astrid product source. |

Astrid-related non-Git custody roots:

- `.local/astrid-projects-extension-demo` — approximately 10 GB; SQLite
  `quick_check=ok`; 19 projects, 64 timelines, 229 media, 3,149 events, 82
  tasks, 567 runs.
- `astrid-intro-projects` — approximately 582 MB; SQLite `quick_check=ok`; 1
  project, 5 timelines, 231 media, 948 events, 72 tasks, 72 runs.
- `.sc05` — approximately 444 KB; SQLite `quick_check=ok`; 1 project and 1
  event.
- `docs/astrid-migration-context` — approximately 1.5 MB of migration/schema/
  bridge/archive material.
- `parked-repo-notes/Astrid` — historical operator notes.
- `banodoco-workspace/hivemind/.astrid` — foreign Hivemind data.
- Arnold-family `.megaplan/initiatives/astrid-consumer` directories — foreign
  orchestration records, not Astrid source.

VibeComfy/ComfyUI repositories that merely contain Astrid smoke-test names
were excluded from the product loose-thread set: they have no Astrid source
branch or Astrid-specific worktree identity. They remain independent repos and
were not changed.

## Target plan and T0–T6 status

Target authority:

```text
/Users/peteromalley/Documents/reigh-workspace/reigh-app/docs/local-runtime/01-astrid-beta.md
SHA-256 d6441bb91f235e5b9bf7a84eb02b70bfb6149ea23024340068c09bd7c9d81a9d
```

The file is also present with the same hash in `reigh-app-stage1-beta`. The
current `reigh-app` checkout is `main` at `62518e9dd...` with six modified
roadmap/vision documents (361 insertions, 108 deletions). The plan is
parallel-first at the leaf packets, while shared contracts, generated clients,
generic-host core, migration, deletion, and release remain serialized gates.

| Gate | Required outcome | Current status |
|---|---|---|
| T0 | Complete authority/capability census, frozen neutral laws, source/migration inventory, DDL/protocol baseline | Open; current evidence is planning/census material, not a committed accepted gate. |
| T1 | Independent runtime, generated Python and TypeScript clients, fake TypeScript actor/worker, no Astrid/Reigh import or direct SQLite/CAS authority | Open; runtime is only seed `ba511c4...`; oracle has evidence but no accepted implementation. |
| T2 | Neutral one-realm bootstrap, credentials, discovery, restart/reboot, zero-logic Astrid launcher | Open. |
| T3 | Full Astrid CLI/SDK generated-client cutover, legacy deletion, real daemon-boundary proof | Open. |
| T4 | One generic pack host, registration/preflight/readiness, capability disposition and adapter-family parity | Open; local-font candidate is an input, not proof. `Sixtyfour` remains unresolved and no hosted fallback is allowed. |
| T5 | Immutable backup, one-time migration, reconciliation, atomic activation, rollback rehearsal, legacy-authority deletion | Open; migration data is preserved custody, not migrated acceptance evidence. |
| T6 | Hash-recorded acceptance aggregate, negative proofs, release-candidate commit and REIGH handoff | Open; no accepted `acceptance.json` proving the full matrix was found. |

## Explicit disposition lists

### MUST-INTEGRATE-BEFORE-STAGE1

- Cleanly reimplement the useful self-hosted Inter/JetBrains font intent from
  the dirty UX branch, after source/license/hash review and a local render
  proof. Do not import its storyboard selection patch or `.oracle` deletions
  without separate review.
- Selectively extract the neutral repository-contract, schema-vocabulary,
  CLI-reference, and import-cycle intent from `Astrid-unified-oracle`, then
  rerun the packet-owned focused tests in a clean worktree from `21a379f...`.
- Advance the independent runtime seed `ba511c4...` through the actual T1
  contract, generated-client, fake-actor, and migration proofs.
- Resolve the local-font capability ledger, including legal local `Sixtyfour`
  source or an explicitly reviewed theme substitution. No hosted fallback.

### ARCHIVE-PRESERVE

- Dirty UX and unified-oracle checkouts exactly as observed, including all
  `.oracle` deletions and untracked files.
- Arnold resident integration and live resident-store data.
- Packification planning branch and remote execution/receipt refs.
- Runtime-oracle findings, PID records, convergence reports, migration docs,
  SQLite project roots, copied snapshots, and parked notes.
- Parent workspace custody and the clean canonical main worktree.

### SUPERSEDED-DELETE-AFTER-HASH

- `/private/tmp/astrid-gallery-projection`
- `/private/tmp/astrid-main-validation.TlNXR4`
- `/private/tmp/astrid-parity-diagnostics.otCs9Y`
- `/private/tmp/astrid-schema-fix.cMghkd`
- `/private/tmp/astrid-ulid-investigate.ogcV8B`
- `/private/tmp/astrid-ulid-parent.BTsqRx`
- `/private/tmp/astrid-uppercase-ulid-fix`

“Superseded” means no unique product delta remains relative to canonical main;
it is not authorization to delete immediately.

### ACTIVE-FOREIGN-PROTECT

- The dirty UX checkout as a whole.
- The dirty unified-oracle checkout as a whole.
- `/Users/peteromalley/Documents/Astrid-oracle` Arnold resident integration.
- Any live or user-owned data, lock, process, or evidence not explicitly
  archived and approved for cleanup.

## Preservation and deletion preconditions

No cleanup was performed. Before any deletion, prune, branch removal, or dirty
checkout cleanup, all of the following must be true:

1. Record the exact absolute path, Git/worktree identity, branch, HEAD, merge
   base, status, and owner for the target.
2. Create an immutable archive or byte-level manifest and SHA-256 for the full
   target, including untracked files, hidden `.oracle` evidence, SQLite WAL/
   SHM files, locks, and nested outputs where applicable.
3. Compare the archive against the source-manifest/receipt and verify that no
   unique commit, untracked patch, migration byte, test result, or provenance
   record is omitted.
4. Obtain explicit owner confirmation for protected, user-owned, foreign, or
   preservation-sensitive material. A prunable Git metadata record is not
   permission to run `git worktree prune`.
5. Check open file handles and active process groups immediately before cleanup;
   never remove a live writer's source, database, lock, or transcript.
6. For any proposed product integration, start from a clean worktree at
   `21a379f...`, manually port only reviewed hunks, run the packet-owned tests,
   and attach a receipt before merge or push.
7. Keep the Stage 1 target document and T0–T6 acceptance gates blocking until
   the required runtime, bootstrap, cutover, generic-host, migration, legacy
   deletion, and release evidence is complete.

## Final conclusion

The canonical convergence slice is complete at
`21a379f24ca2411f5b5222821bf05c447e4ab69f`, including the required storyboard
and FFmpeg tips. The complete loose-thread/Stage 1 objective is **BLOCKED /
UNPROVEN**: all remaining material is now classified, but the two Stage 1
integration candidates still require clean extraction and proof, preserved
foreign/archive material has not been deleted, and T0–T6 remain open.
