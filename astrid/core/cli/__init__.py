"""Top-level CLI aggregation tier — may import any domain downward.

Holds shared CLI infrastructure (registration helpers, conventions) plus the
per-domain CLI command modules. An aggregator in this tier is allowed to import
many domains (downward); domains must not import these modules back upward.
"""