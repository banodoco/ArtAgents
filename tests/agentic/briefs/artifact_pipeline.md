# Artifact Pipeline Provenance

You are running a structural M4 verification scenario.  No live agent
dispatch is performed — the fixture primes the project deterministically
and the check verifies frozen evidence.

## What happens

1. A project is created with slug `${SLUG}`.
2. The fixture writes upstream artifact bytes and computes their
   SHA-256 CAS hash via `produces_check_passed.cas_sha256`.
3. A downstream consumer diagnostic is written asserting that the
   downstream input hash matches the upstream artifact hash, proving
   A-to-B provenance handoff.
4. The fixture verifies zero orphan artifacts and matched provenance.
5. Diagnostic evidence is written to `m4/artifact_pipeline.json`.
6. The capture phase freezes the evidence pack for deterministic M4 checks.

## Canonical CLI constraint

- **Do NOT invoke `python -m astrid.packs.*` directly.** The only
  canonical CLI surfaces are `astrid executors run <id> ...` and
  `astrid orchestrators run <id> ...`. Bypassing them disqualifies the
  run regardless of artifacts produced.

## Evidence left behind

| Path | Description |
|---|---|
| `m4/artifact_pipeline.json` | Diagnostic payload: `upstream_artifact_sha256`, `downstream_input_sha256`, `handoff_matches`, `matched_provenance`, `orphan_artifacts` |
| `runs/*/events.jsonl` | Event log with artifact produce events |

## Deterministic assertion

**`m4.artifact_pipeline.provenance_handoff`** — verifies:
- `upstream_artifact_sha256` is a non-empty SHA-256 string
- `downstream_input_sha256` is a non-empty SHA-256 string
- `upstream_artifact_sha256 == downstream_input_sha256` (hash handoff)
- `handoff_matches == true`
- `matched_provenance == true`
- `orphan_artifacts` is empty or absent

## M2 universal checks

This scenario sets `assessment.universal_checks: false`. No M2 checks
(C3, C4, S1, S2) are enabled. All verification is performed by the
deterministic M4 check above.

## Report (under 200 words, markdown, numbered sections)

Each numbered section MUST have at least 2 substantive sentences.

1. **Upstream artifact creation** — what artifact bytes were written?
   What is the computed upstream SHA-256 hash?
2. **Downstream consumer handoff** — how was the downstream consumer
   invoked? What input hash did it observe?
3. **Hash match verification** — did `upstream_artifact_sha256` equal
   `downstream_input_sha256`? Is `handoff_matches` true?
4. **Orphan check** — were any orphan artifacts detected? Is
   `orphan_artifacts` empty?
5. **Evidence completeness** — are all expected evidence files
   present? Is `m4/artifact_pipeline.json` well-formed?

## Rules

- This scenario runs with `--actor fake --mode structural` only.
- Never run this in live mode — it is a fixture, not an agent task.
- Verify behaviour from frozen evidence files, not from narrative output.
