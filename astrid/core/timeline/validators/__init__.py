"""Validation submodules extracted from banodoco_schema.py.

Each submodule imports types and constants FROM banodoco_schema (never the
reverse).  banodoco_schema re-exports every public validator so existing
``from astrid.core.timeline.banodoco_schema import <validator>`` imports
keep working unchanged.
"""
