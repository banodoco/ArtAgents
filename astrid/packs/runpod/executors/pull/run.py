"""Runtime entrypoint for runpod.pull executor.

Thin wrapper — all logic lives in ``astrid.packs.runpod.executors._common``.
"""

from __future__ import annotations

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint('runpod.pull')

# Re-export everything so that ``from astrid.packs.runpod.executors.pull.run import X``
# continues to work for any callers.
from astrid.packs.runpod.executors._common import *  # noqa: F401,F403,E402
from astrid.packs.runpod.executors._common import main  # noqa: F401,E402

if __name__ == "__main__":
    raise SystemExit(main())
