from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

RUN_ID_PLACEHOLDER = "<run-id>"
SESSION_ID_PLACEHOLDER = "<session-id>"
TIMESTAMP_PLACEHOLDER = "<timestamp>"
DURATION_PLACEHOLDER = "<duration>"
ENGINE_PLACEHOLDER = "<engine>"
PATH_PLACEHOLDER = "<path>"
IGNORED_ARTIFACT_PLACEHOLDER = "<ignored-artifact-field>"

RUN_ID_KEYS = frozenset({"run_id"})
SESSION_ID_KEYS = frozenset(
    {
        "session_id",
        "attached_session_id",
        "writer_session_id",
        "execution_session_id",
    }
)
TIMESTAMP_KEYS = frozenset(
    {
        "timestamp",
        "ts",
        "created_at",
        "updated_at",
        "started_at",
        "finished_at",
        "ended_at",
    }
)
DURATION_KEYS = frozenset({"duration_ms", "duration_seconds", "elapsed_ms"})
ENGINE_KEYS = frozenset({"engine", "engine_id", "engine_name", "lifecycle_engine"})

# T3 contract: parity normalization is placeholder replacement only for the
# approved identity/time/path fields. Artifact payload fields stay strict unless
# a named future exception is added here.
APPROVED_ARTIFACT_IGNORE_PATHS = frozenset[str]()


class ParityNormalizationError(ValueError):
    """Raised when parity normalization is asked to ignore an unapproved field."""


