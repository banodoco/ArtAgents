# Astrid exhaustive QA campaign

This directory is the durable evidence and planning hub for the recursive
domain-by-domain usability and correctness campaign begun on 2026-08-23.

The campaign loop is:

1. Map one domain and its user-shaped journeys.
2. Run adversarial, recovery, and ordinary tasks in an isolated projects root.
3. Record observed behavior and friction with reproducible evidence.
4. Fix the smallest durable root cause.
5. Rerun the original task and nearby regressions.
6. Promote stable scenarios into automated coverage.

Source changes outside this directory are made only after a failing or
frictional journey has been reproduced. Existing uncommitted work in the
repository is treated as user-owned and preserved.

## Campaign artifacts

- `maps/`: independent surface maps and proposed journey matrices.
- `findings/`: reproduced defects and usability friction.
- `waves/`: execution logs and summaries for each domain wave.
- `coverage.md`: synthesized domain inventory and campaign status.

