"""Runtime-backed timelines product mount.

The workspace runtime owns timeline persistence, vocabulary, and migrations.
This package contains only the executable CLI adapter for the nested product
surface; it does not host a schema, repository, or local writer.
"""
