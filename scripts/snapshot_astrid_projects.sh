#!/usr/bin/env bash
# Compatibility wrapper for the canonical Sprint 0 multi-root snapshot command.
set -euo pipefail

exec python3 -m scripts.reshape.snapshot_state "$@"
