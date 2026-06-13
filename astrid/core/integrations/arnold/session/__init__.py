"""A3b session-succession engine for Arnold.

This package provides the session-succession runtime that compiles Astrid
``TaskPlan`` (and plan-mutation delta) objects into frozen Arnold pipeline
segments, manages cross-segment state in the run directory, and exposes a
session-aware CLI path that coexists with the existing A3a static host.

Import boundary: this package MUST be importable without triggering an
Arnold import. All Arnold symbols flow through
``astrid.core.integrations.arnold.host.compat``.
"""

from __future__ import annotations
