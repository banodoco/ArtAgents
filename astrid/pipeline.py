"""Backward-compatibility shim — ``astrid.pipeline`` is ``astrid.gateway``.

Setting ``sys.modules[__name__]`` to the canonical gateway module means
every ``import astrid.pipeline`` and every ``mock.patch("astrid.pipeline.…")``
target transparently resolves through to the gateway.  No re-export lists
to maintain — the gateway *is* the pipeline.
"""

import sys as _sys

# Import the canonical module so it is resident in sys.modules.
from astrid import gateway as _gateway  # noqa: E402, F401

_sys.modules[__name__] = _sys.modules["astrid.gateway"]
