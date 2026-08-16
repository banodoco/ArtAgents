"""References schema pack (in-tree, explicitly registered).

The references pack owns the normative ``project_references``,
``media_references``, and ``reference_links`` tables plus the future
namespaced ``reference.*`` vocabulary declared in ``schema-pack.yaml`` next to
this module. Every locked reference enum/check/index and kernel-currency
association (``media_id``, ``context_task_id``) is preserved verbatim; m1
declares the schema and vocabulary only — no executable repositories ship yet
(plugin law 3).

This package marker stays deliberately minimal: the composed registry (and
later the migration runner) consume the manifest file, and startup registers
this pack through the single explicit ``register_pack()`` path — never through
discovery or the capability-pack loader.
"""