def load_artifact_for_parity(path: str | Path) -> Any:
    """Read one artifact into a deterministic in-memory comparison shape."""
    artifact_path = Path(path)
    suffix = artifact_path.suffix.lower()
    raw = artifact_path.read_bytes()

    if suffix == ".json":
        return json.loads(raw.decode("utf-8"))
    if suffix == ".jsonl":
        lines = raw.decode("utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]
    if suffix in {".txt", ".md", ".html", ".csv", ".log"}:
        return raw.decode("utf-8")
    return raw


def assert_allowed_artifact_ignores(paths: Iterable[str] | None) -> tuple[str, ...]:
    """Fail closed on any requested artifact ignore path outside the allowlist."""
    if paths is None:
        return ()
    normalized = tuple(str(path) for path in paths)
    invalid = sorted(
        path for path in normalized if path not in APPROVED_ARTIFACT_IGNORE_PATHS
    )
    if invalid:
        raise ParityNormalizationError(
            "artifact ignore path(s) are not approved by the parity contract: "
            f"{invalid!r}; approved={sorted(APPROVED_ARTIFACT_IGNORE_PATHS)!r}"
        )
    return normalized


def normalize_for_parity(
    value: Any,
    *,
    artifact_ignore_paths: Iterable[str] | None = None,
    path_roots: Sequence[str | Path] = (),
) -> Any:
    """Normalize only the approved entropy fields before parity comparison."""
    approved_ignores = set(assert_allowed_artifact_ignores(artifact_ignore_paths))
    normalized_roots = _normalize_roots(path_roots)
    return _normalize_node(
        value,
        path=(),
        approved_ignores=approved_ignores,
        path_roots=normalized_roots,
    )


def _normalize_roots(path_roots: Sequence[str | Path]) -> tuple[str, ...]:
    roots: list[str] = []
    for root in path_roots:
        text = str(root)
        if not text:
            continue
        roots.append(text.rstrip("/"))
    return tuple(sorted(set(roots), key=len, reverse=True))


def _normalize_node(
    value: Any,
    *,
    path: tuple[str, ...],
    approved_ignores: set[str],
    path_roots: tuple[str, ...],
) -> Any:
    path_str = ".".join(path)
    if path_str and path_str in approved_ignores:
        return IGNORED_ARTIFACT_PLACEHOLDER

    if isinstance(value, Mapping):
        return {
            key: _normalize_field(
                key,
                field_value,
                path=path + (str(key),),
                approved_ignores=approved_ignores,
                path_roots=path_roots,
            )
            for key, field_value in value.items()
        }

    if isinstance(value, list):
        return [
            _normalize_node(
                item,
                path=path + (str(index),),
                approved_ignores=approved_ignores,
                path_roots=path_roots,
            )
            for index, item in enumerate(value)
        ]

    if isinstance(value, tuple):
        return tuple(
            _normalize_node(
                item,
                path=path + (str(index),),
                approved_ignores=approved_ignores,
                path_roots=path_roots,
            )
            for index, item in enumerate(value)
        )

    if isinstance(value, str):
        return _normalize_string_value(value, path_roots=path_roots)

    return value


def _normalize_field(
    key: str,
    value: Any,
    *,
    path: tuple[str, ...],
    approved_ignores: set[str],
    path_roots: tuple[str, ...],
) -> Any:
    if key in RUN_ID_KEYS and isinstance(value, str):
        return RUN_ID_PLACEHOLDER
    if key in SESSION_ID_KEYS and isinstance(value, str):
        return SESSION_ID_PLACEHOLDER
    if key in TIMESTAMP_KEYS and isinstance(value, (str, int, float)):
        return TIMESTAMP_PLACEHOLDER
    if key in DURATION_KEYS and isinstance(value, (str, int, float)):
        return DURATION_PLACEHOLDER
    if key in ENGINE_KEYS and isinstance(value, str):
        return ENGINE_PLACEHOLDER
    return _normalize_node(
        value,
        path=path,
        approved_ignores=approved_ignores,
        path_roots=path_roots,
    )


def _normalize_string_value(value: str, *, path_roots: tuple[str, ...]) -> str:
    normalized = value
    for root in path_roots:
        normalized = normalized.replace(root, PATH_PLACEHOLDER)
    return normalized


# ═══════════════════════════════════════════════════════════════════════
#  T5: Reusable parity test helpers for Arnold migration orchestrators
# ═══════════════════════════════════════════════════════════════════════


def seed_task_event(run_root: str | Path, event: dict[str, Any]) -> dict[str, Any]:
    """Seed a single task event into ``events.jsonl`` using the test helper.

    Re-exports ``seed_event`` from ``tests.conftest`` with a run-root
    interface so callers don't need to remember the ``events_path``
    convention.
    """
    from tests.conftest import seed_event

    events_path = Path(run_root) / "events.jsonl"
    return seed_event(events_path, event)


def seed_task_events(
    run_root: str | Path,
    *events: dict[str, Any],
) -> list[dict[str, Any]]:
    """Seed multiple task events sequentially into ``events.jsonl``.

    Each event is appended via :func:`seed_event` so the hash chain and
    writer-epoch CAS are maintained.
    """
    results: list[dict[str, Any]] = []
    for event in events:
        results.append(seed_task_event(run_root, event))
    return results


def make_project_state_root(
    project_root: str | Path,
    slug: str = "demo",
    *,
    initial_state: Mapping[str, Any] | None = None,
    run_id: str | None = None,
) -> Path:
    """Create a project directory with state files suitable for parity testing.

    Writes ``project.json``, ``current_run.json``, ``runs/<id>/lease.json``,
    ``runs/<id>/events.jsonl`` (empty), and ``runs/<id>/state.json`` (if
    *initial_state* is provided).  Returns the run root.

    Does NOT seed a timeline — callers that need managed timeline
    assertions should use :func:`make_project_state_root_with_timeline`.
    """
    from astrid.core.project.current_run import write_current_run
    from astrid.core.session.lease import write_lease_init
    from astrid.core.threads.ids import generate_ulid

    proot = Path(project_root)
    pdir = proot / slug
    pdir.mkdir(parents=True, exist_ok=True)

    rid = run_id or generate_ulid()
    run_dir = pdir / "runs" / rid
    run_dir.mkdir(parents=True, exist_ok=True)

    (pdir / "project.json").write_text(
        json.dumps(
            {
                "created_at": "2026-06-13T00:00:00Z",
                "name": slug,
                "schema_version": 1,
                "slug": slug,
                "updated_at": "2026-06-13T00:00:00Z",
                "default_timeline_id": None,
            }
        ),
        encoding="utf-8",
    )

    (run_dir / "events.jsonl").touch()
    write_lease_init(run_dir, session_id="test-writer", plan_hash="")
    write_current_run(slug, rid, root=proot)

    if initial_state is not None:
        write_state_json(run_dir, dict(initial_state))

    return run_dir


def make_project_state_root_with_timeline(
    project_root: str | Path,
    slug: str = "demo",
    *,
    initial_state: Mapping[str, Any] | None = None,
    run_id: str | None = None,
) -> tuple[Path, str]:
    """Like :func:`make_project_state_root` but also seeds a default timeline.

    Returns ``(run_root, timeline_ulid)`` so callers can immediately use
    :func:`assert_timeline_assembly_jsonl`.
    """
    from astrid.core import timeline as timeline_contract
    from astrid.core.threads.ids import generate_ulid

    run_root = make_project_state_root(
        project_root,
        slug=slug,
        initial_state=initial_state,
        run_id=run_id,
    )
    proot = Path(project_root)
    pdir = proot / slug

    timeline_ulid = generate_ulid()
    tdir = pdir / "timelines" / timeline_ulid
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "assembly.json").write_text(
        json.dumps(timeline_contract.canonical_empty_timeline()),
        encoding="utf-8",
    )
    (tdir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "contributing_runs": [],
                "final_outputs": [],
                "tombstoned_at": None,
            }
        ),
        encoding="utf-8",
    )
    (tdir / "display.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "slug": "primary",
                "name": "Primary",
                "is_default": True,
            }
        ),
        encoding="utf-8",
    )

    # Update project.json with the default timeline id
    proj_json = json.loads((pdir / "project.json").read_text(encoding="utf-8"))
    proj_json["default_timeline_id"] = timeline_ulid
    (pdir / "project.json").write_text(
        json.dumps(proj_json), encoding="utf-8"
    )

    return run_root, timeline_ulid


