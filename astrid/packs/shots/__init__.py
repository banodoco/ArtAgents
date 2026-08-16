"""Shots schema pack (in-tree, explicitly registered).

The shots pack owns the normative ``shots`` and ``shot_items`` tables plus the
future namespaced ``shot.*`` vocabulary declared in ``schema-pack.yaml`` next
to this module. m1 declares the schema and vocabulary only: no executable
repositories ship yet (plugin law 3 — pack repositories, when added, receive
the kernel unit-of-work handle and never own a writer).

This package marker stays deliberately minimal: the composed registry (and
later the migration runner) consume the manifest file, and startup registers
this pack through the single explicit ``register_pack()`` path — never through
discovery or the capability-pack loader.
"""
