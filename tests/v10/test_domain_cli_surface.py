"""Product CLI surface tests (m4 plan step 24, task T25).

Proves the product-family registry contract: exactly five families,
manifest-declared nested mounts (shots under timelines, references under
media), rejection of missing/duplicate/unexpected/dynamic mounts, the
exclusion of operational/legacy/singular-run commands from product
dispatch, and the ``AstridClient``-passing handler boundary. Task T26
extends this file with the shared output-layer (exact JSON envelope
renderer, concise human output, stable exit codes) and the product help.
"""

from __future__ import annotations

import argparse
import json
import types

import pytest

from astrid.core.cli.domain_output import (
    EXIT_FAILURE,
    EXIT_OK,
    EXIT_USAGE,
    envelope_dict,
    print_result,
    render_envelope_json,
    render_human,
)
from astrid.core.cli.domain_product import (
    EXCLUDED_FROM_PRODUCT_CENSUS,
    PRODUCT_FAMILIES,
    ManifestMount,
    ProductRegistryError,
    _validate_mounts,
    build_product_mounts,
    family_mount,
    is_product_family,
    is_registered_family,
    product_top_level_commands,
    run_product_family,
)
from astrid.core.cli.registration import CommandSpec, register_product_commands
from astrid.core.gateway.help import _print_product_help, _product_help_text
from astrid.sdk.contracts import DomainResult, ErrorObject

# ---------------------------------------------------------------------------
# Census
# ---------------------------------------------------------------------------


def test_product_census_is_exactly_five_families() -> None:
    assert tuple(PRODUCT_FAMILIES) == (
        "projects",
        "media",
        "tasks",
        "runs",
        "timelines",
    )
    assert product_top_level_commands() == frozenset(PRODUCT_FAMILIES)
    assert len(PRODUCT_FAMILIES) == 5


def test_operational_families_are_excluded_from_product_census() -> None:
    """serve/doctor/backup are operational families outside the census."""
    assert EXCLUDED_FROM_PRODUCT_CENSUS == frozenset(
        {"serve", "doctor", "backup"}
    )
    for excluded in EXCLUDED_FROM_PRODUCT_CENSUS:
        assert not is_product_family(excluded)
        assert excluded not in product_top_level_commands()


def test_is_product_family_validation() -> None:
    assert all(is_product_family(family) for family in PRODUCT_FAMILIES)
    assert not is_product_family("shots")
    assert not is_product_family("references")
    assert not is_product_family("")
    assert not is_product_family(None)


def test_is_registered_family_includes_nested_mounts() -> None:
    assert all(is_registered_family(family) for family in PRODUCT_FAMILIES)
    assert is_registered_family("shots")
    assert is_registered_family("references")
    assert not is_registered_family("serve")
    assert not is_registered_family("run")


# ---------------------------------------------------------------------------
# Mounts
# ---------------------------------------------------------------------------


def test_mounts_include_core_and_the_two_nested_mounts() -> None:
    mounts = build_product_mounts()
    by_family = {mount.family: mount for mount in mounts}
    assert set(by_family) == {
        "projects",
        "media",
        "tasks",
        "runs",
        "timelines",
        "shots",
        "references",
    }
    # Core families mount at their own top-level token.
    for family in ("projects", "media", "tasks", "runs"):
        assert by_family[family].mount_path == (family,)
        assert by_family[family].declared_by == "core"
    # Manifest-owned timelines.
    assert by_family["timelines"].mount_path == ("timelines",)
    assert by_family["timelines"].declared_by == "manifest:timeline"
    # Exactly the two declared nested mounts.
    assert by_family["shots"].mount_path == ("timelines", "shots")
    assert by_family["shots"].declared_by == "manifest:shots"
    assert by_family["references"].mount_path == ("media", "references")
    assert by_family["references"].declared_by == "manifest:references"




def test_family_mount_resolves_and_rejects() -> None:
    assert family_mount("shots").mount_path == ("timelines", "shots")
    assert family_mount("timelines").declared_by == "manifest:timeline"
    with pytest.raises(ProductRegistryError):
        family_mount("serve")


