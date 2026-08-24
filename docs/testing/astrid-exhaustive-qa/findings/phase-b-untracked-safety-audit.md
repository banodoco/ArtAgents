# Phase-B untracked safety audit

Date: 2026-08-24  
Mode: read-only inventory and content scan; no Git state, index, refs, or
product files were changed by this audit.

## Verdict

The current Git-visible untracked tree contains intentional source, tests, QA
evidence, and two separate user-owned initiative records. It contains no
database files, SQLite WAL/SHM files, media, renderer output, dependency
trees, archives, caches, symlinks, or files larger than 100 KiB. A scan for
credential-bearing assignments and private-key material found no secret
values. The untracked tree is therefore suitable for a lossless safety
snapshot, but it must not be blindly folded into the phase-B product commit:
the initiative/oracle/wavespeed paths below are separate work and the phase-B
oracle proof has an add/add collision.

## Inventory

At the point of inspection, `git ls-files --others --exclude-standard` returned
184 paths and 1,295,231 bytes total (all individual files are ordinary text or
Python source).
The stable counts by root were:

| Root | Files | Classification |
| --- | ---: | --- |
| `.megaplan/initiatives/pluggable-timeline-renderers/` | 6 | user-owned renderer initiative |
| `.megaplan/initiatives/timeline-visualization/` | 7 | user-owned visualization initiative |
| `.oracle/findings/stacked-render-proof.txt` | 1 | user-owned/provenance proof; collides with phase-B |
| `astrid/` | 7 | new live-UX/product source, except `wavespeed.py` |
| `tests/` | 16 | live-UX regression tests, except the Wavespeed test |
| `docs/testing/astrid-exhaustive-qa/` | 147 | live-agent UX evidence and maps |

The source and test paths are all `.py`; the evidence is Markdown; the two
initiative manifests are YAML/Markdown; and the oracle proof is text. No
untracked file is a media container or binary asset. There are no untracked
directories such as `node_modules`, `.venv`, `__pycache__`, `dist`, `build`,
`runs`, `outputs`, or renderer caches.

The 147 QA files break down as 54 findings, 3 maps, and 88 wave reports. They
are evidence artifacts, not runtime data. They can be included in the live-UX
campaign snapshot, although the final integrated branch may choose one
canonical acceptance report and retain the rest as historical evidence.

## Secret and local-data scan

The scan covered every Git-visible untracked path. It found only source/docs
references to variable names such as `OPENAI_API_KEY`, `FAL_KEY`, and
`WAVESPEED_API_KEY`; it found no non-empty credential assignment, bearer value,
private-key block, or API-key-shaped secret. Evidence reports contain
disposable `/tmp` paths, hashes, and the local checkout path as test output;
these are provenance disclosures, not credentials or live project data.

Important boundary: ignored files are not part of the untracked inventory.
The checkout currently has ignored `.env`, `.env.local`, `.astrid/`, `.claude/`,
coverage/desloppify state, and large `.megaplan` state. Do not use `git add -f`,
an ignored-file archive, or a broad filesystem tar in the safety snapshot.
Keep these ignored paths outside the merge and never publish them.

## Exact exclusions from the live-UX campaign commit

Preserve these paths in the safety snapshot, but exclude them from the initial
live-UX campaign commit and from any phase-B replay unless the owner explicitly
asks for them:

```text
.megaplan/initiatives/pluggable-timeline-renderers/
.megaplan/initiatives/timeline-visualization/
astrid/core/generation/backends/wavespeed.py
tests/core/generation/backends/test_wavespeed_extract_audio_urls.py
```

The following path must also be kept out of a naïve add/add replay. It is
user-owned proof material and phase-B adds a different tracked blob at the
same path:

```text
.oracle/findings/stacked-render-proof.txt
```

Preserve that file in the safety snapshot, compare it with phase-B's version,
then rerun the stacked-render proof on the integrated tree and publish one
new canonical result. Do not resolve this collision by whole-file `ours` or
`theirs` selection.

## Recommended inclusion set

Subject to the parent agent's thematic review, the remaining untracked paths
are coherent live-UX work and should be included in the safety snapshot and
replayed into the integration branch:

```text
astrid/core/generation/preflight.py
astrid/core/io/managed_media_resolver.py
astrid/core/kernel/database.py
astrid/core/project/workspace.py
astrid/core/rendering/output_policy.py
astrid/packs/rendering/executors/render/managed_timeline.py
tests/core/generation/test_preflight.py
tests/core/io/test_managed_media_resolver.py
tests/core/test_capability_handler_streams.py
tests/packs/rendering/test_managed_timeline_render.py
tests/sdk/test_extended_composition.py
tests/sdk/test_maker_preflight_contracts.py
tests/sdk/test_project_orientation_ux.py
tests/sdk/test_restored_event_readback.py
tests/test_live_capability_discovery_fix.py
tests/v10/test_archive_return_recovery.py
tests/v10/test_backup_external_portability.py
tests/v10/test_doctor.py
tests/v10/test_kernel_database_precedence.py
tests/v10/test_kernel_read_composition.py
tests/v10/test_selection_isolation.py
docs/testing/astrid-exhaustive-qa/
```

The 147 reports should remain evidence even where their findings later become
redundant; deduplication is a documentation decision after integration, not a
safety prerequisite.
