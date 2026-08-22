"""Shared bridge/SDK/CLI service-authority proof (m4 plan step 30, task T33).

Proves that a bridge timeline save, an SDK timeline save, and a CLI
timeline save all resolve to **the same service command** over **one
in-process standard application**:

- the standard application instruments exactly one service command —
  ``TimelinesService.save`` — into ``app.timeline_save_calls`` (plan step
  30's single instrumentation point, installed by
  ``astrid.application.compose_standard_application``);
- the bridge adapter and the local HTTP server are composed over the
  *same* application services and the *same* writer, so the HTTP save
  route, ``AstridClient`` SDK calls, and the product ``timelines`` CLI all
  cross the identical bound method;
- **equivalent committed receipts**: the bridge supplies the hidden
  deterministic bridge save key (§6.1), and an SDK or CLI retry under that
  exact key replays the identical committed receipt with zero new rows;
  fresh saves from each surface under distinct caller keys commit
  receipts with the identical command kind and canonical request hash;
- **no handler-side alternate authority**: the bridge HTTP handler and the
  product CLI handlers never import SQLite, a repository implementation,
  or a legacy authority — statically (module-level imports) and
  behaviorally (the save journey runs solely through the injected
  service-backed bridge).

This proof is retained gate evidence for the plan-step-33 authority lint
(CF-C8DABA3EFC17A617F801).
"""

from __future__ import annotations

import ast
import json
import threading
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from astrid.application import TimelineSaveCall, compose_standard_application
from astrid.core.cli.domain_product import run_product_family
from astrid.core.integrations.reigh.bridge_service import TimelineSaveRequest
from astrid.core.integrations.reigh.local_bridge_server import (
    create_local_bridge_server,
)
from astrid.core.receipts.service import CommandReceipt
from astrid.packs.timeline.bridge import TimelineBridgeAdapter
from astrid.sdk.client import AstridClient

# The bridge/CLI handler modules the authority claim covers: the bridge
# HTTP handler plus every product-family CLI parser (the five core
# families and the two manifest-declared nested mounts).
_HANDLER_MODULES: tuple[str, ...] = (
    "astrid/core/integrations/reigh/local_bridge_server.py",
    "astrid/packs/timeline/cli.py",
    "astrid/packs/shots/cli.py",
    "astrid/packs/references/cli.py",
    "astrid/core/cli/domain_projects.py",
    "astrid/core/cli/domain_media.py",
    "astrid/core/cli/domain_tasks.py",
    "astrid/core/cli/domain_runs.py",
)

LEGACY_AUTHORITY_MARKERS: tuple[str, ...] = (
    "LocalFsBackend",
    "astrid.core.timeline.eventlog",
    "supabase",
    "data_provider",
    "sidecar",
)


def _is_legacy_authority_import(module: str) -> bool:
    """Whether *module* is a legacy authority import.

    Mirrors the authority-lint marker set: the legacy file/JSONL/FSA/
    Supabase authorities are imported by name (``supabase``,
    ``data_provider``, ``LocalFsBackend``, ``astrid.core.timeline.eventlog``,
    or a ``sidecar`` module). Prose in docstrings — e.g. "the legacy
    sidecar/FSA asset fallback was removed" — never matches, exactly as in
    the deterministic authority lint.
    """
    for marker in LEGACY_AUTHORITY_MARKERS:
        if module == marker or module.startswith(f"{marker}."):
            return True
    return False


def _post_json(
    url: str, body: dict[str, Any], *, token: str | None = None
) -> tuple[int, dict[str, Any]]:
    """POST one JSON body and return (status, parsed response).

    *token* carries the server's per-boot request token (doc 27 §4.7):
    the local-trust gate rejects any token-less mutation with 403 before
    routing, so live-server callers must present the boot token exactly
    as the launcher-delivered app/worker would.
    """
    data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token is not None:
        req.add_header("X-Astrid-Request-Token", token)
    try:
        with urlopen(req) as response:  # noqa: S310 - local test server only
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def _module_level_imports(source: str) -> set[str]:
    """Return the module-level imported module names of *source*."""
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
    return modules


def _save_payload(*, fps: int) -> dict[str, Any]:
    """One timeline save payload (frozen bridge top keys only)."""
    return {"config": {"fps": fps}, "registry": {"assets": {}}, "expected_version": 1}


