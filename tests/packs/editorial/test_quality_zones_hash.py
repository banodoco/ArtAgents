"""Regression for editorial/quality_zones SHA TOCTOU between main() and compute().

Pre-fix bug: ``main()`` hashed the file bytes for the cache key, then
``compute()`` re-hashed the file bytes for the report's ``source_sha256``
field. If the file was rewritten between those two reads, the cache key and
the recorded SHA would diverge — silently corrupting the on-disk cache.

The fix (SD3) adds a ``source_sha256: str | None`` parameter to ``compute()``
that, when provided by ``main()``, suppresses the inner re-read. ffmpeg still
reads the on-disk Path (it needs a real file), but the recorded SHA always
matches the caller's single source of truth.
"""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from astrid.packs.editorial.executors.quality_zones.run import compute


class _MutatingReadBytes:
    """A ``Path.read_bytes`` replacement that mutates the file after first read.

    The first call returns ``initial`` bytes. After that call, the on-disk
    file is rewritten with ``mutated`` bytes, so any subsequent read by
    ``compute`` would see different content (different SHA).
    """

    def __init__(self, target: Path, *, initial: bytes, mutated: bytes) -> None:
        self.target = target
        self.initial = initial
        self.mutated = mutated
        self.calls = 0

    def __call__(self) -> bytes:
        self.calls += 1
        if self.calls == 1:
            self.target.write_bytes(self.mutated)
            return self.initial
        return self.target.read_bytes()


class QualityZonesShaTocTouTest(unittest.TestCase):
    def test_compute_uses_caller_sha_and_skips_inner_reread(self) -> None:
        """When main() passes its SHA to compute(), the SHA must not change.

        Simulates a file mutation between main()'s hash and compute()'s read.
        The recorded source_sha256 must equal main()'s captured SHA, proving
        compute() did not re-hash the mutated bytes.
        """
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "clip.mp4"
            initial_bytes = b"frame-data-A" * 8
            mutated_bytes = b"frame-data-B-changed-mid-flight" * 8
            source.write_bytes(initial_bytes)

            # Step 1: main()-equivalent: hash the file once.
            caller_sha = hashlib.sha256(initial_bytes).hexdigest()
            mutated_sha = hashlib.sha256(mutated_bytes).hexdigest()
            self.assertNotEqual(caller_sha, mutated_sha, "fixture sanity")

            # Step 2: mutate the file before compute() runs, then ensure
            # compute() does NOT re-read for hashing — _run_ffmpeg is stubbed
            # so the ffmpeg subprocess is bypassed entirely.
            source.write_bytes(mutated_bytes)

            with patch(
                "astrid.packs.editorial.executors.quality_zones.run._run_ffmpeg",
                return_value="",
            ):
                report = compute(source, source_sha256=caller_sha)

            self.assertEqual(report.source_sha256, caller_sha)
            self.assertNotEqual(report.source_sha256, mutated_sha)

    def test_compute_falls_back_to_reading_when_no_sha_passed(self) -> None:
        """Without a passed SHA, compute() must still hash the file itself."""
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "clip.mp4"
            content = b"some-bytes-for-hash"
            source.write_bytes(content)
            expected = hashlib.sha256(content).hexdigest()
            with patch(
                "astrid.packs.editorial.executors.quality_zones.run._run_ffmpeg",
                return_value="",
            ):
                report = compute(source)
            self.assertEqual(report.source_sha256, expected)


if __name__ == "__main__":
    unittest.main()