def write_review_state_file(
    run_root: str | Path,
    state: Mapping[str, Any],
) -> Path:
    """Write a ``review_state.json`` file into *run_root*.

    Uses the dataset_build ``write_review_state`` helper when available;
    falls back to a plain JSON write with basic validation otherwise.
    """
    target = Path(run_root) / "review_state.json"
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        from astrid.packs.training.orchestrators.dataset_build.state import (
            write_review_state,
        )

        write_review_state(str(target), dict(state))
        return target
    except ImportError:
        pass

    target.write_text(json.dumps(dict(state), indent=2), encoding="utf-8")
    return target


def read_review_state_file(run_root: str | Path) -> dict[str, Any]:
    """Read a ``review_state.json`` file from *run_root*.

    Uses the dataset_build ``read_review_state`` helper when available;
    falls back to plain JSON parsing.
    """
    target = Path(run_root) / "review_state.json"

    try:
        from astrid.packs.training.orchestrators.dataset_build.state import (
            read_review_state,
        )

        return read_review_state(str(target))  # type: ignore[return-value]
    except ImportError:
        pass

    if not target.is_file():
        raise FileNotFoundError(f"review_state.json not found at {target}")
    return json.loads(target.read_text(encoding="utf-8"))


def assert_sentinel_file(
    path: str | Path,
    *,
    exists: bool = True,
) -> None:
    """Assert that a sentinel file exists (or does not) at *path*.

    Sentinel files are lightweight markers (often empty or with a simple
    status payload) written by orchestrators to signal phase completion.
    """
    spath = Path(path)
    if exists:
        assert spath.exists(), f"expected sentinel file at {spath}"
    else:
        assert not spath.exists(), f"unexpected sentinel file at {spath}"


def write_state_json(
    run_root: str | Path,
    state: Mapping[str, Any],
) -> None:
    """Write accumulated state to ``state.json`` in *run_root*.

    Uses the Arnold session ``write_state_file`` when available;
    falls back to atomic JSON write.
    """
    target = Path(run_root)
    target.mkdir(parents=True, exist_ok=True)

    try:
        from astrid.core.integrations.arnold.session.state import write_state_file

        write_state_file(target, dict(state))
        return
    except ImportError:
        pass

    from astrid.core._shared.jsonio import write_json_atomic

    write_json_atomic(target / "state.json", dict(state))


def read_state_json(run_root: str | Path) -> dict[str, Any]:
    """Read accumulated state from ``state.json`` in *run_root*.

    Uses the Arnold session ``load_state_file`` when available;
    falls back to plain JSON parsing (returns ``{}`` on missing file).
    """
    target = Path(run_root)

    try:
        from astrid.core.integrations.arnold.session.state import load_state_file

        return load_state_file(target)
    except ImportError:
        pass

    state_path = target / "state.json"
    if not state_path.is_file():
        return {}
    return json.loads(state_path.read_text(encoding="utf-8"))


def make_plan_for_parity(
    plan_dict: Mapping[str, Any],
    target_dir: str | Path,
    *,
    filename: str = "plan.json",
) -> Path:
    """Write *plan_dict* as a JSON plan file in *target_dir*.

    Returns the path to the written plan file.
    """
    tdir = Path(target_dir)
    tdir.mkdir(parents=True, exist_ok=True)
    plan_path = tdir / filename
    plan_path.write_text(
        json.dumps(dict(plan_dict), indent=2), encoding="utf-8"
    )
    return plan_path


