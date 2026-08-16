"""Timeline schema pack (in-tree, explicitly registered).

The timeline pack owns the normative ``timelines`` table plus the namespaced
``timeline.*`` vocabulary (stream type, event kinds, command kinds) declared in
``schema-pack.yaml`` next to this module. Timeline identity (slug, lowercase
ULID, default) is projected from events and ``projects.settings_json`` per SD1;
the table itself carries no convenience columns.

This package marker stays deliberately minimal: the composed registry (and
later the migration runner and repositories) consume the manifest file, and
startup registers this pack through the single explicit ``register_pack()``
path — never through discovery or the capability-pack loader.
"""