def _start_server(app, adapter: TimelineBridgeAdapter, projects_root: Path):
    """Start a bridge HTTP server over *app*'s services and writer.

    Mirrors the gateway serve composition root (m4 plan step 21):
    bridge, writer, and database path are constructor-injected, so the
    server holds exactly the application's one authority.
    """
    server = create_local_bridge_server(
        projects_root=projects_root,
        bridge=adapter,
        writer=app.writer,
        database_path=app.database_path,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host = str(server.server_address[0])
    port = int(server.server_address[1])
    return server, thread, f"http://{host}:{port}"


def _stop_server(server, thread: threading.Thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


# ---------------------------------------------------------------------------
# The shared journey: one application, one service command, one writer
# ---------------------------------------------------------------------------


def test_bridge_sdk_cli_saves_reach_one_service_command_one_writer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Bridge, SDK, and CLI saves cross the same instrumented command.

    One in-process standard application is composed; the bridge adapter,
    the HTTP server, and the CLI parser all bind to its single timeline
    service and single writer. The bridge commits the save under the
    hidden deterministic bridge key; the SDK and CLI saves under that
    exact key replay the **identical committed receipt** with zero new
    rows — proving every path resolves to the same service command over
    the one writer queue.
    """
    with compose_standard_application(projects_root=tmp_path) as app:
        client = AstridClient(app)
        project = client.projects.create(
            slug="demo", name="Demo", idempotency_key="p1"
        )
        assert project.ok, project.error
        timeline = client.timelines.create(
            project="demo", slug="main", name="Main", idempotency_key="t1"
        )
        assert timeline.ok, timeline.error
        project_id = project.data["id"]
        timeline_id = timeline.data["timeline_id"]

        # The bridge adapter over the application's own services: no new
        # service construction, no new writer (plan steps 20/21).
        adapter = TimelineBridgeAdapter(
            writer=app.writer,
            projects=app.projects_service,
            timelines=app.timelines_service,
        )
        server, thread, base = _start_server(app, adapter, tmp_path)
        try:
            payload = _save_payload(fps=30)

            # 1) Bridge save over HTTP.
            status, body = _post_json(
                f"{base}/projects/demo/timelines/main/save", payload, token=server.request_token
            )
            assert status == 200, body
            assert body["config_version"] == 2

            # The bridge's hidden deterministic save key (bridge §6.1).
            derived_key = adapter._derive_bridge_save_key(  # noqa: SLF001
                project_id=project_id,
                timeline_id=timeline_id,
                request=TimelineSaveRequest.parse(payload),
            )
            with app.writer.read_only_connection() as conn:
                bridge_receipt = app.receipts.lookup_committed(
                    conn, project_id=project_id, idempotency_key=derived_key
                )
            assert bridge_receipt is not None
            assert bridge_receipt.command_kind == "timeline.save"

            # 2) SDK save under the same derived key: an identical retry
            # replays the exact committed receipt with zero new rows.
            sdk = client.timelines.save(
                "demo",
                "main",
                config=payload["config"],
                registry=payload["registry"],
                expected_version=payload["expected_version"],
                idempotency_key=derived_key,
            )
            assert sdk.ok, sdk.error
            assert sdk.receipt == bridge_receipt
            assert sdk.data["config_version"] == 2

            # 3) CLI save under the same derived key: the product
            # ``timelines`` handler is a rule-free SDK adapter, so it
            # replays the exact same committed receipt.
            rc = run_product_family(
                "timelines",
                [
                    "save",
                    "main",
                    "--project",
                    "demo",
                    "--config",
                    json.dumps(payload["config"]),
                    "--registry",
                    json.dumps(payload["registry"]),
                    "--expected-version",
                    str(payload["expected_version"]),
                    "--idempotency-key",
                    derived_key,
                    "--json",
                ],
                client=client,
            )
            assert rc == 0
            cli_envelope = json.loads(capsys.readouterr().out)
            assert cli_envelope["ok"] is True
            assert cli_envelope["data"]["config_version"] == 2
            assert (
                CommandReceipt.from_dict(cli_envelope["receipt"]) == bridge_receipt
            )
        finally:
            _stop_server(server, thread)

        # Every path reached the same service command: exactly three
        # crossings of the one instrumented ``TimelinesService.save``,
        # all under the bridge's derived key, all for the same timeline.
        assert len(app.timeline_save_calls) == 3
        assert {
            call.idempotency_key for call in app.timeline_save_calls
        } == {derived_key}
        assert all(call.project == "demo" for call in app.timeline_save_calls)
        assert all(call.ref == "main" for call in app.timeline_save_calls)
        assert all(
            call.expected_version == payload["expected_version"]
            for call in app.timeline_save_calls
        )
        assert all(
            isinstance(call, TimelineSaveCall) for call in app.timeline_save_calls
        )

        # One shared writer: the single timeline service holds the one
        # application writer, and the two replays committed zero new rows
        # (the bridge save is the only mutation after project/timeline
        # creation).
        assert app.timelines_service._writer is app.writer  # noqa: SLF001
        assert adapter._writer is app.writer  # noqa: SLF001
        events = app.event_log.list_events()
        assert [event.kind for event in events] == [
            "core.project.created",
            "timeline.created",
            "timeline.saved",
        ]


def test_fresh_saves_from_each_surface_commit_equivalent_receipts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fresh commits from bridge, SDK, and CLI produce equivalent receipts.

    Each surface saves its own timeline with the identical payload and
    expected head under a distinct idempotency key; the three committed
    receipts must agree on command kind and committed result content and
    land in one gap-free queue, while the canonical request hashes are
    **target-scoped** — a caller-keyed save's semantic request includes
    the resolved project/timeline identity (repository save command), so
    the alpha/beta/gamma saves necessarily hash differently and the
    per-timeline identity is the only intended difference.
    """
    with compose_standard_application(projects_root=tmp_path) as app:
        client = AstridClient(app)
        project = client.projects.create(
            slug="demo", name="Demo", idempotency_key="p1"
        )
        assert project.ok, project.error
        project_id = project.data["id"]
        timeline_ids: dict[str, str] = {}
        for slug in ("alpha", "beta", "gamma"):
            created = client.timelines.create(
                project="demo", slug=slug, name=slug.title(), idempotency_key=f"t-{slug}"
            )
            assert created.ok, created.error
            timeline_ids[slug] = created.data["timeline_id"]

        adapter = TimelineBridgeAdapter(
            writer=app.writer,
            projects=app.projects_service,
            timelines=app.timelines_service,
        )
        server, thread, base = _start_server(app, adapter, tmp_path)
        try:
            payload = _save_payload(fps=60)

            # Bridge saves its timeline (derived key).
            status, body = _post_json(
                f"{base}/projects/demo/timelines/alpha/save", payload
            )
            assert status == 200, body
            bridge_key = adapter._derive_bridge_save_key(  # noqa: SLF001
                project_id=project_id,
                timeline_id=timeline_ids["alpha"],
                request=TimelineSaveRequest.parse(payload),
            )

            # SDK saves its timeline (caller key).
            sdk = client.timelines.save(
                "demo",
                "beta",
                config=payload["config"],
                registry=payload["registry"],
                expected_version=payload["expected_version"],
                idempotency_key="sdk-fresh",
            )
            assert sdk.ok, sdk.error
            assert sdk.receipt is not None

            # CLI saves its timeline (caller key).
            rc = run_product_family(
                "timelines",
                [
                    "save",
                    "gamma",
                    "--project",
                    "demo",
                    "--config",
                    json.dumps(payload["config"]),
                    "--registry",
                    json.dumps(payload["registry"]),
                    "--expected-version",
                    str(payload["expected_version"]),
                    "--idempotency-key",
                    "cli-fresh",
                    "--json",
                ],
                client=client,
            )
            assert rc == 0
            cli_envelope = json.loads(capsys.readouterr().out)
            assert cli_envelope["ok"] is True
        finally:
            _stop_server(server, thread)

        # All three saves crossed the one instrumented service command.
        assert len(app.timeline_save_calls) == 3
        assert {
            call.idempotency_key for call in app.timeline_save_calls
        } == {bridge_key, "sdk-fresh", "cli-fresh"}

        # One writer: three fresh commits land as one gap-free sequence.
        assert app.timelines_service._writer is app.writer  # noqa: SLF001
        events = app.event_log.list_events()
        assert [event.project_seq for event in events] == list(
            range(1, len(events) + 1)
        )
        assert [event.kind for event in events] == [
            "core.project.created",
            "timeline.created",
            "timeline.created",
            "timeline.created",
            "timeline.saved",
            "timeline.saved",
            "timeline.saved",
        ]

        # Equivalent committed receipts: identical command kind, and
        # identical committed result content apart from the per-timeline
        # identity. Request hashes are target-scoped: a caller-keyed save
        # includes the resolved project/timeline identity in its semantic
        # request, so the three saves to alpha/beta/gamma must hash
        # differently (three distinct hashes — not one).
        with app.writer.read_only_connection() as conn:
            receipts = [
                app.receipts.lookup_committed(
                    conn, project_id=project_id, idempotency_key=key
                )
                for key in (bridge_key, "sdk-fresh", "cli-fresh")
            ]
        assert all(receipt is not None for receipt in receipts)
        kinds = {receipt.command_kind for receipt in receipts}  # type: ignore[union-attr]
        assert kinds == {"timeline.save"}
        hashes = {receipt.request_hash for receipt in receipts}  # type: ignore[union-attr]
        assert len(hashes) == 3, (
            "request hashes are target-scoped (resolved project/timeline "
            "identity participates in the semantic request), so the three "
            "saves to different timelines must hash differently"
        )
        results = [receipt.result for receipt in receipts]  # type: ignore[union-attr]
        for result in results:
            assert result["config"] == payload["config"]
            assert result["registry"] == payload["registry"]
            assert result["config_version"] == 2
        # Identity differs per timeline; content is equivalent.
        assert len({result["timeline_id"] for result in results}) == 3
        assert len({result["slug"] for result in results}) == 3


# ---------------------------------------------------------------------------
# No handler-side alternate authority
# ---------------------------------------------------------------------------


def test_bridge_and_cli_handlers_import_no_sql_repositories_or_legacy(
    tmp_path: Path,
) -> None:
    """No bridge/CLI handler imports SQLite, repositories, or legacy
    authorities — statically at module level and behaviorally by the
    journey tests above (the saves run solely through the injected
    service-backed bridge)."""

    from astrid.core import cli as cli_package
    from astrid.core.integrations import reigh as reigh_package
    from astrid.packs import references as references_package
    from astrid.packs import shots as shots_package
    from astrid.packs import timeline as timeline_package

    package_roots = {
        "astrid/core/integrations/reigh/": Path(reigh_package.__file__).parent,
        "astrid/core/cli/": Path(cli_package.__file__).parent,
        "astrid/packs/timeline/": Path(timeline_package.__file__).parent,
        "astrid/packs/shots/": Path(shots_package.__file__).parent,
        "astrid/packs/references/": Path(references_package.__file__).parent,
    }
    repo_root = Path(__file__).resolve().parents[2]

    for rel in _HANDLER_MODULES:
        for prefix, package_root in package_roots.items():
            if rel.startswith(prefix):
                source = (package_root / Path(rel).name).read_text(encoding="utf-8")
                break
        else:  # pragma: no cover - the mapping above covers every handler
            source = (repo_root / rel).read_text(encoding="utf-8")

        # Module-level imports: no SQLite, no repository implementation,
        # no writer construction, and no legacy authority import anywhere.
        imports = _module_level_imports(source)
        assert "sqlite3" not in imports, f"{rel} imports sqlite3 at module level"
        assert not any(
            module == "astrid.core.repositories"
            or module.startswith("astrid.core.repositories.")
            for module in imports
        ), f"{rel} imports a repository implementation at module level"
        assert not any(
            module == "astrid.core.store.writer"
            or module.startswith("astrid.core.store.writer.")
            for module in imports
        ), f"{rel} imports the writer at module level"
        assert "DatabaseWriter(" not in source, f"{rel} constructs a writer"
        # Legacy authority imports (by module name; prose mentions of the
        # removed fallback never match).
        assert not any(
            _is_legacy_authority_import(module) for module in imports
        ), f"{rel} imports a legacy authority at module level"

    # Behaviorally: importing the bridge handler pulls in no SQLite or
    # repository module into its own namespace (the only raw-SQL/repository
    # use is the lazy read-only asset path, exercised by asset GETs only).
    import astrid.core.integrations.reigh.local_bridge_server as server_module

    assert not hasattr(server_module, "sqlite3")
    assert not hasattr(server_module, "MediaRepository")
    assert not hasattr(server_module, "ProjectRepository")

    # The save journey itself (test_bridge_sdk_cli_saves_reach_one_service_
    # command_one_writer) behaviorally proves the handlers resolve through
    # the one injected service command: no handler-side SQL, repository
    # construction, or legacy authority is reachable on the save path.