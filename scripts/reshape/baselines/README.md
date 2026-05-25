Advisory lint/type baselines for `scripts/reshape/run_ci_checks.sh`.

History note:
- Git evidence: commit `7d343bcff89a0e6d342c0704d78f7bdb315242a9` introduced `pyproject.toml`, `.github/workflows/ci.yml`, and `scripts/reshape/run_ci_checks.sh` together. That commit scoped Ruff to reshape/concurrency paths and scoped mypy to `files = ["scripts/reshape"]`.
- Git evidence: the same commit message included `ci: exclude known non-s0 baseline gates`.
- Inference: `astrid/` was intentionally kept out of the first advisory gate so CI could start narrow before the broader repo backlog was baselined.

Baseline policy:
- These files record the accepted current finding counts for the expanded advisory scope.
- Compare scripts must exit `0` when current findings are less than or equal to baseline, and non-zero only when the count regresses upward.
- Existing backlog stays advisory until it is separately remediated and the baseline is intentionally lowered.

Regeneration commands:

```bash
python3 scripts/reshape/compare_ruff_baseline.py --write-baseline
python3 scripts/reshape/compare_mypy_baseline.py --write-baseline
```
