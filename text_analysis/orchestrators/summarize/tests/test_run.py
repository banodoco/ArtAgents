"""Basic smoke test for text_analysis.summarize."""
import subprocess
import sys


def test_dry_run() -> None:
    """Verify the orchestrator runs in dry-run mode without errors."""
    result = subprocess.run(
        [sys.executable, "-m", "astrid", "orchestrators", "run",
         "text_analysis.summarize", "--dry-run"],
        capture_output=True,
        text=True,
    )
    # TODO: assert on expected behavior
    assert result.returncode == 0, f"dry-run failed: {result.stderr}"