# ---------------------------------------------------------------------------
# Mount validation: missing / duplicate / unexpected / dynamic
# ---------------------------------------------------------------------------


def test_missing_required_manifest_mount_is_rejected() -> None:
    """A shipped manifest that omits a required cli_mounts entry fails closed."""
    with pytest.raises(ProductRegistryError, match="missing mount"):
        _validate_mounts(
            PRODUCT_FAMILIES,
            (
                ManifestMount("timelines", "timelines", "timeline"),
                ManifestMount("shots", "timelines shots", "shots"),
                # references declaration is missing entirely.
            ),
        )


def test_empty_manifest_mount_is_rejected() -> None:
    with pytest.raises(ProductRegistryError, match="missing mount"):
        _validate_mounts(
            PRODUCT_FAMILIES,
            (
                ManifestMount("timelines", "timelines", "timeline"),
                ManifestMount("shots", "", "shots"),
                ManifestMount("references", "media references", "references"),
            ),
        )


def test_duplicate_manifest_family_is_rejected() -> None:
    """Two manifests declaring the same family are a duplicate mount."""
    with pytest.raises(ProductRegistryError, match="duplicate mount"):
        _validate_mounts(
            PRODUCT_FAMILIES,
            (
                ManifestMount("timelines", "timelines", "timeline"),
                ManifestMount("shots", "timelines shots", "shots"),
                ManifestMount("references", "media references", "references"),
                ManifestMount("shots", "timelines shots", "another-pack"),
            ),
        )


def test_unexpected_manifest_family_is_rejected() -> None:
    """A manifest declaring a family outside the frozen registry is rejected."""
    with pytest.raises(ProductRegistryError, match="unexpected mount"):
        _validate_mounts(
            PRODUCT_FAMILIES,
            (
                ManifestMount("timelines", "timelines", "timeline"),
                ManifestMount("shots", "timelines shots", "shots"),
                ManifestMount("references", "media references", "references"),
                ManifestMount("sixth-family", "projects sixth-family", "extra"),
            ),
        )


def test_unexpected_mount_path_is_rejected() -> None:
    """A declared family at a different mount path is rejected."""
    with pytest.raises(ProductRegistryError, match="unexpected mount"):
        _validate_mounts(
            PRODUCT_FAMILIES,
            (
                ManifestMount("timelines", "timelines", "timeline"),
                ManifestMount("shots", "media references", "shots"),
                ManifestMount("references", "media references", "references"),
            ),
        )


def test_core_family_re_mounted_at_other_path_is_rejected() -> None:
    with pytest.raises(ProductRegistryError, match="unexpected mount"):
        _validate_mounts(
            PRODUCT_FAMILIES,
            (
                ManifestMount("timelines", "media timelines", "timeline"),
                ManifestMount("shots", "timelines shots", "shots"),
                ManifestMount("references", "media references", "references"),
            ),
        )




# ---------------------------------------------------------------------------
# Handler boundary: AstridClient is passed to rule-free handlers
# ---------------------------------------------------------------------------


