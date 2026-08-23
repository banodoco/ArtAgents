# Runaway release fixtures

These are byte-for-byte, tracked copies of the immutable Runaway migration
inputs used by the paired Reigh/Astrid release gate. The operational project
tree remains ignored and untouched; release archives must use these fixtures
so an exact Git commit is sufficient to reproduce migration acceptance.

- `timing-manifest.json`: `44b5c0eea0aeb8b35a83e3e7620b5dbab27a106bf575fcc6e0ca6591dd4612bb`
- `audio-reactive-v1.json`: `d7925d72b52180e206a2511a5d30cf1638c7007a962fd57d8a6eb9ffb10af886`

Update a fixture, its hash here, and the executable integrity test in one
reviewed commit. Never read an ignored `projects/` path in a release gate.
