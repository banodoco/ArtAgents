"""Shared SDK-module lazy resolver.

Every call-site that needs to reach across the SDK package boundary
resolves ``astrid.sdk`` through this single helper so monkeypatches
applied to the package namespace are visible at call time.
"""

from __future__ import annotations

import importlib
from typing import Any


def _sdk_module() -> Any:
    return importlib.import_module("astrid.sdk")
