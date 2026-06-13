"""Stable non-task home for managed timeline binding helpers.

Release N keeps ``astrid.core.task.managed_binding`` as the implementation and
fallback surface. This module provides the long-lived import path for
non-task and pack consumers while the behavioral core is being retired.
"""

from astrid.core.task.managed_binding import is_managed_mode

__all__ = ["is_managed_mode"]
