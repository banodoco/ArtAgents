"""Runtime entrypoint for runpod.provision executor.

Thin wrapper — all logic lives in ``astrid.packs.runpod.executors._common``.
"""

from __future__ import annotations

from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint('runpod.provision')

# Re-export everything so that ``from astrid.packs.runpod.executors.provision.run import X``
# continues to work for tests and any other callers.
from astrid.packs.runpod.executors._common import *  # noqa: F401,F403,E402
from astrid.packs.runpod.executors._common import main  # noqa: F401,E402

if __name__ == "__main__":
    raise SystemExit(main())
