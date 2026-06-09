"""Top-level CLI aggregation tier — may import any domain downward.

Holds shared CLI infrastructure (registration helpers, conventions) plus the
stranded per-domain CLI command modules lifted here so that domain packages no
longer reach sideways into one another through their CLI layers. An aggregator
in this tier is allowed to import many domains (downward); domains must not
import these modules back upward.
"""