def resolve_plan_path_for_start(
    project_slug: str,
    plan_ref: str,
) -> Path:
    """Resolve a plan reference for Arnold ``--from-plan``.

    Mirrors ``_resolve_plan_path`` from ``astrid.core.integrations.arnold.session.cli``
    so test helpers can pre-compute canonical plan paths.
    """
    from astrid.core.foundation.project_paths import project_dir

    explicit = Path(plan_ref).expanduser()
    for candidate in (
        explicit,
        project_dir(project_slug) / "runs" / plan_ref,
    ):
        plan_path = candidate / "plan.json" if candidate.is_dir() else candidate
        if plan_path.is_file():
            return plan_path.resolve()
    raise FileNotFoundError(
        f"could not resolve plan reference {plan_ref!r} for project {project_slug!r}"
    )


def start_arnold_session_from_plan(
    *,
    project_slug: str,
    from_plan: str | Path,
    initial_state: Mapping[str, Any] | None = None,
    input_values: Mapping[str, str] | None = None,
    requested_run_id: str | None = None,
    json_mode: bool = False,
) -> dict[str, Any]:
    """Invoke Arnold ``start --engine arnold --from-plan`` programmatically.

    Calls ``start_session_run`` directly (bypassing the CLI arg-parser)
    and returns a structured result dict with keys:

    * ``return_code`` — 0 on success
    * ``run_id`` — the allocated run id (may differ from *requested_run_id*)
    * ``stdout`` — captured stdout
    * ``exception`` — caught exception (None on success)

    This is the canonical test helper for seeding an Arnold session run
    from a plan emitted by any of the five target orchestrators.
    """
    import io
    from contextlib import redirect_stdout

    try:
        from astrid.core.integrations.arnold.session.cli import start_session_run
    except ImportError as exc:
        return {
            "return_code": -1,
            "run_id": None,
            "stdout": "",
            "exception": exc,
        }

    state = dict(initial_state or {})
    inputs = dict(input_values or {})
    buf = io.StringIO()

    try:
        with redirect_stdout(buf):
            rc = start_session_run(
                project_slug=project_slug,
                from_plan=str(from_plan),
                initial_state=state,
                input_values=inputs,
                requested_run_id=requested_run_id,
                json_mode=json_mode,
                argv=["start", "--from-plan", str(from_plan), "--project", project_slug],
            )
        stdout = buf.getvalue()
    except Exception as exc:  # noqa: BLE001
        return {
            "return_code": getattr(exc, "returncode", 1),
            "run_id": None,
            "stdout": buf.getvalue(),
            "exception": exc,
        }

    # Extract run_id from JSON-mode stdout when available
    run_id: str | None = None
    if json_mode and stdout.strip():
        try:
            parsed = json.loads(stdout.strip())
            run_id = parsed.get("run_id")
        except json.JSONDecodeError:
            pass

    # For non-JSON mode, try to reconstruct run_id from the project's
    # current_run pointer
    if run_id is None:
        try:
            from astrid.core.project.current_run import read_current_run

            run_id = read_current_run(project_slug)
        except Exception:  # noqa: BLE001
            pass

    return {
        "return_code": rc,
        "run_id": run_id,
        "stdout": stdout,
        "exception": None,
    }


def assert_timeline_assembly_jsonl(
    project_root: str | Path,
    timeline_ulid: str,
    *,
    project_slug: str = "demo",
    min_events: int = 0,
) -> list[dict[str, Any]]:
    """Assert that ``timelines/<ulid>/assembly.jsonl`` exists and is valid.

    Returns the parsed event list.  When *min_events* is positive, also
    asserts there are at least that many events.
    """
    from astrid.core.timeline.paths import assembly_log_path

    proot = Path(project_root)
    log_path = assembly_log_path(project_slug, timeline_ulid, root=proot)

    assert log_path.is_file(), (
        f"timeline assembly.jsonl not found at {log_path}"
    )

    raw = log_path.read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if line.strip()]
    events = [json.loads(line) for line in lines]

    if min_events > 0:
        assert len(events) >= min_events, (
            f"timeline assembly.jsonl at {log_path} has {len(events)} events, "
            f"expected at least {min_events}"
        )

    return events


def assert_managed_timeline_exists(
    project_root: str | Path,
    timeline_ulid: str,
    *,
    project_slug: str = "demo",
) -> None:
    """Quick assertion that a managed timeline directory exists with the
    canonical files (assembly.json, manifest.json, display.json).
    """
    from astrid.core.timeline.paths import timeline_dir

    proot = Path(project_root)
    tdir = timeline_dir(project_slug, timeline_ulid, root=proot)

    assert tdir.is_dir(), f"timeline directory not found at {tdir}"
    assert (tdir / "assembly.json").is_file(), f"assembly.json missing at {tdir}"
    assert (tdir / "manifest.json").is_file(), f"manifest.json missing at {tdir}"
    assert (tdir / "display.json").is_file(), f"display.json missing at {tdir}"