def test_register_product_commands_stamps_client_and_family() -> None:
    parser = argparse.ArgumentParser(prog="astrid projects")
    sub = parser.add_subparsers(dest="command", required=True)
    client = object()

    def _configure(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--json", action="store_true")
        subparser.set_defaults(
            handler=lambda parsed: (parsed.client, parsed.family, parsed.json)
        )

    register_product_commands(
        sub,
        [CommandSpec("ls", help="List projects", configure=_configure)],
        family="projects",
        client=client,
    )

    parsed = parser.parse_args(["ls", "--json"])
    assert parsed.client is client
    assert parsed.family == "projects"
    assert parsed.handler(parsed) == (client, "projects", True)


def test_register_product_commands_accepts_nested_families() -> None:
    parser = argparse.ArgumentParser(prog="astrid timelines shots")
    sub = parser.add_subparsers(dest="command", required=True)
    register_product_commands(
        sub,
        [
            CommandSpec(
                "list",
                help="List shots",
                configure=lambda p: p.set_defaults(handler=lambda parsed: 0),
            )
        ],
        family="shots",
        client=object(),
    )
    parsed = parser.parse_args(["list"])
    assert parsed.family == "shots"


def test_register_product_commands_rejects_unknown_family() -> None:
    parser = argparse.ArgumentParser(prog="astrid")
    sub = parser.add_subparsers(dest="command", required=True)
    with pytest.raises(ValueError, match="not a registered product family"):
        register_product_commands(
            sub,
            [
                CommandSpec(
                    "ls",
                    help="List",
                    configure=lambda p: p.set_defaults(handler=lambda parsed: 0),
                )
            ],
            family="serve",
            client=object(),
        )


class _StubParser:
    def __init__(self, client: object) -> None:
        self._client = client

    def parse_args(self, args: list[str]) -> argparse.Namespace:
        return argparse.Namespace(
            handler=lambda parsed: parsed.client is not None and 3,
            client=self._client,
            args=args,
        )


def _stub_family_module() -> types.ModuleType:
    module = types.ModuleType("stub_family")
    module.build_parser = lambda client: _StubParser(client)
    return module


def test_run_product_family_passes_client_to_handler() -> None:
    client = object()
    stub = _stub_family_module()
    result = run_product_family(
        "projects",
        ["ls"],
        client=client,
        _parser_modules={"projects": stub},
    )
    assert result == 3


def test_run_product_family_rejects_non_product_family() -> None:
    stub = _stub_family_module()
    with pytest.raises(ProductRegistryError, match="not a product family"):
        run_product_family(
            "serve",
            [],
            client=object(),
            _parser_modules={"serve": stub},
        )
    with pytest.raises(ProductRegistryError, match="not a product family"):
        run_product_family(
            "shots",
            [],
            client=object(),
            _parser_modules={"shots": stub},
        )


def test_run_product_family_rejects_missing_builder() -> None:
    with pytest.raises(ProductRegistryError, match="no in-tree parser builder"):
        run_product_family(
            "projects",
            [],
            client=object(),
            _parser_modules={},
        )


# ---------------------------------------------------------------------------
# Dispatch boundary
# ---------------------------------------------------------------------------


def _call_dispatch_product(args: list[str], monkeypatch: pytest.MonkeyPatch):
    from astrid.core.gateway import dispatch

    return dispatch._dispatch_product(args)


class _FakeClient:
    closed = False

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        type(self).closed = True


def test_dispatch_product_routes_family_and_closes_client(monkeypatch) -> None:
    import astrid.core.cli.domain_product as domain_product
    import astrid.sdk.client as sdk_client

    seen: dict[str, object] = {}

    def _fake_open(cls, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return _FakeClient()

    def _fake_run(family, args, *, client, **kwargs):  # noqa: ANN001, ANN002, ANN003
        seen["family"] = family
        seen["args"] = list(args)
        seen["client"] = client
        return 7

    monkeypatch.setattr(sdk_client.AstridClient, "open", classmethod(_fake_open))
    monkeypatch.setattr(domain_product, "run_product_family", _fake_run)

    from astrid.core.gateway import dispatch

    assert dispatch._dispatch_product(["projects", "ls", "--json"]) == 7
    assert seen["family"] == "projects"
    assert seen["args"] == ["ls", "--json"]
    assert isinstance(seen["client"], _FakeClient)
    assert _FakeClient.closed


def test_dispatch_product_owner_contention_is_typed_json(monkeypatch, capsys) -> None:
    """A held serve owner is a retryable product error, not a gateway bug."""
    import astrid.sdk.client as sdk_client
    from astrid.core.gateway import dispatch
    from astrid.sdk.exceptions import ServiceUnavailableError

    def _raise_open(cls, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise ServiceUnavailableError(
            "the Astrid serve bridge owns the store; use GET /routes and its "
            "HTTP routes while it is running, or wait for a clean shutdown.",
            details={"reason": "store_owned", "retryable": True},
        )

    monkeypatch.setattr(
        sdk_client.AstridClient, "open", classmethod(_raise_open)
    )

    assert dispatch._dispatch_product(["projects", "list", "--json"]) == 1
    output = capsys.readouterr()
    assert output.err == ""
    payload = json.loads(output.out)
    assert set(payload) == {
        "ok",
        "data",
        "error",
        "receipt",
        "idempotency_key",
    }
    assert payload["ok"] is False
    assert payload["error"]["code"] == "unavailable"
    assert payload["error"]["details"] == {
        "reason": "store_owned",
        "retryable": True,
    }


def test_dispatch_product_owner_contention_human_guidance(monkeypatch, capsys) -> None:
    """Human contention output names the bridge handoff and safe retry rule."""
    import astrid.sdk.client as sdk_client
    from astrid.core.gateway import dispatch
    from astrid.sdk.exceptions import ServiceUnavailableError

    def _raise_open(cls, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise ServiceUnavailableError(
            "the Astrid serve bridge owns the store; use GET /routes and its "
            "HTTP routes while it is running, or wait for a clean shutdown. "
            "Reads may retry after release. For writes, preserve the exact "
            "payload and idempotency key, then verify state.",
            details={"reason": "store_owned", "retryable": True},
        )

    monkeypatch.setattr(
        sdk_client.AstridClient, "open", classmethod(_raise_open)
    )

    assert dispatch._dispatch_product(["projects", "list"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "error unavailable:" in output.err
    assert "GET /routes" in output.err
    assert "clean shutdown" in output.err
    assert "exact payload and idempotency key" in output.err


def test_dispatch_product_help_does_not_open_client(monkeypatch, capsys) -> None:
    """Family/verb help remains available without touching the store."""
    import astrid.sdk.client as sdk_client

    def _fail_open(cls, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise AssertionError("help must not compose an AstridClient")

    monkeypatch.setattr(sdk_client.AstridClient, "open", classmethod(_fail_open))

    from astrid.core.gateway import dispatch

    with pytest.raises(SystemExit) as excinfo:
        dispatch._dispatch_product(["timelines", "save", "--help"])
    assert excinfo.value.code == 0
    assert "astrid timelines save" in capsys.readouterr().out


def test_dispatch_product_rejects_excluded_commands_before_opening(
    monkeypatch,
) -> None:
    import astrid.sdk.client as sdk_client
    from astrid.core.contracts.errors import AstridError

    def _fail_open(cls, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise AssertionError("client must not be opened for excluded commands")

    monkeypatch.setattr(sdk_client.AstridClient, "open", classmethod(_fail_open))

    from astrid.core.gateway import dispatch

    for excluded in ("serve", "doctor", "backup", "sessions", "renderers"):
        with pytest.raises(AstridError, match="unknown product command"):
            dispatch._dispatch_product([excluded])


def test_dispatch_product_requires_a_family(monkeypatch) -> None:
    import astrid.sdk.client as sdk_client
    from astrid.core.contracts.errors import AstridError

    monkeypatch.setattr(
        sdk_client.AstridClient,
        "open",
        classmethod(lambda cls, *args, **kwargs: _FakeClient()),
    )

    from astrid.core.gateway import dispatch

    with pytest.raises(AstridError, match="product family is required"):
        dispatch._dispatch_product([])


def test_product_census_hook_matches_domain_registry() -> None:
    from astrid.core.gateway import dispatch

    assert dispatch._product_top_level_commands() == product_top_level_commands()


def test_top_level_commands_are_exactly_eight_families() -> None:
    from astrid.core.gateway import dispatch

    assert dispatch._top_level_commands() == frozenset(
        {
            "projects",
            "timelines",
            "media",
            "tasks",
            "runs",
            "serve",
            "doctor",
            "backup",
        }
    )
    assert len(dispatch._top_level_commands()) == 8


def test_all_five_product_families_route_through_product_dispatch(
    monkeypatch,
) -> None:
    """Every product-family handler prepends its token to _dispatch_product."""
    from astrid.core.gateway import dispatch

    seen: dict[str, object] = {}

    def _fake_product(args):  # noqa: ANN001
        seen["args"] = list(args)
        return 7

    monkeypatch.setattr(dispatch, "_dispatch_product", _fake_product)
    for family in ("projects", "timelines", "media", "tasks", "runs"):
        handler = dispatch._TOP_LEVEL_HANDLERS[family]
        assert handler(["list", "--json"]) == 7
        assert seen["args"] == [family, "list", "--json"]


# ---------------------------------------------------------------------------
# Shared output layer (plan step 24 renderer, task T26)
# ---------------------------------------------------------------------------


def test_renderer_emits_exact_envelope_for_success() -> None:
    result = DomainResult.success(
        {"slug": "demo", "name": "Demo"}, idempotency_key="key-1"
    )
    envelope = json.loads(render_envelope_json(result))
    assert set(envelope) == {"ok", "data", "error", "receipt", "idempotency_key"}
    assert envelope["ok"] is True
    assert envelope["data"] == {"slug": "demo", "name": "Demo"}
    assert envelope["error"] is None
    assert envelope["receipt"] is None
    assert envelope["idempotency_key"] == "key-1"


def test_renderer_emits_exact_envelope_for_failure() -> None:
    error = ErrorObject(
        code="not_found", message="missing", details={"kind": "project"}
    )
    result = DomainResult.failure(error, idempotency_key="key-2")
    envelope = json.loads(render_envelope_json(result))
    assert set(envelope) == {"ok", "data", "error", "receipt", "idempotency_key"}
    assert envelope["ok"] is False
    assert envelope["data"] is None
    assert envelope["error"] == {
        "code": "not_found",
        "message": "missing",
        "details": {"kind": "project"},
    }
    assert envelope["receipt"] is None


def test_renderer_envelope_keys_match_sdk_contract() -> None:
    from astrid.sdk.contracts import ENVELOPE_KEYS as SDK_ENVELOPE_KEYS

    envelope = json.loads(
        render_envelope_json(DomainResult.success({"slug": "demo"}))
    )
    assert tuple(sorted(envelope)) == tuple(sorted(SDK_ENVELOPE_KEYS))


def test_renderer_accepts_plain_envelope_dict_and_rejects_drift() -> None:
    good = {
        "ok": True,
        "data": {"slug": "demo"},
        "error": None,
        "receipt": None,
        "idempotency_key": "k",
    }
    assert envelope_dict(good) == good
    for bad in (
        # missing key
        {"ok": True, "data": None, "error": None, "receipt": None},
        # extra key
        {
            "ok": True,
            "data": None,
            "error": None,
            "receipt": None,
            "idempotency_key": "k",
            "extra": 1,
        },
        # non-boolean ok
        {
            "ok": "yes",
            "data": None,
            "error": None,
            "receipt": None,
            "idempotency_key": "k",
        },
    ):
        with pytest.raises(ValueError):
            envelope_dict(bad)
    with pytest.raises(ValueError):
        envelope_dict("not an envelope")


def test_renderer_json_round_trips_through_domain_result() -> None:
    result = DomainResult.success(
        {"media_id": "M1", "content_hash": "abc"}, idempotency_key="key-3"
    )
    assert DomainResult.from_json(render_envelope_json(result)) == result


def test_human_output_is_concise() -> None:
    assert render_human(DomainResult.success({"slug": "demo"})) == "slug: demo"
    assert render_human(DomainResult.success({"media_id": "M1"})) == "media_id: M1"
    assert (
        render_human(DomainResult.success([{"id": "a"}, {"id": "b"}]))
        == "2 result(s)"
    )
    assert render_human(DomainResult.success(None)) == "ok"
    failure = DomainResult.failure(
        ErrorObject(code="conflict", message="stale version", details={})
    )
    assert render_human(failure) == "error conflict: stale version"


def test_print_result_returns_stable_exit_codes(capsys) -> None:
    ok = DomainResult.success({"slug": "demo"}, idempotency_key="k")
    failure = DomainResult.failure(
        ErrorObject(code="not_found", message="missing", details={})
    )
    assert EXIT_OK == 0
    assert EXIT_FAILURE == 1
    assert EXIT_USAGE == 2

    # Human success -> stdout, exit 0.
    assert print_result(ok) == EXIT_OK
    out, err = capsys.readouterr()
    assert out == "slug: demo\n"
    assert err == ""

    # Human failure -> stderr, exit 1.
    assert print_result(failure) == EXIT_FAILURE
    out, err = capsys.readouterr()
    assert out == ""
    assert err == "error not_found: missing\n"

    # JSON mode always prints the exact envelope on stdout; the exit code
    # still carries the outcome.
    assert print_result(ok, as_json=True) == EXIT_OK
    out, err = capsys.readouterr()
    envelope = json.loads(out)
    assert set(envelope) == {"ok", "data", "error", "receipt", "idempotency_key"}
    assert envelope["ok"] is True
    assert err == ""

    assert print_result(failure, as_json=True) == EXIT_FAILURE
    out, err = capsys.readouterr()
    envelope = json.loads(out)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "not_found"
    assert err == ""


# ---------------------------------------------------------------------------
# Product help (plan step 24 renderer/help, task T26)
# ---------------------------------------------------------------------------


def test_product_help_text_declares_exact_census_and_mounts() -> None:
    text = _product_help_text()
    assert (
        "Family census (exactly eight families): "
        "projects timelines media tasks runs serve doctor backup" in text
    )
    for family in PRODUCT_FAMILIES:
        assert family in text
    for operational in ("serve", "doctor", "backup"):
        assert operational in text
    assert "timelines shots" in text
    assert "media references" in text
    for excluded in EXCLUDED_FROM_PRODUCT_CENSUS:
        assert excluded in text


def test_product_help_census_matches_explicit_registry() -> None:
    text = _product_help_text()
    census_line = next(
        line for line in text.splitlines() if line.startswith("Family census")
    )
    census = census_line.split(":", 1)[1].split()
    assert tuple(census[5:]) == ("serve", "doctor", "backup")
    assert set(census[:5]) == set(PRODUCT_FAMILIES)
    # Every advertised product family is a real registered product family.
    for family in census[:5]:
        assert is_product_family(family)
    # The three operational families are exactly the excluded set.
    assert set(census[5:]) == set(EXCLUDED_FROM_PRODUCT_CENSUS)


def test_product_help_documents_stable_exit_codes() -> None:
    text = _product_help_text()
    assert "Exit codes:" in text
    assert "0  success (envelope ok=true)" in text
    assert "1  typed SDK error (envelope ok=false)" in text
    assert "2  usage/parse error" in text


def test_product_help_documents_json_envelope_convention() -> None:
    text = _product_help_text()
    assert "--json" in text
    assert "ok/data/error/receipt/idempotency_key" in text
    assert "doctor emits" in text
    assert "serve/backup have no --json flag" in text


def test_product_help_lists_current_timeline_visualize_and_render_verbs() -> None:
    text = _product_help_text()
    assert "projects    [kernel] project create/list/show/update/select/current" in text
    assert (
        "timeline create/list/show/save/archive/unarchive/history/diff/visualize/render"
        in text
    )


def test_product_help_documents_store_handoff() -> None:
    text = _product_help_text()
    assert "astrid serve" in text
    assert "GET" in text and "/routes" in text
    assert "clean" in text and "shutdown" in text
    assert "exact payload and idempotency key" in text
    assert "error.details.reason=store_owned" in text


def test_print_product_help_prints_to_stdout(capsys) -> None:
    _print_product_help()
    captured = capsys.readouterr()
    assert captured.out.startswith("Astrid product commands")
    assert "Family census (exactly eight families)" in captured.out
