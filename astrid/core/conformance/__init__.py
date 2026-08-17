"""Reusable repository-command conformance kit (m1 plan step 15 / NSA-2).

The kit generalizes the transactional invariants every implemented command
must satisfy (replay, mismatch-before-mutation, same-project, vocabulary,
writer ownership, statement-boundary old-or-complete crash atomicity, and
full envelope hash-chain verification) so a conformance inventory cannot
create false confidence by omitting a dimension. The executable command set
registers only implemented commands: m1 ships ``timeline.create`` and
``timeline.save``; declared-but-unimplemented shot/reference commands stay
non-executable.
"""

from __future__ import annotations

from astrid.core.conformance.kit import (
    CONFORMANCE_DIMENSIONS,
    CommandSpec,
    ConformanceContext,
    ConformanceError,
    ConformanceEvidence,
    ConformanceReport,
    NON_EXECUTABLE_COMMAND_KINDS,
    TS,
    check_crash_atomicity,
    check_hash_chain,
    check_mismatch_before_mutation,
    check_replay,
    check_same_project,
    check_vocabulary,
    check_writer_ownership,
    run_all,
    standard_command_specs,
)

__all__ = [
    "CONFORMANCE_DIMENSIONS",
    "CommandSpec",
    "ConformanceContext",
    "ConformanceError",
    "ConformanceEvidence",
    "ConformanceReport",
    "NON_EXECUTABLE_COMMAND_KINDS",
    "TS",
    "check_crash_atomicity",
    "check_hash_chain",
    "check_mismatch_before_mutation",
    "check_replay",
    "check_same_project",
    "check_vocabulary",
    "check_writer_ownership",
    "run_all",
    "standard_command_specs",
]
