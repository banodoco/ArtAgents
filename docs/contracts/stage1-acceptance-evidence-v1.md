# Astrid Stage 1 acceptance evidence

The final Stage 1 gate consumes a portable directory of machine-readable
receipts. It does not run migration, render, network, or launch operations and
it does not turn a narrative into a pass. Every check must have non-empty
machine observations and at least one retained artifact whose SHA-256 matches
the bytes in the bundle.

The normative checklist is §§10–13 of
`reigh-app/docs/local-runtime/01-astrid-beta.md`. The schema is
[`stage1-acceptance-evidence-v1.schema.json`](stage1-acceptance-evidence-v1.schema.json).

## Receipt shape

Each receipt is one `*.json` file with:

```json
{
  "schema": "astrid.stage1.evidence.receipt.v1",
  "receipt_id": "cold-launch-20260901",
  "category": "cold_launch",
  "status": "pass",
  "observed_at": "2026-09-01T12:00:00Z",
  "command": ["pytest", "tests/stage1/test_final_cold_launch_matrix_luna.py"],
  "observations": {"evidence_mode": "live", "owner_count": 1},
  "checks": [
    {
      "id": "10.1.clean-editable-setup",
      "status": "pass",
      "observations": {"fresh_home": true},
      "artifacts": [
        {"path": "cold-launch.json", "sha256": "sha256:<64 lowercase hex>", "kind": "trace"}
      ]
    }
  ]
}
```

The source-identity receipt must contain exactly one `astrid` and one
`runtime` repository in `observations.repositories`. Each entry records the
full 40-character commit, a dirty-tree digest, and a tree digest. Dependency
locks and source/capability manifests similarly carry content digests.

Migration, backup/restore, rollback, network, and render claims must be
retained from their real execution lanes. Synthetic, fixture, narrative, or
manual-claim modes are rejected for live categories. The aggregator never
creates a substitute receipt.

## Building the final bundle

```bash
python3 -m scripts.reshape.stage1_acceptance \
  --evidence-dir .astrid-convergence/stage1-evidence \
  --output-dir .astrid-convergence/stage1-acceptance
```

The command always writes `acceptance.json` and `ASTRID-BETA.md`. Missing,
malformed, failed, stale, or unhashable evidence produces a `blocked`/`fail`
report and exit status 1. Only a complete set of passing, hash-verified
receipts exits 0. The aggregate contains a sorted receipt index, artifact
index, report hash, exact repository identities, dependency/manifests, census
summaries, every blocking checklist row, and a redaction policy. User-home
path components and credential-shaped fields are redacted; retained artifact
paths are evidence-bundle relative.
