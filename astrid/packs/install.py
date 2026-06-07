"""Backward-compatibility shim for ``astrid.packs.install``.

``astrid.packs.install`` remains a supported import and patch target, but the
implementation now lives in ``astrid.core.pack.install``.
"""

import sys as _sys

from astrid.core.pack import install as _install  # noqa: E402, F401

_sys.modules[__name__] = _sys.modules["astrid.core.pack.install"]
