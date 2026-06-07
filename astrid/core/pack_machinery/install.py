"""Backward-compatibility shim for ``astrid.core.pack_machinery.install``."""

import sys as _sys

from astrid.core.pack import install as _install  # noqa: E402, F401

_sys.modules[__name__] = _sys.modules["astrid.core.pack.install"]
