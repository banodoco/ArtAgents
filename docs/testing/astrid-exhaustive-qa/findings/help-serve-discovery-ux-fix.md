# Help / serve discovery UX fix

Date: 2026-08-23 (Europe/Berlin)

## Outcome

Fixed the P1/P2 agent-UX findings from `waves/live-serve-editor-1.md`:

- Product-family and verb help now parses without composing an
  `AstridClient`, opening/migrating the selected database, or acquiring its
  exclusive-owner lock. This works while `astrid serve` owns another root and
  against a default root with an incompatible/unregistered migration.
- `serve` readiness output now prints the resolved projects root, exclusive
  ownership implication, canonical routes, save payload shape, and the fact
  that asset URLs take a registry key rather than `media_id`.
- The bridge exposes `GET /routes`, a machine-readable discovery document with
  routes, save request/response version fields, ownership metadata, and asset
  registry-key semantics.
- The public CLI and bridge contracts document these guarantees.

## Live proof

Before the change, `python3 -m astrid projects --help` failed on the checkout's
default root with `MigrationTooNewError` for an unregistered `runaway` pack,
and help while a live bridge held an isolated root failed during DB composition.

After the change:

- `projects --help`, `timelines --help`, `media --help`, `tasks --help`,
  `runs --help`, and representative nested verb help all exited 0 with no
  stderr, without setting `ASTRID_PROJECTS_ROOT`.
- A real headless bridge on an isolated root printed the new readiness details;
  concurrent `python3 -m astrid timelines save --help` exited 0 while the
  bridge owned the store.
- `curl http://127.0.0.1:<port>/routes` returned JSON containing the selected
  absolute root, `exclusive_ownership.owner = "astrid serve"`, all canonical
  routes, the `{config, registry, expected_version}` save shape, and
  `registry.assets.{registry_key}` asset semantics.
- `/health` remained 200 and returned the same selected root.

## Guard coverage

Focused tests pass:

```text
pytest -q tests/v10/test_domain_cli_surface.py -k 'dispatch_product_help or dispatch_product_routes'
pytest -q tests/v10/test_m6_gate.py -k 'serve_boots_clean_project_end_to_end or serve_route_discovery'
2 passed in each invocation
```

Changed implementation: `astrid/core/gateway/dispatch.py`,
`astrid/core/integrations/reigh/local_bridge_server.py`.

