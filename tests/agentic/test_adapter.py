from __future__ import annotations

import inspect
import json
import os
import subprocess
from pathlib import Path

from sisypy import (
    ActorRun,
    AgenticProjectAdapter,
    EvidencePack,
    FakeProjectAdapter,
    RunMode,
    Scenario,
    SuccessProofLevel,
)

from tests.agentic.adapter import AstridProjectAdapter
from tests.agentic.checks.results import ScoredCheckResult


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["astrid"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _write_capture_fixture(
    *,
    evidence_dir: Path,
    project_dir: Path,
    report_text: str = "# report\n",
    stderr_text: str = "",
    stdout_text: str | None = None,
) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "report.md").write_text(report_text, encoding="utf-8")
    (evidence_dir / "stderr.log").write_text(stderr_text, encoding="utf-8")
    if stdout_text is not None:
        (evidence_dir / "stdout.log").write_text(stdout_text, encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps({"files": {"report.md": "report.md", "stderr.log": "stderr.log"}}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n',
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Interface conformance — verify adapter through Sisypy base interface
# ---------------------------------------------------------------------------


def test_adapter_is_instance_of_sisypy_base_interfaces(tmp_path: Path) -> None:
    """Instantiate the adapter and assert it passes isinstance checks against
    both the ABC and the fake base that Sisypy consumers rely on."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)

    assert isinstance(adapter, AgenticProjectAdapter), (
        "AstridProjectAdapter must be an AgenticProjectAdapter"
    )
    assert isinstance(adapter, FakeProjectAdapter), (
        "AstridProjectAdapter must be a FakeProjectAdapter"
    )


def test_all_required_sisypy_methods_present_and_callable(tmp_path: Path) -> None:
    """Every abstract method defined on AgenticProjectAdapter must be present
    and callable on an AstridProjectAdapter instance — either via the
    Astrid override or the inherited FakeProjectAdapter default.

    prime() is wired with a fake runner to avoid real subprocess calls;
    the full prime path is validated separately in
    test_prime_threads_session_and_applies_env_write_touch_and_ack."""

    def fake_astrid(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return _completed()

    adapter = AstridProjectAdapter(repo_root=tmp_path, astrid_runner=fake_astrid)

    # Build minimal Scenario / ActorRun / EvidencePack for callability checks.
    scenario = Scenario(name="call-check")
    run = ActorRun(
        id="call-run",
        scenario_name="call-check",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(tmp_path / "ws"),
    )
    evidence_dir = tmp_path / "evidence" / "call-check"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("", encoding="utf-8")
    evidence_pack = EvidencePack(
        manifest={},
        evidence_dir=str(evidence_dir),
        files={},
        capture_notes=[],
        capture_gaps={},
    )

    # 1. build_env
    env = adapter.build_env(scenario, run)
    assert isinstance(env, dict)

    # 2. prime (fake runner — no real astrid subprocess)
    adapter.prime(scenario, run)

    # 3. capture
    adapter.capture(scenario, run, evidence_dir)

    # 4. project_universal_checks
    checks = adapter.project_universal_checks(scenario, evidence_dir)
    assert isinstance(checks, dict)

    # 5. canonical_bypass_patterns
    patterns = adapter.canonical_bypass_patterns(scenario)
    assert isinstance(patterns, list)

    # 6. classify_success
    level = adapter.classify_success(scenario, evidence_pack)
    assert isinstance(level, SuccessProofLevel)

    # 7. live_prerequisites
    prereqs = adapter.live_prerequisites(scenario)
    assert isinstance(prereqs, dict)

    # 8. command_policy
    policy = adapter.command_policy(scenario, run)
    assert isinstance(policy, dict)
    for key in ("allow_patterns", "deny_patterns", "enforce"):
        assert key in policy, f"command_policy missing key {key!r}"


def test_required_method_signatures_match_agentic_project_adapter() -> None:
    """The adapter's public method signatures must be compatible with the
    AgenticProjectAdapter ABC — same parameter names and count."""
    abc_methods = {
        name: meth
        for name, meth in inspect.getmembers(AgenticProjectAdapter, inspect.isfunction)
        if hasattr(meth, "__isabstractmethod__") and meth.__isabstractmethod__
    }
    adapter_methods = {
        name: meth
        for name, meth in inspect.getmembers(AstridProjectAdapter, inspect.isfunction)
        if not name.startswith("_")
    }

    for abc_name, abc_meth in abc_methods.items():
        assert abc_name in adapter_methods, (
            f"Missing method {abc_name!r} on AstridProjectAdapter"
        )
        abc_sig = inspect.signature(abc_meth)
        adp_sig = inspect.signature(adapter_methods[abc_name])
        abc_params = list(abc_sig.parameters.keys())
        adp_params = list(adp_sig.parameters.keys())

        # The adapter may include extra optional parameters but must accept
        # at least the parameters the ABC declares.
        assert abc_params == adp_params[: len(abc_params)], (
            f"Method {abc_name!r}: ABC params={abc_params}, "
            f"adapter params={adp_params}"
        )


# ---------------------------------------------------------------------------
# Structural isolation — verify credential/GPU/cloud stripping and
# isolated ASTRID_PROJECTS_ROOT placement
# ---------------------------------------------------------------------------


def test_structural_mode_a_strid_projects_root_is_inside_isolated_workspace(
    monkeypatch, tmp_path: Path
) -> None:
    """When running in structural mode, ASTRID_PROJECTS_ROOT must be set to a
    path inside the Sisypy workspace (not the host/global projects root)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", "/host/global/projects")
    monkeypatch.setenv("ASTRID_SESSION_ID", "bound-session")

    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "sandbox"
    run = ActorRun(
        id="iso-run",
        scenario_name="iso",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
    )

    env = adapter.build_env(Scenario(name="iso"), run)

    # The host ASTRID_PROJECTS_ROOT must not leak through.
    assert env.get("ASTRID_PROJECTS_ROOT") == str(workspace / ".astrid-projects"), (
        "ASTRID_PROJECTS_ROOT must be inside the isolated workspace, "
        "not the host global path"
    )
    # Credentials stripped.
    assert "OPENAI_API_KEY" not in env
    assert "ASTRID_SESSION_ID" not in env
    # Workspace projects dir created on disk.
    assert (workspace / ".astrid-projects").is_dir()


def test_structural_mode_strips_model_and_gpu_variables(
    monkeypatch, tmp_path: Path
) -> None:
    """Structural mode must strip variables whose names contain GPU, CUDA,
    NVIDIA, or MODEL tokens."""
    monkeypatch.setenv("GPU_COUNT", "8")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0,1")
    monkeypatch.setenv("NVIDIA_DRIVER_VERSION", "535")
    monkeypatch.setenv("DEFAULT_MODEL", "gpt-4")
    monkeypatch.setenv("CLOUD_REGION", "us-east-1")
    monkeypatch.setenv("KEEP_THIS", "retained")

    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "ws"
    run = ActorRun(
        id="gpu-run",
        scenario_name="gpu",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
    )

    env = adapter.build_env(Scenario(name="gpu"), run)

    assert env.get("KEEP_THIS") == "retained", "Unrelated vars must survive"
    for stripped_key in (
        "GPU_COUNT",
        "CUDA_VISIBLE_DEVICES",
        "NVIDIA_DRIVER_VERSION",
        "DEFAULT_MODEL",
        "CLOUD_REGION",
    ):
        assert stripped_key not in env, (
            f"{stripped_key} must be stripped in structural mode"
        )


def test_live_mode_does_not_strip_non_session_credentials(
    monkeypatch, tmp_path: Path
) -> None:
    """In live mode only ASTRID_SESSION_ID is unbound; credentials and model
    variables are preserved for real API access."""
    monkeypatch.setenv("ASTRID_SESSION_ID", "bound")
    monkeypatch.setenv("OPENAI_API_KEY", "real-key")
    monkeypatch.setenv("MODEL_NAME", "gpt-4")
    monkeypatch.setenv("GPU_DEVICE", "0")

    adapter = AstridProjectAdapter(repo_root=tmp_path)
    run = ActorRun(
        id="live-run",
        scenario_name="live",
        mode=RunMode.LIVE,
        dispatcher="shell",
        workdir=str(tmp_path / "ws"),
    )

    env = adapter.build_env(Scenario(name="live"), run)

    assert env["OPENAI_API_KEY"] == "real-key"
    assert env["MODEL_NAME"] == "gpt-4"
    assert env["GPU_DEVICE"] == "0"
    assert "ASTRID_SESSION_ID" not in env


def test_build_env_strips_structural_secrets_and_sets_workspace_projects_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ASTRID_SESSION_ID", "bound-session")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("RUNPOD_API_KEY", "pod-secret")
    monkeypatch.setenv("GPU_DEVICE", "0")
    monkeypatch.setenv("MODEL_NAME", "gpt-test")
    monkeypatch.setenv("CLOUD_PROFILE", "prod")
    monkeypatch.setenv("KEEP_ME", "present")

    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    run = ActorRun(
        id="agentic-run",
        scenario_name="sample",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
    )

    env = adapter.build_env(Scenario(name="sample"), run)

    assert env["KEEP_ME"] == "present"
    assert "ASTRID_SESSION_ID" not in env
    assert "OPENAI_API_KEY" not in env
    assert "RUNPOD_API_KEY" not in env
    assert "GPU_DEVICE" not in env
    assert "MODEL_NAME" not in env
    assert "CLOUD_PROFILE" not in env
    assert env["ASTRID_PROJECTS_ROOT"] == str(workspace / ".astrid-projects")
    assert (workspace / ".astrid-projects").is_dir()


def test_build_env_keeps_live_credentials_but_unbinds_session(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ASTRID_SESSION_ID", "bound-session")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")

    adapter = AstridProjectAdapter(repo_root=tmp_path)
    run = ActorRun(
        id="agentic-run",
        scenario_name="sample",
        mode=RunMode.LIVE,
        dispatcher="shell",
        workdir=str(tmp_path / "workspace"),
    )

    env = adapter.build_env(Scenario(name="sample"), run)

    assert env["OPENAI_API_KEY"] == "secret"
    assert "ASTRID_SESSION_ID" not in env


def test_prime_threads_session_and_applies_env_write_touch_and_ack(tmp_path: Path) -> None:
    calls: list[tuple[tuple[str, ...], dict[str, str] | None]] = []

    def fake_astrid(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        calls.append((args, dict(env) if env is not None else None))
        if args == ("projects", "create", "demo-slug"):
            return _completed()
        if args == ("attach", "demo-slug", "--as", "agent:agentic-primer"):
            return _completed(stdout="export ASTRID_SESSION_ID=session-123\n")
        if args == ("start", "builtin.agent_probe", "--project", "demo-slug"):
            return _completed()
        if args == ("status", "--project", "demo-slug"):
            return _completed(stdout="run-id: run-42\n")
        if args[:2] == ("ack", "baseline_write"):
            return _completed()
        if args == ("timelines", "create", "main", "--default"):
            return _completed()
        raise AssertionError(f"unexpected astrid call: {args!r}")

    adapter = AstridProjectAdapter(repo_root=tmp_path, astrid_runner=fake_astrid)
    workspace = tmp_path / "workspace"
    projects_root = workspace / ".astrid-projects"
    run = ActorRun(
        id="run-1",
        scenario_name="sample",
        mode=RunMode.STRUCTURAL,
        dispatcher="shell",
        workdir=str(workspace),
        extras={"project_slug": "demo-slug"},
    )
    scenario = Scenario(
        name="sample",
        priming=[
            {"create_project": "$SLUG"},
            {"env": {"CUSTOM_FLAG": "yes"}},
            {"start": "builtin.agent_probe"},
            {
                "ack": [
                    {
                        "step": "baseline_write",
                        "produces": {"baseline.json": {"ok": True}},
                    }
                ]
            },
            {"write": {"path": str(tmp_path / "fixture.txt"), "content": "hello"}},
            {"touch": str(tmp_path / "touched.txt")},
        ],
    )

    adapter.prime(scenario, run)

    start_env = next(env for args, env in calls if args[:1] == ("start",))
    ack_env = next(env for args, env in calls if args[:2] == ("ack", "baseline_write"))
    assert start_env is not None
    assert ack_env is not None
    assert start_env["ASTRID_SESSION_ID"] == "session-123"
    assert ack_env["ASTRID_SESSION_ID"] == "session-123"
    assert start_env["CUSTOM_FLAG"] == "yes"
    assert ack_env["CUSTOM_FLAG"] == "yes"
    assert start_env["ASTRID_PROJECTS_ROOT"] == str(projects_root)
    assert (tmp_path / "fixture.txt").read_text(encoding="utf-8") == "hello"
    assert (tmp_path / "touched.txt").exists()
    produces = (
        projects_root
        / "demo-slug"
        / "runs"
        / "run-42"
        / "steps"
        / "baseline_write"
        / "v1"
        / "produces"
        / "baseline.json"
    )
    assert produces.is_file()
    assert produces.read_text(encoding="utf-8") == '{"ok": true}'
    assert os.environ.get("ASTRID_SESSION_ID") != "session-123"


def test_prime_writes_timeline_compose_edit_m4_fixture_for_structural_runs(tmp_path: Path) -> None:
    def fake_astrid(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        if args[:2] == ("projects", "create"):
            return _completed()
        raise AssertionError(f"unexpected astrid call: {args!r}")

    adapter = AstridProjectAdapter(repo_root=tmp_path, astrid_runner=fake_astrid)
    workspace = tmp_path / "workspace"
    run = ActorRun(
        id="m4-prime-run",
        scenario_name="timeline_compose_edit",
        mode=RunMode.STRUCTURAL,
        dispatcher="shell",
        workdir=str(workspace),
        extras={"project_slug": "m4-prime-slug"},
    )
    scenario = Scenario(
        name="timeline_compose_edit",
        extras={"m4_fixture": "timeline_compose_edit"},
    )

    adapter.prime(scenario, run)

    diagnostic_path = (
        workspace
        / ".astrid-projects"
        / "m4-prime-slug"
        / "m4"
        / "timeline_compose_edit.json"
    )
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    assert diagnostic["features_present"] == [
        "track",
        "clip",
        "audio_bind",
        "transition",
        "effect",
        "theme",
    ]
    assert diagnostic["verify_chain_ok"] is True
    assert diagnostic["head_consistency_ok"] is True
    assert diagnostic["projection_fidelity_ok"] is True
    assert diagnostic["event_count"] >= 8


def test_prime_writes_timeline_conflict_desync_and_large_audit_m4_fixtures(
    tmp_path: Path,
) -> None:
    def fake_astrid(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        if args[:2] == ("projects", "create"):
            return _completed()
        raise AssertionError(f"unexpected astrid call: {args!r}")

    adapter = AstridProjectAdapter(repo_root=tmp_path, astrid_runner=fake_astrid)
    workspace = tmp_path / "workspace"

    for fixture_name in (
        "timeline_concurrent_version_conflict",
        "durability_after_crash",
        "timeline_large_audit",
    ):
        run = ActorRun(
            id=f"{fixture_name}-run",
            scenario_name=fixture_name,
            mode=RunMode.STRUCTURAL,
            dispatcher="shell",
            workdir=str(workspace),
            extras={"project_slug": f"{fixture_name}-slug"},
        )
        scenario = Scenario(name=fixture_name, extras={"m4_fixture": fixture_name})

        adapter.prime(scenario, run)

    projects_root = workspace / ".astrid-projects"
    conflict = json.loads(
        (
            projects_root
            / "timeline_concurrent_version_conflict-slug"
            / "m4"
            / "timeline_concurrent_version_conflict.json"
        ).read_text(encoding="utf-8")
    )
    assert conflict["loser_error"] == "EventLogStaleVersionError"
    assert conflict["winner_appended"] is True
    assert conflict["verify_chain_ok"] is True
    assert conflict["mechanism"] == "expected_version_conflict"
    assert conflict["mentions_lease"] is False
    assert conflict["conflict"]["expected_version"] == 0
    assert conflict["conflict"]["current_version"] == 1

    desync_root = projects_root / "durability_after_crash-slug" / "m4"
    desync = json.loads((desync_root / "durability_after_crash.json").read_text(encoding="utf-8"))
    assert desync["detection_ok"] is True
    assert desync["mismatch_kind"] == "head_vs_jsonl_desync"
    assert desync["served_stale_state"] is False
    assert (desync_root / "desync" / "assembly.head.json").is_file()
    assert (desync_root / "desync" / "assembly.jsonl").is_file()

    large_root = projects_root / "timeline_large_audit-slug"
    large = json.loads(
        (large_root / "m4" / "timeline_large_audit.json").read_text(encoding="utf-8")
    )
    assert large["event_count"] >= 500
    assert large["checked_events"] >= 500
    assert large["verify_chain_ok"] is True
    assert large["within_budget"] is True
    large_jsonl = next((large_root / "timelines").glob("*/assembly.jsonl"))
    assert len(large_jsonl.read_text(encoding="utf-8").splitlines()) >= 500


def test_prime_normalizes_overlong_project_slug_for_structural_m4_runs(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_astrid(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:2] == ("projects", "create"):
            return _completed()
        raise AssertionError(f"unexpected astrid call: {args!r}")

    adapter = AstridProjectAdapter(repo_root=tmp_path, astrid_runner=fake_astrid)
    workspace = tmp_path / "workspace"
    run = ActorRun(
        id="m4-structural-timeline_concurrent_version_conflict-agent-0-20260601-114706",
        scenario_name="timeline_concurrent_version_conflict",
        mode=RunMode.STRUCTURAL,
        dispatcher="shell",
        workdir=str(workspace),
    )
    scenario = Scenario(
        name="timeline_concurrent_version_conflict",
        priming=[{"create_project": "${SLUG}"}],
        extras={"m4_fixture": "timeline_concurrent_version_conflict"},
    )

    adapter.prime(scenario, run)

    create_call = next(args for args in calls if args[:2] == ("projects", "create"))
    normalized_slug = create_call[2]
    assert len(normalized_slug) <= 63
    assert normalized_slug.startswith("m4-structural-timeline_concurrent_version_conflict")
    assert (
        workspace / ".astrid-projects" / normalized_slug / "m4" / "timeline_concurrent_version_conflict.json"
    ).is_file()


def test_prime_writes_orchestrator_run_persists_m4_fixture_with_cas_artifact(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_astrid(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:2] == ("projects", "create"):
            return _completed()
        if args == (
            "orchestrators",
            "run",
            "video_editing.event_talks",
            "--project",
            "m4-orch-slug",
            "--dry-run",
        ):
            assert env is not None
            assert env["ASTRID_PROJECTS_ROOT"].endswith(".astrid-projects")
            return _completed(stdout="dry-run ok\n")
        raise AssertionError(f"unexpected astrid call: {args!r}")

    adapter = AstridProjectAdapter(repo_root=tmp_path, astrid_runner=fake_astrid)
    workspace = tmp_path / "workspace"
    run = ActorRun(
        id="m4-orch-run",
        scenario_name="orchestrator_run_persists",
        mode=RunMode.STRUCTURAL,
        dispatcher="shell",
        workdir=str(workspace),
        extras={"project_slug": "m4-orch-slug"},
    )
    scenario = Scenario(
        name="orchestrator_run_persists",
        extras={
            "m4_fixture": "orchestrator_run_persists",
            "m4_checks": {"orchestrator_run_persists": {"enabled": True}},
        },
    )

    adapter.prime(scenario, run)

    project_dir = workspace / ".astrid-projects" / "m4-orch-slug"
    diagnostic = json.loads(
        (project_dir / "m4" / "orchestrator_run_persists.json").read_text(encoding="utf-8")
    )
    assert diagnostic["terminal_status"] == "success"
    assert diagnostic["run_json_status"] == "success"
    assert diagnostic["produces_event_count"] == 1
    assert diagnostic["artifact_count"] == 1
    assert diagnostic["artifacts_match_cas"] is True
    assert diagnostic["fallback"] == "start_with_plan+ack"
    assert (
        "orchestrators",
        "run",
        "video_editing.event_talks",
        "--project",
        "m4-orch-slug",
        "--dry-run",
    ) in calls

    evidence_dir = tmp_path / "evidence-orch"
    _write_capture_fixture(evidence_dir=evidence_dir, project_dir=project_dir)
    adapter.capture(scenario, run, evidence_dir)
    result = adapter.project_universal_checks(scenario, evidence_dir)
    assert result["m4.orchestrator_run_persists.terminal_success"]["status"] == "pass"

    event = next(
        json.loads(line)
        for line in (evidence_dir / "runs" / "m4-orchestrator-run" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if json.loads(line).get("kind") == "produces_check_passed"
    )
    artifact = (
        evidence_dir
        / "runs"
        / "m4-orchestrator-run"
        / "steps"
        / "render"
        / "v1"
        / "produces"
        / "render.json"
    )
    import hashlib

    assert event["cas_sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()


def test_prime_writes_artifact_pipeline_m4_fixture_with_a_to_b_provenance(
    tmp_path: Path,
) -> None:
    def fake_astrid(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        if args[:2] == ("projects", "create"):
            return _completed()
        raise AssertionError(f"unexpected astrid call: {args!r}")

    adapter = AstridProjectAdapter(repo_root=tmp_path, astrid_runner=fake_astrid)
    workspace = tmp_path / "workspace"
    run = ActorRun(
        id="m4-artifact-run",
        scenario_name="artifact_pipeline",
        mode=RunMode.STRUCTURAL,
        dispatcher="shell",
        workdir=str(workspace),
        extras={"project_slug": "m4-artifact-slug"},
    )
    scenario = Scenario(
        name="artifact_pipeline",
        extras={
            "m4_fixture": "artifact_pipeline",
            "m4_checks": {"artifact_pipeline": {"enabled": True}},
        },
    )

    adapter.prime(scenario, run)

    project_dir = workspace / ".astrid-projects" / "m4-artifact-slug"
    diagnostic = json.loads(
        (project_dir / "m4" / "artifact_pipeline.json").read_text(encoding="utf-8")
    )
    assert diagnostic["producer_step"] == "producer"
    assert diagnostic["consumer_step"] == "consumer"
    assert diagnostic["upstream_artifact_sha256"] == diagnostic["downstream_input_sha256"]
    assert diagnostic["handoff_matches"] is True
    assert diagnostic["matched_provenance"] is True
    assert diagnostic["orphan_artifacts"] == []
    assert diagnostic["artifact_consumer_diagnostics"][0]["from_step"] == "producer"
    assert diagnostic["artifact_consumer_diagnostics"][0]["to_step"] == "consumer"

    evidence_dir = tmp_path / "evidence-artifact"
    _write_capture_fixture(evidence_dir=evidence_dir, project_dir=project_dir)
    adapter.capture(scenario, run, evidence_dir)
    result = adapter.project_universal_checks(scenario, evidence_dir)
    assert result["m4.artifact_pipeline.provenance_handoff"]["status"] == "pass"


def test_prime_writes_taskrun_concurrent_lease_m4_fixture_with_valid_chain(
    tmp_path: Path,
) -> None:
    def fake_astrid(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        if args[:2] == ("projects", "create"):
            return _completed()
        raise AssertionError(f"unexpected astrid call: {args!r}")

    adapter = AstridProjectAdapter(repo_root=tmp_path, astrid_runner=fake_astrid)
    workspace = tmp_path / "workspace"
    run = ActorRun(
        id="m4-lease-run",
        scenario_name="taskrun_concurrent_lease",
        mode=RunMode.STRUCTURAL,
        dispatcher="shell",
        workdir=str(workspace),
        extras={"project_slug": "m4-lease-slug"},
    )
    scenario = Scenario(
        name="taskrun_concurrent_lease",
        extras={
            "m4_fixture": "taskrun_concurrent_lease",
            "m4_checks": {"taskrun_concurrent_lease": {"enabled": True}},
        },
    )

    adapter.prime(scenario, run)

    project_dir = workspace / ".astrid-projects" / "m4-lease-slug"
    diagnostic = json.loads(
        (project_dir / "m4" / "taskrun_concurrent_lease.json").read_text(encoding="utf-8")
    )
    assert diagnostic["rejection_error"] == "StaleEpochError"
    assert diagnostic["writer_count"] == 1
    assert diagnostic["winning_writer"] == "writer-b"
    assert diagnostic["final_writer_epoch"] == 1
    assert diagnostic["lease_file_present"] is True
    assert diagnostic["verify_chain_ok"] is True

    from astrid.core.task.events import verify_chain

    run_dir = project_dir / "runs" / "m4-taskrun-lease"
    chain_ok, _index, error = verify_chain(run_dir / "events.jsonl")
    assert chain_ok, error
    final_lease = json.loads((run_dir / "lease.json").read_text(encoding="utf-8"))
    assert final_lease["attached_session_id"] == "writer-b"
    assert final_lease["writer_epoch"] == 1

    evidence_dir = tmp_path / "evidence-lease"
    _write_capture_fixture(evidence_dir=evidence_dir, project_dir=project_dir)
    adapter.capture(scenario, run, evidence_dir)
    result = adapter.project_universal_checks(scenario, evidence_dir)
    assert result["m4.taskrun_concurrent_lease.single_writer_lease"]["status"] == "pass"
    assert (evidence_dir / "runs" / "m4-taskrun-lease" / "events.jsonl").is_file()
    assert (evidence_dir / "runs" / "m4-taskrun-lease" / "lease.json").is_file()


def test_prime_skips_m4_fixture_diagnostic_for_live_runs_by_default(tmp_path: Path) -> None:
    def fake_astrid(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        if args[:2] == ("projects", "create"):
            return _completed()
        raise AssertionError(f"unexpected astrid call: {args!r}")

    adapter = AstridProjectAdapter(repo_root=tmp_path, astrid_runner=fake_astrid)
    workspace = tmp_path / "workspace"
    run = ActorRun(
        id="m4-live-run",
        scenario_name="timeline_compose_edit",
        mode=RunMode.LIVE,
        dispatcher="shell",
        workdir=str(workspace),
        extras={"project_slug": "m4-live-slug"},
    )
    scenario = Scenario(
        name="timeline_compose_edit",
        extras={"m4_fixture": "timeline_compose_edit"},
    )

    adapter.prime(scenario, run)

    diagnostic_path = (
        workspace
        / ".astrid-projects"
        / "m4-live-slug"
        / "m4"
        / "timeline_compose_edit.json"
    )
    assert not diagnostic_path.exists()


def test_capture_copies_astrid_artifacts_and_records_optional_misses(tmp_path: Path) -> None:
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "capture-slug"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("", encoding="utf-8")
    (evidence_dir / "capture.notes").write_text("skip stdout.log: not provided\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps({"files": {"report.md": "report.md", "stderr.log": "stderr.log"}}, indent=2) + "\n",
        encoding="utf-8",
    )

    run_dir = project_dir / "runs" / "run-42"
    (run_dir / "audit").mkdir(parents=True, exist_ok=True)
    (run_dir / "events.jsonl").write_text('{"type":"run.completed","hash":"sha256:1"}\n', encoding="utf-8")
    (run_dir / "run.json").write_text('{"run_id":"run-42"}\n', encoding="utf-8")

    timeline_dir = project_dir / "timelines" / "tl-1"
    timeline_dir.mkdir(parents=True, exist_ok=True)
    (timeline_dir / "assembly.jsonl").write_text('{"id":"e1"}\n', encoding="utf-8")
    raw_projection = '{"timeline":"raw"}\n'
    (timeline_dir / "assembly.json").write_text(raw_projection, encoding="utf-8")
    (timeline_dir / "assembly.identity.json").write_text('{"timeline_id":"tl-1"}\n', encoding="utf-8")

    (project_dir / "plan.json").write_text('{"ok":true}\n', encoding="utf-8")
    (project_dir / ".astrid-session").write_text("session\n", encoding="utf-8")
    (project_dir / "current_run.json").write_text('{"run_id":"run-42"}\n', encoding="utf-8")

    run = ActorRun(
        id="capture-run",
        scenario_name="capture",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "capture-slug"},
    )

    adapter.capture(Scenario(name="capture"), run, evidence_dir)

    assert (evidence_dir / "plan.json").is_file()
    assert (evidence_dir / ".astrid-session").is_file()
    assert (evidence_dir / "current_run.json").is_file()
    assert (evidence_dir / "tree.txt").is_file()
    assert (evidence_dir / "runs" / "run-42" / "events.jsonl").is_file()
    assert (evidence_dir / "runs" / "run-42" / "run.json").is_file()
    assert (evidence_dir / "timelines" / "tl-1" / "assembly.jsonl").is_file()
    assert (evidence_dir / "timelines" / "tl-1" / "assembly.identity.json").is_file()
    assert (evidence_dir / "timelines" / "tl-1" / "assembly.json").read_text(encoding="utf-8") == raw_projection

    notes = (evidence_dir / "capture.notes").read_text(encoding="utf-8")
    assert "skip stdout.log: not provided" in notes
    assert "skip runs/run-42/audit/ledger.jsonl: source not present" in notes
    assert "skip timelines/tl-1/assembly.head.json: source not present" in notes

    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"]["runs/run-42/events.jsonl"] == "runs/run-42/events.jsonl"
    assert manifest["files"]["timelines/tl-1/assembly.json"] == "timelines/tl-1/assembly.json"
    assert "runs/run-42/audit/ledger.jsonl" in manifest["capture_gaps"]


def test_capture_enforces_smoke_events_artifact(tmp_path: Path) -> None:
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "smoke-slug"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "runs").mkdir(parents=True, exist_ok=True)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("", encoding="utf-8")

    run = ActorRun(
        id="smoke-run",
        scenario_name="_smoke",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "smoke-slug"},
    )

    try:
        adapter.capture(Scenario(name="_smoke"), run, evidence_dir)
    except RuntimeError as exc:
        assert "runs/*/events.jsonl" in str(exc)
    else:
        raise AssertionError("expected smoke capture to require runs/*/events.jsonl")

    assert (evidence_dir / "tree.txt").is_file()
    notes = (evidence_dir / "capture.notes").read_text(encoding="utf-8")
    assert "note: no events.jsonl found under any run dir" in notes


# ---------------------------------------------------------------------------
# T9: command_policy, canonical_bypass_patterns, classify_success
# ---------------------------------------------------------------------------


def test_command_policy_returns_astrid_deny_patterns_and_advisory_enforce(
    tmp_path: Path,
) -> None:
    """command_policy must include the legacy bypass regex in deny_patterns
    and set enforce=False for M1 advisory mode."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    scenario = Scenario(name="policy")
    run = ActorRun(
        id="pol-run",
        scenario_name="policy",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(tmp_path / "ws"),
    )

    policy = adapter.command_policy(scenario, run)

    assert isinstance(policy, dict)
    assert isinstance(policy["allow_patterns"], list)
    assert isinstance(policy["deny_patterns"], list)
    assert policy["enforce"] is False

    # The deny list must include the legacy bypass pattern.
    bypass_pat = r"\bpython3?\b.*?(?:-m\s+astrid\.packs\.|/\bastrid\b/packs/)"
    assert any(bypass_pat in dp for dp in policy["deny_patterns"]), (
        "deny_patterns must include the legacy bypass pattern"
    )

    # Allow patterns must include astrid CLI invocations.
    assert any("astrid" in ap for ap in policy["allow_patterns"]), (
        "allow_patterns must permit the astrid CLI"
    )


def test_canonical_bypass_patterns_matches_known_bypass_strings(
    tmp_path: Path,
) -> None:
    """The canonical bypass regex must detect direct pack execution
    and must NOT trigger on safe mentions like file-read markers."""
    import re

    adapter = AstridProjectAdapter(repo_root=tmp_path)
    patterns = adapter.canonical_bypass_patterns(Scenario(name="bypass"))
    assert len(patterns) == 1, "expected a single canonical bypass pattern"

    pat = re.compile(patterns[0], re.IGNORECASE)

    # Should match: python/python3 + -m astrid.packs.*
    assert pat.search("python -m astrid.packs.foo.bar")
    assert pat.search("python3 -m astrid.packs.auth.inspect")
    assert pat.search("  python -m astrid.packs.x  ")

    # Should match: path form /astrid/packs/ (only with python prefix)
    assert pat.search("python /astrid/packs/smoke.py --flag")

    # Should NOT match: file-read mentions (📖 read ./astrid/packs/...)
    assert not pat.search("📖 read ./astrid/packs/auth/inspect.py")

    # Should NOT match: plain python without pack path
    assert not pat.search("python -c 'print(1)'")
    assert not pat.search("python3 my_script.py")

    # Should NOT match: astrid CLI in discussion
    assert not pat.search("we used astrid.packs to inspect")


def test_classify_success_returns_authored_for_events_jsonl_evidence(
    tmp_path: Path,
) -> None:
    """When events.jsonl exists with content, classify_success must return
    at least AUTHORED."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("", encoding="utf-8")
    (evidence_dir / "tree.txt").write_text("plan.json\n", encoding="utf-8")

    # Create a run artifact with events.jsonl.
    events_dir = evidence_dir / "runs" / "run-1"
    events_dir.mkdir(parents=True)
    (events_dir / "events.jsonl").write_text('{"type":"run.started"}\n', encoding="utf-8")

    evidence_pack = EvidencePack(
        manifest={},
        evidence_dir=str(evidence_dir),
        files={"runs/run-1/events.jsonl": "runs/run-1/events.jsonl"},
        capture_notes=[],
        capture_gaps={},
    )

    level = adapter.classify_success(Scenario(name="s"), evidence_pack)
    # At minimum AUTHORED — higher is acceptable when other evidence exists.
    rank_order = {
        "authored": 0,
        "compiled": 1,
        "validated": 2,
        "runtime_attempted": 3,
        "runtime_proven": 4,
        "artifact_proven": 5,
        "quality_assessed": 6,
    }
    assert rank_order[level.value] >= rank_order["authored"], (
        f"expected at least authored, got {level.value}"
    )


def test_classify_success_returns_compiled_for_api_json_in_tree(
    tmp_path: Path,
) -> None:
    """When tree.txt mentions api.json, classify_success must return
    at least COMPILED."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("", encoding="utf-8")

    # events.jsonl for AUTHORED baseline.
    events_dir = evidence_dir / "runs" / "run-1"
    events_dir.mkdir(parents=True)
    (events_dir / "events.jsonl").write_text('{"type":"x"}\n', encoding="utf-8")

    # tree.txt with api.json mention.
    (evidence_dir / "tree.txt").write_text(
        "runs/\nout/artifacts/api.json\n", encoding="utf-8"
    )

    evidence_pack = EvidencePack(
        manifest={},
        evidence_dir=str(evidence_dir),
        files={
            "runs/run-1/events.jsonl": "runs/run-1/events.jsonl",
            "tree.txt": "tree.txt",
        },
        capture_notes=[],
        capture_gaps={},
    )

    level = adapter.classify_success(Scenario(name="s"), evidence_pack)
    assert level.value in ("compiled", "artifact_proven"), (
        f"expected at least compiled when api.json in tree, got {level.value}"
    )


def test_classify_success_returns_artifact_proven_for_output_files_in_tree(
    tmp_path: Path,
) -> None:
    """When tree.txt shows F out/ entries, classify_success must return
    ARTIFACT_PROVEN."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("", encoding="utf-8")
    (evidence_dir / "tree.txt").write_text(
        "F out/report.pdf\nF out/image.png\n", encoding="utf-8"
    )

    # events.jsonl for AUTHORED baseline.
    events_dir = evidence_dir / "runs" / "run-1"
    events_dir.mkdir(parents=True)
    (events_dir / "events.jsonl").write_text('{"type":"x"}\n', encoding="utf-8")

    evidence_pack = EvidencePack(
        manifest={},
        evidence_dir=str(evidence_dir),
        files={
            "runs/run-1/events.jsonl": "runs/run-1/events.jsonl",
            "tree.txt": "tree.txt",
        },
        capture_notes=[],
        capture_gaps={},
    )

    level = adapter.classify_success(Scenario(name="s"), evidence_pack)
    assert level == SuccessProofLevel.ARTIFACT_PROVEN, (
        f"expected artifact_proven when tree shows out/, got {level.value}"
    )


def test_classify_success_defaults_to_authored_without_structural_evidence(
    tmp_path: Path,
) -> None:
    """With no events.jsonl, plan.json, or tree artifacts, classify_success
    must return AUTHORED — the lowest rung on the proof ladder."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("", encoding="utf-8")
    (evidence_dir / "tree.txt").write_text("", encoding="utf-8")

    evidence_pack = EvidencePack(
        manifest={},
        evidence_dir=str(evidence_dir),
        files={},
        capture_notes=[],
        capture_gaps={},
    )

    level = adapter.classify_success(Scenario(name="s"), evidence_pack)
    assert level == SuccessProofLevel.AUTHORED, (
        f"expected authored as fallback, got {level.value}"
    )


def test_project_universal_checks_returns_stable_m2_results_without_crashing(
    tmp_path: Path,
) -> None:
    """Partial packs with no M4 triggers must still yield the stable M2-only dict."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("", encoding="utf-8")
    (evidence_dir / "tree.txt").write_text("", encoding="utf-8")

    result = adapter.project_universal_checks(Scenario(name="s"), evidence_dir)

    expected_keys = [
        "m2.u1.claim_vs_evidence",
        "m2.u2.no_direct_pack",
        "m2.u3.chain_integrity",
        "m2.u4.no_cross_project_leak",
        "m2.u5.auditability",
        "m2.u6.deliverable_hygiene",
        "m2.c1.head_sidecar_consistency",
        "m2.c2.artifact_provenance",
        "m2.c3.no_mutation_on_read",
        "m2.c4.projection_fidelity",
        "m2.s1.append_not_rewrite",
        "m2.s2.idempotent_reattach",
    ]
    assert list(result.keys()) == expected_keys

    for stable_id, check in result.items():
        assert isinstance(check, ScoredCheckResult), stable_id
        assert set(check.keys()) == {"id", "status", "evidence_refs", "detail"}

    for stable_id in (
        "m2.c3.no_mutation_on_read",
        "m2.c4.projection_fidelity",
        "m2.s1.append_not_rewrite",
        "m2.s2.idempotent_reattach",
    ):
        check = result[stable_id]
        assert check["status"] == "na"
        assert check.get("passed") is True
        assert check.get("undetermined") is False


def test_project_universal_checks_ignore_legacy_acceptance_mirror(
    tmp_path: Path,
) -> None:
    """Universal checks must depend on frozen evidence, not the mirrored
    ``extras.legacy_acceptance`` compatibility payload."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text(
        "python3 -m astrid.packs.video_editing.orchestrators.hype.run --flag\n",
        encoding="utf-8",
    )
    (evidence_dir / "tree.txt").write_text("", encoding="utf-8")

    without_mirror = Scenario(
        name="s",
        extras={"target_orchestrator": "video_editing.hype"},
    )
    with_mirror = Scenario(
        name="s",
        extras={
            "target_orchestrator": "video_editing.hype",
            "legacy_acceptance": [{"events_contain": "run_completed"}],
        },
    )

    plain_result = adapter.project_universal_checks(without_mirror, evidence_dir)
    mirrored_result = adapter.project_universal_checks(with_mirror, evidence_dir)

    assert list(mirrored_result.keys()) == list(plain_result.keys())
    assert plain_result["m2.u2.no_direct_pack"]["status"] == "fail"
    assert mirrored_result["m2.u2.no_direct_pack"] == plain_result["m2.u2.no_direct_pack"]


def test_project_universal_checks_appends_enabled_m4_results_after_m2_keys(
    tmp_path: Path,
) -> None:
    """Enabled M4 checks must append stable m4.* keys without changing M2 keys."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "manifest.json").write_text(
        json.dumps(
            {
                "m4_checks": {
                    "artifact_pipeline": {"enabled": True},
                }
            }
        ),
        encoding="utf-8",
    )
    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("", encoding="utf-8")
    (evidence_dir / "tree.txt").write_text("", encoding="utf-8")
    (evidence_dir / "m4").mkdir(parents=True)
    (evidence_dir / "m4" / "orchestrator_run_persists.json").write_text(
        json.dumps(
            {
                "terminal_status": "success",
                "run_json_status": "success",
                "artifacts_match_cas": True,
                "produces_event_count": 1,
                "artifact_count": 1,
            }
        ),
        encoding="utf-8",
    )
    (evidence_dir / "m4" / "artifact_pipeline.json").write_text(
        json.dumps(
            {
                "upstream_artifact_sha256": "a" * 64,
                "downstream_input_sha256": "a" * 64,
                "handoff_matches": True,
                "matched_provenance": True,
                "orphan_artifacts": [],
            }
        ),
        encoding="utf-8",
    )
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        json.dumps({"kind": "produces_check_passed"}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "run.json").write_text(
        json.dumps({"status": "success"}),
        encoding="utf-8",
    )

    scenario = Scenario(
        name="s",
        extras={
            "m4_checks": {
                "orchestrator_run_persists": {"enabled": True},
                "artifact_pipeline": {"enabled": False},
            }
        },
    )

    result = adapter.project_universal_checks(scenario, evidence_dir)

    assert list(result.keys()) == [
        "m2.u1.claim_vs_evidence",
        "m2.u2.no_direct_pack",
        "m2.u3.chain_integrity",
        "m2.u4.no_cross_project_leak",
        "m2.u5.auditability",
        "m2.u6.deliverable_hygiene",
        "m2.c1.head_sidecar_consistency",
        "m2.c2.artifact_provenance",
        "m2.c3.no_mutation_on_read",
        "m2.c4.projection_fidelity",
        "m2.s1.append_not_rewrite",
        "m2.s2.idempotent_reattach",
        "m4.orchestrator_run_persists.terminal_success",
    ]
    assert "m4.artifact_pipeline.provenance_handoff" not in result

    m4_result = result["m4.orchestrator_run_persists.terminal_success"]
    assert isinstance(m4_result, ScoredCheckResult)
    assert m4_result["status"] == "pass"
    assert m4_result["id"] == "m4.orchestrator_run_persists.terminal_success"


def test_project_universal_checks_merges_manifest_enabled_m4_results(
    tmp_path: Path,
) -> None:
    """Manifest-backed M4 declarations must merge under stable m4.* keys."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "manifest.json").write_text(
        json.dumps(
            {
                "m4_checks": {
                    "artifact_pipeline": {"enabled": True},
                }
            }
        ),
        encoding="utf-8",
    )
    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("", encoding="utf-8")
    (evidence_dir / "tree.txt").write_text("", encoding="utf-8")
    (evidence_dir / "m4").mkdir(parents=True)
    (evidence_dir / "m4" / "artifact_pipeline.json").write_text(
        json.dumps(
            {
                "upstream_artifact_sha256": "b" * 64,
                "downstream_input_sha256": "b" * 64,
                "handoff_matches": True,
                "matched_provenance": True,
                "orphan_artifacts": [],
            }
        ),
        encoding="utf-8",
    )
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        json.dumps({"kind": "produces_check_passed"}) + "\n",
        encoding="utf-8",
    )

    result = adapter.project_universal_checks(Scenario(name="s"), evidence_dir)

    assert "m4.artifact_pipeline.provenance_handoff" in result
    assert result["m4.artifact_pipeline.provenance_handoff"]["status"] == "pass"


def test_project_universal_checks_converts_unexpected_exceptions_to_failed_checks(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """One crashing check must not crash the battery or erase other results."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("", encoding="utf-8")
    (evidence_dir / "tree.txt").write_text("", encoding="utf-8")

    from tests.agentic.checks import claims

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(claims, "u1_claim_vs_evidence", boom)

    result = adapter.project_universal_checks(Scenario(name="s"), evidence_dir)

    failed = result["m2.u1.claim_vs_evidence"]
    assert failed["id"] == "U1"
    assert failed["status"] == "fail"
    assert failed.get("passed") is False
    assert failed["detail"]["reason"] == "unexpected adapter check exception"
    assert "RuntimeError: boom" in failed["detail"]["error"]
    assert "manifest.json" in failed["evidence_refs"]
    assert isinstance(result["m2.u2.no_direct_pack"], ScoredCheckResult)


def test_parity_bypass_detected_by_both_legacy_and_adapter(
    tmp_path: Path,
) -> None:
    """One representative bypass string must be detected by BOTH
    enforcement (_check_canonical_bypass in enforcement.py) AND the
    adapter's canonical_bypass_patterns — proving parity at the M1
    intersection of their detection capabilities.

    This is the SC10 coverage gate test."""
    import re

    from tests.agentic.enforcement import _check_canonical_bypass

    # Representative bypass: python3 -m astrid.packs.<anything>
    bypass_line = "python3 -m astrid.packs.video_editing.orchestrators.hype.run --flag"

    # --- Legacy enforcement ---
    stderr = tmp_path / "stderr.log"
    stderr.write_text(
        "Starting agent...\n"
        f"{bypass_line}\n"
        "Agent finished.\n"
    )
    legacy_result = _check_canonical_bypass(stderr, scenario_cfg=None)
    assert legacy_result is not None, (
        "Legacy _check_canonical_bypass must detect the bypass line"
    )
    assert bypass_line in legacy_result, (
        f"Legacy result must contain the bypass line; got {legacy_result!r}"
    )

    # --- Adapter policy ---
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    patterns = adapter.canonical_bypass_patterns(Scenario(name="parity"))
    assert len(patterns) == 1, "expected a single canonical bypass pattern"

    pat = re.compile(patterns[0], re.IGNORECASE)
    assert pat.search(bypass_line), (
        "Adapter canonical_bypass_patterns must detect the same bypass line"
    )

    # --- Safe line must NOT trigger either ---
    safe_line = "📖 read ./astrid/packs/video_editing/orchestrators/hype/run.py"
    safe_stderr = tmp_path / "safe_stderr.log"
    safe_stderr.write_text(f"{safe_line}\n")
    assert _check_canonical_bypass(safe_stderr, scenario_cfg=None) is None, (
        "Legacy must not flag a file-read mention"
    )
    assert not pat.search(safe_line), (
        "Adapter must not flag a file-read mention"
    )


# ---------------------------------------------------------------------------
# T14: Smoke evidence-pack tests — Sisypy core, mandatory Astrid,
#      optional-miss notes, cheap verifier-output inspection
# ---------------------------------------------------------------------------


def test_smoke_evidence_pack_sisypy_core_artifacts_present(tmp_path: Path) -> None:
    """After a successful _smoke capture, the evidence directory must contain
    the Sisypy core evidence artifacts: report.md, stderr.log, capture.notes,
    and manifest.json — all present and non-empty where applicable."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "smoke-slug"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    # Pre-create Sisypy core artifacts that the fake dispatcher would produce.
    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("stderr content\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps({"files": {"report.md": "report.md", "stderr.log": "stderr.log"}}, indent=2) + "\n",
        encoding="utf-8",
    )

    # Create minimal project structure with events.jsonl (mandatory for smoke).
    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"plan_initialized","hash":"sha256:00"}\n{"type":"run_started","hash":"sha256:01"}\n',
        encoding="utf-8",
    )
    (project_dir / "plan.json").write_text('{"ok":true}\n', encoding="utf-8")

    run = ActorRun(
        id="smoke-core",
        scenario_name="_smoke",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "smoke-slug"},
    )

    adapter.capture(Scenario(name="_smoke"), run, evidence_dir)

    # --- Assert Sisypy core artifacts ---
    # report.md: mandatory, must exist and be non-empty.
    assert (evidence_dir / "report.md").is_file(), "report.md must exist"
    report_content = (evidence_dir / "report.md").read_text(encoding="utf-8")
    assert len(report_content.strip()) > 0, "report.md must be non-empty"

    # stderr.log: mandatory, must exist.
    assert (evidence_dir / "stderr.log").is_file(), "stderr.log must exist"
    stderr_content = (evidence_dir / "stderr.log").read_text(encoding="utf-8")
    assert len(stderr_content) > 0, "stderr.log must contain content"

    # capture.notes: always written by adapter, must exist.
    assert (evidence_dir / "capture.notes").is_file(), "capture.notes must exist"
    notes_content = (evidence_dir / "capture.notes").read_text(encoding="utf-8")
    assert len(notes_content.strip()) > 0, "capture.notes must be non-empty"

    # manifest.json: must exist and be valid JSON with files dict + capture_gaps.
    assert (evidence_dir / "manifest.json").is_file(), "manifest.json must exist"
    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    assert isinstance(manifest, dict), "manifest.json must be a JSON object"
    assert "files" in manifest, "manifest.json must have a 'files' key"
    assert isinstance(manifest["files"], dict), "manifest.json 'files' must be a dict"
    assert "capture_gaps" in manifest, "manifest.json must have a 'capture_gaps' key"


def test_smoke_evidence_pack_mandatory_astrid_artifacts_present(tmp_path: Path) -> None:
    """A successful _smoke capture must freeze at least one runs/*/events.jsonl
    and a non-empty tree.txt into the evidence pack."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "smoke-mand"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text("{}", encoding="utf-8")

    # Two run dirs — both with events.jsonl.
    for rid in ("run-1", "run-2"):
        rd = project_dir / "runs" / rid
        rd.mkdir(parents=True, exist_ok=True)
        (rd / "events.jsonl").write_text(
            f'{{"type":"run_started","hash":"sha256:{rid}"}}\n', encoding="utf-8"
        )

    # Additional project-level files so tree.txt is non-empty.
    (project_dir / "plan.json").write_text('{"ok":true}\n', encoding="utf-8")
    (project_dir / "notes.txt").write_text("some notes\n", encoding="utf-8")

    run = ActorRun(
        id="smoke-mand",
        scenario_name="_smoke",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "smoke-mand"},
    )

    adapter.capture(Scenario(name="_smoke"), run, evidence_dir)

    # --- Assert mandatory Astrid artifacts ---
    # events.jsonl: must exist in at least one run directory.
    events_found = list(evidence_dir.glob("runs/*/events.jsonl"))
    assert len(events_found) >= 1, (
        f"smoke capture must freeze at least one runs/*/events.jsonl; "
        f"found {len(events_found)}"
    )
    for events_file in events_found:
        content = events_file.read_text(encoding="utf-8")
        assert len(content.strip()) > 0, (
            f"events.jsonl at {events_file} must be non-empty"
        )

    # tree.txt: mandatory, must exist and be non-empty.
    assert (evidence_dir / "tree.txt").is_file(), "tree.txt must exist"
    tree_content = (evidence_dir / "tree.txt").read_text(encoding="utf-8")
    assert len(tree_content.strip()) > 0, "tree.txt must be non-empty"
    # tree.txt should mention the project entries.
    assert "plan.json" in tree_content, "tree.txt must mention plan.json"
    assert "runs/run-1/events.jsonl" in tree_content or "runs" in tree_content, (
        "tree.txt must show run directories"
    )


def test_smoke_evidence_pack_capture_notes_document_optional_misses(
    tmp_path: Path,
) -> None:
    """When optional artifacts are absent from the project directory, the
    _smoke capture must record each miss in capture.notes without failing."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "smoke-miss"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text("{}", encoding="utf-8")

    # Only create the bare minimum: one run with events.jsonl.
    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n', encoding="utf-8"
    )

    # Deliberately omit: plan.json, .astrid-session, current_run.json,
    # timelines/, runs/*/audit/ledger.jsonl — all optional.

    run = ActorRun(
        id="smoke-miss",
        scenario_name="_smoke",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "smoke-miss"},
    )

    adapter.capture(Scenario(name="_smoke"), run, evidence_dir)

    # capture.notes must document each absent optional artifact.
    notes_path = evidence_dir / "capture.notes"
    assert notes_path.is_file(), "capture.notes must exist after smoke capture"
    notes = notes_path.read_text(encoding="utf-8")

    # Optional artifacts that were never created should be recorded as skips.
    expected_misses = [
        "plan.json",
        ".astrid-session",
        "current_run.json",
        "ledger.jsonl",
    ]
    for miss_label in expected_misses:
        assert f"skip {miss_label}" in notes.lower() or miss_label in notes, (
            f"capture.notes must document missing optional artifact '{miss_label}'; "
            f"notes content: {notes!r}"
        )

    # The events.jsonl and tree.txt must NOT be skipped (they exist).
    assert "skip runs/run-1/events.jsonl" not in notes, (
        "events.jsonl must NOT appear as skipped"
    )
    assert "skip tree.txt" not in notes, (
        "tree.txt must NOT appear as skipped"
    )


def test_smoke_evidence_verifier_files_cheap_inspection(tmp_path: Path) -> None:
    """Verifier-relevant evidence files can be inspected for structural
    validity cheaply — without running the full hash-chain verifier.

    - events.jsonl: every line must be valid JSON (parseable).
    - tree.txt: must contain expected directory entries with decent size.
    - report.md: must contain numbered sections (deliverable shape).
    - stderr.log: must exist (no structural assertions beyond presence).
    """
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "smoke-verify"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text("{}", encoding="utf-8")

    # Create realistic project structure with multiple files.
    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"plan_initialized","hash":"sha256:0000000000000000000000000000000000000000000000000000000000000000"}\n'
        '{"type":"run_started","hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}\n',
        encoding="utf-8",
    )
    (run_dir / "run.json").write_text('{"run_id":"run-1"}\n', encoding="utf-8")
    (project_dir / "plan.json").write_text('{"ok":true}\n', encoding="utf-8")
    (project_dir / ".astrid-session").write_text("session-data\n", encoding="utf-8")
    (project_dir / "current_run.json").write_text('{"run_id":"run-1"}\n', encoding="utf-8")
    (project_dir / "src").mkdir(parents=True, exist_ok=True)
    (project_dir / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")

    run = ActorRun(
        id="smoke-verify",
        scenario_name="_smoke",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "smoke-verify"},
    )

    adapter.capture(Scenario(name="_smoke"), run, evidence_dir)

    # --- Cheap verifier-file inspections ---
    import json as json_mod

    # 1. events.jsonl: every line must be valid JSON.
    events_file = evidence_dir / "runs" / "run-1" / "events.jsonl"
    assert events_file.is_file(), "events.jsonl must exist after smoke capture"
    events_lines = events_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(events_lines) >= 2, "events.jsonl must have at least 2 events"
    for i, line in enumerate(events_lines, start=1):
        try:
            obj = json_mod.loads(line)
        except json_mod.JSONDecodeError as exc:
            raise AssertionError(
                f"events.jsonl line {i} is not valid JSON: {exc}"
            )
        assert isinstance(obj, dict), (
            f"events.jsonl line {i} must be a JSON object, got {type(obj).__name__}"
        )

    # 2. tree.txt: non-empty, contains expected entries.
    tree_path = evidence_dir / "tree.txt"
    assert tree_path.is_file(), "tree.txt must exist"
    tree_text = tree_path.read_text(encoding="utf-8")
    assert len(tree_text.strip()) > 0, "tree.txt must be non-empty"
    # tree.txt should show project structure.
    for expected_entry in ("plan.json", "runs", "events.jsonl", "src/main.py"):
        assert expected_entry in tree_text, (
            f"tree.txt must contain '{expected_entry}'"
        )
    # Size sanity: tree.txt should be reasonably small (< 100 KB).
    tree_size = tree_path.stat().st_size
    assert tree_size < 100_000, (
        f"tree.txt size {tree_size} bytes exceeds 100 KB sanity limit"
    )

    # 3. report.md: must exist and be non-empty (already checked in core test).
    report_path = evidence_dir / "report.md"
    assert report_path.is_file(), "report.md must exist"
    report_text = report_path.read_text(encoding="utf-8")
    # The smoke adapter overwrites report.md with numbered sections.
    assert "## 1." in report_text or "## 2." in report_text, (
        "report.md should contain numbered sections for deliverable shape"
    )

    # 4. stderr.log: must exist (no further structural assertion).
    stderr_path = evidence_dir / "stderr.log"
    assert stderr_path.is_file(), "stderr.log must exist"

    # 5. manifest.json: must be valid JSON with files dict.
    manifest_path = evidence_dir / "manifest.json"
    manifest = json_mod.loads(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict), "manifest.json must be a JSON object"
    assert "files" in manifest, "manifest.json must have 'files'"
    # events.jsonl and tree.txt must appear in the manifest files.
    manifest_files = manifest.get("files", {})
    assert isinstance(manifest_files, dict), "manifest 'files' must be a dict"
    assert "runs/run-1/events.jsonl" in manifest_files, (
        "manifest must register events.jsonl"
    )
    assert "tree.txt" in manifest_files, (
        "manifest must register tree.txt"
    )

    # 6. capture.notes: must exist and contain expected skip records.
    notes_path = evidence_dir / "capture.notes"
    assert notes_path.is_file(), "capture.notes must exist"
    notes_text = notes_path.read_text(encoding="utf-8")
    # Optional artifact skips should be present (ledger, timelines).
    assert "ledger" in notes_text.lower(), (
        "capture.notes should mention audit/ledger absence"
    )


# ---------------------------------------------------------------------------
# T18: capture/manifest m2_checks wiring
# ---------------------------------------------------------------------------


def test_capture_persists_scenario_m2_checks_into_manifest(tmp_path: Path) -> None:
    """When scenario.extras.m2_checks is declared, manifest must contain it."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "m2w-slug"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps({"files": {"report.md": "report.md", "stderr.log": "stderr.log"}}, indent=2) + "\n",
        encoding="utf-8",
    )

    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n', encoding="utf-8"
    )

    run = ActorRun(
        id="m2w-run",
        scenario_name="m2_checks_wired",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "m2w-slug"},
    )
    scenario = Scenario(
        name="m2_checks_wired",
        extras={
            "m2_checks": {
                "c3_no_mutation_on_read": {"enabled": True},
                "c4_projection_fidelity": {"enabled": False},
                "s1_append_not_rewrite": {"enabled": True},
            }
        },
    )

    adapter.capture(scenario, run, evidence_dir)

    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "m2_checks" in manifest, "manifest must have m2_checks key"
    assert manifest["m2_checks"] == {
        "c3_no_mutation_on_read": {"enabled": True},
        "c4_projection_fidelity": {"enabled": False},
        "s1_append_not_rewrite": {"enabled": True},
    }


def test_capture_manifest_omits_m2_checks_when_extras_absent(tmp_path: Path) -> None:
    """When scenario.extras has no m2_checks, manifest must not contain m2_checks."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "nom2-slug"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps({"files": {"report.md": "report.md", "stderr.log": "stderr.log"}}, indent=2) + "\n",
        encoding="utf-8",
    )

    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n', encoding="utf-8"
    )

    run = ActorRun(
        id="nom2-run",
        scenario_name="no_m2_checks",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "nom2-slug"},
    )
    scenario = Scenario(
        name="no_m2_checks",
        extras={"project_slug": "nom2-slug"},
    )

    adapter.capture(scenario, run, evidence_dir)

    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "m2_checks" not in manifest, (
        "manifest must not have m2_checks when scenario.extras omits it"
    )


def test_capture_handles_non_dict_m2_checks_gracefully(tmp_path: Path) -> None:
    """When scenario.extras.m2_checks is not a dict, capture must not crash."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "badm2-slug"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps({"files": {"report.md": "report.md", "stderr.log": "stderr.log"}}, indent=2) + "\n",
        encoding="utf-8",
    )

    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n', encoding="utf-8"
    )

    run = ActorRun(
        id="badm2-run",
        scenario_name="bad_m2_checks",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "badm2-slug"},
    )
    scenario = Scenario(
        name="bad_m2_checks",
        extras={"m2_checks": "not-a-dict"},
    )

    adapter.capture(scenario, run, evidence_dir)

    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    # Non-dict m2_checks is ignored — only dict-valued m2_checks is persisted.
    assert "m2_checks" not in manifest, (
        "non-dict m2_checks must not be written to manifest"
    )


def test_capture_produces_files_frozen_for_c2_provenance(tmp_path: Path) -> None:
    """Produces files under runs/*/steps/*/v*/produces/* must be frozen."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "prod-slug"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps({"files": {"report.md": "report.md", "stderr.log": "stderr.log"}}, indent=2) + "\n",
        encoding="utf-8",
    )

    # Run with events.jsonl (required for smoke and general capture).
    run_dir = project_dir / "runs" / "run-42"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n', encoding="utf-8"
    )

    # Produces files under steps/<step>/v<version>/produces/
    produces_dir = run_dir / "steps" / "my_step" / "v1" / "produces"
    produces_dir.mkdir(parents=True)
    (produces_dir / "output.json").write_text('{"result": "ok"}\n', encoding="utf-8")
    (produces_dir / "artifact.bin").write_text("binary-content", encoding="utf-8")

    run = ActorRun(
        id="prod-run",
        scenario_name="produces",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "prod-slug"},
    )

    adapter.capture(Scenario(name="produces"), run, evidence_dir)

    # Verify produces files are frozen at expected paths.
    frozen_output = evidence_dir / "runs" / "run-42" / "steps" / "my_step" / "v1" / "produces" / "output.json"
    assert frozen_output.is_file(), "produces output.json must be frozen"
    assert frozen_output.read_text(encoding="utf-8") == '{"result": "ok"}\n'

    frozen_bin = evidence_dir / "runs" / "run-42" / "steps" / "my_step" / "v1" / "produces" / "artifact.bin"
    assert frozen_bin.is_file(), "produces artifact.bin must be frozen"
    assert frozen_bin.read_text(encoding="utf-8") == "binary-content"

    # Manifest must register the produces files.
    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest_files = manifest.get("files", {})
    prod_output_key = "runs/run-42/steps/my_step/v1/produces/output.json"
    prod_bin_key = "runs/run-42/steps/my_step/v1/produces/artifact.bin"
    assert prod_output_key in manifest_files, f"manifest must register {prod_output_key}"
    assert prod_bin_key in manifest_files, f"manifest must register {prod_bin_key}"


def test_capture_optional_baseline_artifacts_frozen_when_present(tmp_path: Path) -> None:
    """Optional baseline/snapshot artifacts must be frozen when they exist."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "base-slug"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps({"files": {"report.md": "report.md", "stderr.log": "stderr.log"}}, indent=2) + "\n",
        encoding="utf-8",
    )

    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n', encoding="utf-8"
    )

    # Optional baseline/snapshot artifacts.
    (project_dir / "baseline_events.jsonl").write_text(
        '{"id":"ev1","hash":"sha256:bb"}\n', encoding="utf-8"
    )
    (project_dir / "git_diff.patch").write_text("+added line\n", encoding="utf-8")
    (project_dir / "reattach_stdout.txt").write_text("reattach ok\n", encoding="utf-8")
    (project_dir / "reattach_stderr.log").write_text("reattach warn\n", encoding="utf-8")

    # Timeline snapshot.
    tl_dir = project_dir / "timelines" / "tl-1"
    tl_dir.mkdir(parents=True)
    (tl_dir / "assembly.snapshot.json").write_text('{"snap":true}\n', encoding="utf-8")

    run = ActorRun(
        id="base-run",
        scenario_name="baseline",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "base-slug"},
    )

    adapter.capture(Scenario(name="baseline"), run, evidence_dir)

    # Verify baseline artifacts are frozen.
    assert (evidence_dir / "baseline_events.jsonl").is_file()
    assert (evidence_dir / "git_diff.patch").is_file()
    assert (evidence_dir / "reattach_stdout.txt").is_file()
    assert (evidence_dir / "reattach_stderr.log").is_file()

    # Verify snapshot artifact.
    frozen_snap = evidence_dir / "timelines" / "tl-1" / "assembly.snapshot.json"
    assert frozen_snap.is_file(), "assembly.snapshot.json must be frozen"
    assert frozen_snap.read_text(encoding="utf-8") == '{"snap":true}\n'

    # Manifest must register these artifacts.
    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest_files = manifest.get("files", {})
    assert "baseline_events.jsonl" in manifest_files
    assert "git_diff.patch" in manifest_files
    assert "reattach_stdout.txt" in manifest_files
    assert "reattach_stderr.log" in manifest_files
    assert "timelines/tl-1/assembly.snapshot.json" in manifest_files


def test_capture_does_not_fail_when_optional_baseline_artifacts_absent(tmp_path: Path) -> None:
    """Optional baseline artifacts must not cause capture failure when absent."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "no-base-slug"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps({"files": {"report.md": "report.md", "stderr.log": "stderr.log"}}, indent=2) + "\n",
        encoding="utf-8",
    )

    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n', encoding="utf-8"
    )

    run = ActorRun(
        id="no-base-run",
        scenario_name="no_baseline",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "no-base-slug"},
    )

    # Must not raise.
    adapter.capture(Scenario(name="no_baseline"), run, evidence_dir)

    # capture.notes must document skips for absent optional artifacts.
    notes = (evidence_dir / "capture.notes").read_text(encoding="utf-8")
    for artifact in ("baseline_events.jsonl", "git_diff.patch",
                     "reattach_stdout.txt", "reattach_stderr.log"):
        assert f"skip {artifact}" in notes, (
            f"capture.notes must document absent optional artifact '{artifact}'"
        )

    # Manifest must still be present and valid.
    assert (evidence_dir / "manifest.json").is_file()
    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "files" in manifest


# ---------------------------------------------------------------------------
# T23: Tampered fixture — deliberately fails one intended M2 check while
#      unrelated absent-trigger checks report status: na
# ---------------------------------------------------------------------------


def test_tampered_smoke_fixture_fails_exactly_one_m2_check_others_na(tmp_path: Path) -> None:
    """Build a smoke-like evidence pack with a declared C3 trigger, provide
    the required baseline/final/diff evidence, then tamper final events so
    that an extra post-read event exists.  Verify:

    * C3 fails with an ``extra_events`` mismatch.
    * C4, S1, and S2 are ``na`` (trigger not declared).
    * Universal checks still produce valid results.
    """
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    # --- Sisypy core artifacts (mandatory for capture completeness) ---
    (evidence_dir / "report.md").write_text(
        "# Tampered smoke report\n\n"
        "## 1. Setup\n\nBaseline captured before read.\n\n"
        "## 2. Read phase\n\nFake agent inspected the project.\n\n"
        "## 3. Tamper\n\nAn extra event was injected after read.\n\n"
        "## 4. Evidence\n\nFrozen pack includes the tampered stream.\n\n"
        "## 5. Verification\n\nC3 must detect the extra event.\n\n"
        "## 6. Summary\n\nStructural smoke tamper fixture.\n",
        encoding="utf-8",
    )
    (evidence_dir / "stderr.log").write_text("tampered smoke stderr\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps({"files": {"report.md": "report.md", "stderr.log": "stderr.log"}}, indent=2) + "\n",
        encoding="utf-8",
    )

    # --- Baseline events (snapshot before read) ---
    baseline_lines = [
        {"kind": "run_started", "ts": "2025-01-01T00:00:00Z", "run_id": "run-1", "hash": "sha256:" + "a" * 64},
        {"kind": "step_dispatched", "ts": "2025-01-01T00:00:01Z", "run_id": "run-1", "hash": "sha256:" + "b" * 64},
    ]
    (evidence_dir / "baseline_events.jsonl").write_text(
        "\n".join(json.dumps(row, separators=(",", ":")) for row in baseline_lines) + "\n",
        encoding="utf-8",
    )

    # --- Final events (tampered: includes an extra event after read) ---
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    final_lines = [
        {"kind": "run_started", "ts": "2025-01-01T00:00:00Z", "run_id": "run-1", "hash": "sha256:" + "a" * 64},
        {"kind": "step_dispatched", "ts": "2025-01-01T00:00:01Z", "run_id": "run-1", "hash": "sha256:" + "b" * 64},
        # Extra event injected after read — this is the tamper.
        {"kind": "file_written", "ts": "2025-01-01T00:00:02Z", "run_id": "run-1", "hash": "sha256:" + "c" * 64},
    ]
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(row, separators=(",", ":")) for row in final_lines) + "\n",
        encoding="utf-8",
    )
    (run_dir / "run.json").write_text(
        json.dumps({"run_id": "run-1", "project_slug": "tampered-smoke"}), encoding="utf-8"
    )

    # --- Empty git diff (no working-tree changes) ---
    (evidence_dir / "git_diff.patch").write_text("", encoding="utf-8")

    # --- Tree artifact (required for completeness) ---
    (evidence_dir / "tree.txt").write_text("runs/run-1/events.jsonl\n", encoding="utf-8")

    # --- Scenario with declared C3 trigger ---
    scenario = Scenario(
        name="_smoke",
        extras={
            "m2_checks": {
                "c3_no_mutation_on_read": {"enabled": True},
            }
        },
    )

    results = adapter.project_universal_checks(scenario, evidence_dir)

    # --- C3 must fail (extra events after read) ---
    c3 = results["m2.c3.no_mutation_on_read"]
    assert c3["status"] == "fail", f"expected C3 fail, got {c3['status']!r}"
    assert set(c3.keys()) == {"id", "status", "evidence_refs", "detail"}
    assert c3["id"] == "C3"
    mismatches = c3["detail"].get("mismatches", [])
    extra_kinds = {m["kind"] for m in mismatches}
    assert "extra_events" in extra_kinds, (
        f"expected extra_events mismatch in C3 detail, got {mismatches!r}"
    )

    # --- C4, S1, S2 must be na (trigger not declared) ---
    for stable_id in (
        "m2.c4.projection_fidelity",
        "m2.s1.append_not_rewrite",
        "m2.s2.idempotent_reattach",
    ):
        check = results[stable_id]
        assert check["status"] == "na", (
            f"expected {stable_id} na (absent trigger), got {check['status']!r}"
        )
        assert check.get("passed") is True
        assert check.get("undetermined") is False

    # --- Universal checks must still produce valid results ---
    for stable_id in (
        "m2.u1.claim_vs_evidence",
        "m2.u2.no_direct_pack",
        "m2.u3.chain_integrity",
        "m2.u4.no_cross_project_leak",
        "m2.u5.auditability",
        "m2.u6.deliverable_hygiene",
        "m2.c1.head_sidecar_consistency",
        "m2.c2.artifact_provenance",
    ):
        check = results[stable_id]
        assert isinstance(check, ScoredCheckResult), (
            f"{stable_id} must be a ScoredCheckResult, got {type(check).__name__}"
        )
        assert set(check.keys()) == {"id", "status", "evidence_refs", "detail"}
        assert check["status"] in ("pass", "fail", "na"), (
            f"{stable_id} status must be pass/fail/na, got {check['status']!r}"
        )


# ---------------------------------------------------------------------------
# T4: M4 check dispatch and M2/M4 coexistence tests
# ---------------------------------------------------------------------------


def test_project_universal_checks_all_m4_disabled_returns_only_m2_keys(
    tmp_path: Path,
) -> None:
    """When all M4 triggers are disabled in extras, only the 12 stable M2 keys
    must appear; no m4.* keys may leak into the result dict."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("", encoding="utf-8")
    (evidence_dir / "tree.txt").write_text("", encoding="utf-8")

    scenario = Scenario(
        name="s",
        extras={
            "m4_checks": {
                "orchestrator_run_persists": {"enabled": False},
                "artifact_pipeline": {"enabled": False},
                "timeline_compose_edit": {"enabled": False},
                "timeline_concurrent_version_conflict": {"enabled": False},
                "taskrun_concurrent_lease": {"enabled": False},
                "durability_after_crash": {"enabled": False},
                "timeline_large_audit": {"enabled": False},
            }
        },
    )

    result = adapter.project_universal_checks(scenario, evidence_dir)

    expected_m2_keys = [
        "m2.u1.claim_vs_evidence",
        "m2.u2.no_direct_pack",
        "m2.u3.chain_integrity",
        "m2.u4.no_cross_project_leak",
        "m2.u5.auditability",
        "m2.u6.deliverable_hygiene",
        "m2.c1.head_sidecar_consistency",
        "m2.c2.artifact_provenance",
        "m2.c3.no_mutation_on_read",
        "m2.c4.projection_fidelity",
        "m2.s1.append_not_rewrite",
        "m2.s2.idempotent_reattach",
    ]
    # All M4 disabled — result must have exactly the M2 keys and nothing else.
    result_keys = list(result.keys())
    assert result_keys == expected_m2_keys, (
        f"expected only M2 keys, got extra keys: "
        f"{set(result_keys) - set(expected_m2_keys)}"
    )


def test_project_universal_checks_disabled_m4_result_absent(
    tmp_path: Path,
) -> None:
    """A mixed scenario with one enabled and one disabled M4 trigger must
    include only the enabled check result; the disabled trigger must be
    completely absent (not even an ``na`` entry)."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("", encoding="utf-8")
    (evidence_dir / "tree.txt").write_text("", encoding="utf-8")
    (evidence_dir / "m4").mkdir(parents=True)
    (evidence_dir / "m4" / "orchestrator_run_persists.json").write_text(
        json.dumps(
            {
                "terminal_status": "success",
                "run_json_status": "success",
                "artifacts_match_cas": True,
                "produces_event_count": 1,
                "artifact_count": 1,
            }
        ),
        encoding="utf-8",
    )
    run_dir = evidence_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        json.dumps({"kind": "produces_check_passed"}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "run.json").write_text(
        json.dumps({"status": "success"}),
        encoding="utf-8",
    )

    scenario = Scenario(
        name="s",
        extras={
            "m4_checks": {
                "orchestrator_run_persists": {"enabled": True},
                "timeline_large_audit": {"enabled": False},
            }
        },
    )

    result = adapter.project_universal_checks(scenario, evidence_dir)

    # Enabled → present.
    assert "m4.orchestrator_run_persists.terminal_success" in result
    assert result["m4.orchestrator_run_persists.terminal_success"]["status"] == "pass"

    # Disabled → absent (not even na).
    assert "m4.timeline_large_audit.large_chain_verified" not in result

    # Other M4 checks also absent (never declared).
    for absent_key in (
        "m4.artifact_pipeline.provenance_handoff",
        "m4.timeline_compose_edit.composite_projection",
        "m4.timeline_concurrent_version_conflict.stale_version_conflict",
        "m4.taskrun_concurrent_lease.single_writer_lease",
        "m4.durability_after_crash.head_jsonl_desync_detected",
    ):
        assert absent_key not in result, (
            f"undeclared M4 key {absent_key} must not appear in result"
        )


def test_project_universal_checks_manifest_fallback_when_extras_lack_m4_checks(
    tmp_path: Path,
) -> None:
    """When scenario.extras exists but has no ``m4_checks`` key, manifest-based
    M4 declarations must still be resolved and merged into results."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "manifest.json").write_text(
        json.dumps(
            {
                "m4_checks": {
                    "artifact_pipeline": {"enabled": True},
                }
            }
        ),
        encoding="utf-8",
    )
    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("", encoding="utf-8")
    (evidence_dir / "tree.txt").write_text("", encoding="utf-8")
    (evidence_dir / "m4").mkdir(parents=True)
    (evidence_dir / "m4" / "artifact_pipeline.json").write_text(
        json.dumps(
            {
                "upstream_artifact_sha256": "c" * 64,
                "downstream_input_sha256": "c" * 64,
                "handoff_matches": True,
                "matched_provenance": True,
                "orphan_artifacts": [],
            }
        ),
        encoding="utf-8",
    )
    run_dir = evidence_dir / "runs" / "run-a"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        json.dumps({"kind": "produces_check_passed"}) + "\n",
        encoding="utf-8",
    )

    # Scenario has extras but NO m4_checks key — manifest provides it.
    scenario = Scenario(name="s", extras={"project_slug": "m4-fallback"})

    result = adapter.project_universal_checks(scenario, evidence_dir)

    assert "m4.artifact_pipeline.provenance_handoff" in result
    assert result["m4.artifact_pipeline.provenance_handoff"]["status"] == "pass"


# ---------------------------------------------------------------------------
# T5: manifest persistence for m4_checks
# ---------------------------------------------------------------------------


def test_capture_persists_scenario_m4_checks_into_manifest(tmp_path: Path) -> None:
    """When scenario.extras.m4_checks is a dict, manifest.json must contain it."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "m4w-slug"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps({"files": {"report.md": "report.md", "stderr.log": "stderr.log"}}, indent=2) + "\n",
        encoding="utf-8",
    )

    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n', encoding="utf-8"
    )

    run = ActorRun(
        id="m4w-run",
        scenario_name="m4_checks_wired",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "m4w-slug"},
    )
    scenario = Scenario(
        name="m4_checks_wired",
        extras={
            "m4_checks": {
                "orchestrator_run_persists": {"enabled": True},
                "artifact_pipeline": {"enabled": False},
                "timeline_compose_edit": {"enabled": True},
            }
        },
    )

    adapter.capture(scenario, run, evidence_dir)

    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "m4_checks" in manifest, "manifest must have m4_checks key"
    assert manifest["m4_checks"] == {
        "orchestrator_run_persists": {"enabled": True},
        "artifact_pipeline": {"enabled": False},
        "timeline_compose_edit": {"enabled": True},
    }


def test_capture_manifest_omits_m4_checks_when_extras_absent(tmp_path: Path) -> None:
    """When scenario.extras has no m4_checks, manifest must not contain m4_checks."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "nom4-slug"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps({"files": {"report.md": "report.md", "stderr.log": "stderr.log"}}, indent=2) + "\n",
        encoding="utf-8",
    )

    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n', encoding="utf-8"
    )

    run = ActorRun(
        id="nom4-run",
        scenario_name="no_m4_checks",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "nom4-slug"},
    )
    scenario = Scenario(
        name="no_m4_checks",
        extras={"project_slug": "nom4-slug"},
    )

    adapter.capture(scenario, run, evidence_dir)

    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "m4_checks" not in manifest, (
        "manifest must not have m4_checks when scenario.extras omits it"
    )


def test_capture_handles_non_dict_m4_checks_gracefully(tmp_path: Path) -> None:
    """When scenario.extras.m4_checks is not a dict, capture must not crash
    and must not write m4_checks to manifest."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "badm4-slug"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps({"files": {"report.md": "report.md", "stderr.log": "stderr.log"}}, indent=2) + "\n",
        encoding="utf-8",
    )

    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n', encoding="utf-8"
    )

    run = ActorRun(
        id="badm4-run",
        scenario_name="bad_m4_checks",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "badm4-slug"},
    )
    scenario = Scenario(
        name="bad_m4_checks",
        extras={"m4_checks": ["not", "a", "dict"]},
    )

    adapter.capture(scenario, run, evidence_dir)

    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "m4_checks" not in manifest, (
        "non-dict m4_checks must not be written to manifest"
    )


def test_capture_persists_both_m2_and_m4_checks_together(tmp_path: Path) -> None:
    """When both m2_checks and m4_checks are dict-valued in extras, both must
    appear in manifest and m2_checks must not be disturbed by m4_checks."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "both-slug"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps({"files": {"report.md": "report.md", "stderr.log": "stderr.log"}}, indent=2) + "\n",
        encoding="utf-8",
    )

    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n', encoding="utf-8"
    )

    run = ActorRun(
        id="both-run",
        scenario_name="both_checks",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "both-slug"},
    )
    scenario = Scenario(
        name="both_checks",
        extras={
            "m2_checks": {
                "c3_no_mutation_on_read": {"enabled": True},
                "s1_append_not_rewrite": {"enabled": True},
            },
            "m4_checks": {
                "orchestrator_run_persists": {"enabled": True},
                "durability_after_crash": {"enabled": False},
            },
        },
    )

    adapter.capture(scenario, run, evidence_dir)

    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "m2_checks" in manifest, "manifest must have m2_checks"
    assert "m4_checks" in manifest, "manifest must have m4_checks"
    assert manifest["m2_checks"] == {
        "c3_no_mutation_on_read": {"enabled": True},
        "s1_append_not_rewrite": {"enabled": True},
    }
    assert manifest["m4_checks"] == {
        "orchestrator_run_persists": {"enabled": True},
        "durability_after_crash": {"enabled": False},
    }


# ---------------------------------------------------------------------------
# T6: M5 check wiring in capture + universal checks
# ---------------------------------------------------------------------------


def test_capture_creates_manifest_and_persists_m5_checks(tmp_path: Path) -> None:
    """Capture must create manifest.json when absent and persist dict-valued
    scenario.extras.m5_checks into it."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "m5w-slug"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")

    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n', encoding="utf-8"
    )

    run = ActorRun(
        id="m5w-run",
        scenario_name="m5_checks_wired",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "m5w-slug"},
    )
    scenario = Scenario(
        name="m5_checks_wired",
        extras={
            "m5_checks": {
                "no_fabricated_tool_id": {"enabled": True},
                "author_run_revise_loop": {"enabled": False},
            }
        },
    )

    adapter.capture(scenario, run, evidence_dir)

    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"]["report.md"] == "report.md"
    assert manifest["files"]["stderr.log"] == "stderr.log"
    assert manifest["m5_checks"] == {
        "no_fabricated_tool_id": {"enabled": True},
        "author_run_revise_loop": {"enabled": False},
    }


def test_project_universal_checks_appends_enabled_m5_results_after_m4_keys(
    tmp_path: Path,
) -> None:
    """Enabled M5 checks must merge under stable m5.* keys after the M4 block."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (evidence_dir / "report.md").write_text(
        "No matching tool exists in the Astrid registry.\n",
        encoding="utf-8",
    )
    (evidence_dir / "stderr.log").write_text(
        "\n".join(
            [
                "$ astrid executors search music clearance",
                "$ astrid orchestrators search sync licensing",
            ]
        ),
        encoding="utf-8",
    )
    (evidence_dir / "tree.txt").write_text("", encoding="utf-8")

    scenario = Scenario(
        name="s",
        extras={
            "m4_checks": {
                "orchestrator_run_persists": {"enabled": False},
            },
            "m5_checks": {
                "no_fabricated_tool_id": {"enabled": True},
                "search_fallback_after_zero_hits": {"enabled": False},
            },
        },
    )

    result = adapter.project_universal_checks(scenario, evidence_dir)

    assert "m5.no_tool_exists_pushback.no_fabricated_tool_id" in result
    assert result["m5.no_tool_exists_pushback.no_fabricated_tool_id"]["status"] == "pass"
    assert "m5.recover_from_no_search_results.search_fallback_after_zero_hits" not in result
    assert list(result.keys())[-1] == "m5.no_tool_exists_pushback.no_fabricated_tool_id"


def test_project_universal_checks_manifest_fallback_when_extras_lack_m5_checks(
    tmp_path: Path,
) -> None:
    """When scenario.extras exists without m5_checks, manifest declarations
    must still dispatch enabled M5 checks."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "manifest.json").write_text(
        json.dumps(
            {
                "m5_checks": {
                    "projects_runs_sessions_discovered": {"enabled": True},
                }
            }
        ),
        encoding="utf-8",
    )
    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text(
        "\n".join(
            [
                "$ astrid projects ls",
                "$ astrid runs ls",
                "$ astrid sessions ls",
            ]
        ),
        encoding="utf-8",
    )
    (evidence_dir / "tree.txt").write_text("", encoding="utf-8")

    result = adapter.project_universal_checks(
        Scenario(name="s", extras={"project_slug": "m5-fallback"}),
        evidence_dir,
    )

    assert "m5.discover_projects_runs_sessions.projects_runs_sessions_discovered" in result
    assert (
        result["m5.discover_projects_runs_sessions.projects_runs_sessions_discovered"]["status"]
        == "pass"
    )


# ---------------------------------------------------------------------------
# T8: capture tests — lease capture, M4 diagnostic capture, manifest labels
# ---------------------------------------------------------------------------


def test_capture_lease_json_persisted_in_manifest(tmp_path: Path) -> None:
    """When runs/*/lease.json exists, it must be captured and listed in
    manifest.files with the correct label."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "lease-slug"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps(
            {"files": {"report.md": "report.md", "stderr.log": "stderr.log"}},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n', encoding="utf-8"
    )
    (run_dir / "lease.json").write_text(
        json.dumps({"holder": "agent-1", "epoch": 1}) + "\n",
        encoding="utf-8",
    )

    run = ActorRun(
        id="lease-run",
        scenario_name="lease_test",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "lease-slug"},
    )
    scenario = Scenario(name="lease_test")

    adapter.capture(scenario, run, evidence_dir)

    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "runs/run-1/lease.json" in manifest["files"], (
        "manifest.files must include runs/run-1/lease.json when present"
    )
    assert manifest["files"]["runs/run-1/lease.json"] == "runs/run-1/lease.json"


def test_capture_missing_lease_json_produces_skip_note(tmp_path: Path) -> None:
    """When runs/*/lease.json is absent, capture must record a skip note
    and not fail."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "nolease-slug"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps(
            {"files": {"report.md": "report.md", "stderr.log": "stderr.log"}},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # Create run dir with events.jsonl but NO lease.json
    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n', encoding="utf-8"
    )

    run = ActorRun(
        id="nolease-run",
        scenario_name="nolease_test",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "nolease-slug"},
    )
    scenario = Scenario(name="nolease_test")

    adapter.capture(scenario, run, evidence_dir)

    # Verify manifest does NOT contain lease
    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "runs/run-1/lease.json" not in manifest["files"], (
        "manifest.files must not contain lease.json when absent"
    )

    # Verify capture.notes records the skip
    notes_text = (evidence_dir / "capture.notes").read_text(encoding="utf-8")
    assert "skip" in notes_text.lower() or "lease.json" in notes_text, (
        "capture.notes must mention the missing lease.json"
    )


def test_capture_m4_diagnostics_copied_to_evidence(tmp_path: Path) -> None:
    """When project_dir/m4/ contains *.json, *.jsonl, and *.txt files,
    they must be copied to evidence_dir with correct manifest labels."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "m4cap-slug"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps(
            {"files": {"report.md": "report.md", "stderr.log": "stderr.log"}},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # Create M4 diagnostic directory with various allowed file types
    m4_dir = project_dir / "m4"
    m4_dir.mkdir(parents=True)
    (m4_dir / "orchestrator_run_persists.json").write_text(
        json.dumps({"terminal_status": "success"}) + "\n",
        encoding="utf-8",
    )
    (m4_dir / "events.jsonl").write_text(
        '{"kind":"test","hash":"sha256:bb"}\n', encoding="utf-8"
    )
    (m4_dir / "notes.txt").write_text("M4 diagnostic notes.\n", encoding="utf-8")
    # Non-allowed file — must be excluded
    (m4_dir / "ignored.md").write_text("# ignored\n", encoding="utf-8")
    (m4_dir / "ignored.dat").write_bytes(b"\x00\x01\x02")

    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n', encoding="utf-8"
    )

    run = ActorRun(
        id="m4cap-run",
        scenario_name="m4cap_test",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "m4cap-slug"},
    )
    scenario = Scenario(name="m4cap_test")

    adapter.capture(scenario, run, evidence_dir)

    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))

    # Allowed types must be captured
    assert "m4/orchestrator_run_persists.json" in manifest["files"], (
        "m4/orchestrator_run_persists.json must be captured"
    )
    assert "m4/events.jsonl" in manifest["files"], (
        "m4/events.jsonl must be captured"
    )
    assert "m4/notes.txt" in manifest["files"], (
        "m4/notes.txt must be captured"
    )

    # Disallowed types must NOT be captured
    assert "m4/ignored.md" not in manifest["files"], (
        "m4/ignored.md must NOT be captured (not in allowlist)"
    )
    assert "m4/ignored.dat" not in manifest["files"], (
        "m4/ignored.dat must NOT be captured (not in allowlist)"
    )

    # Verify the files actually exist in evidence_dir
    assert (evidence_dir / "m4" / "orchestrator_run_persists.json").is_file()
    assert (evidence_dir / "m4" / "events.jsonl").is_file()
    assert (evidence_dir / "m4" / "notes.txt").is_file()
    assert not (evidence_dir / "m4" / "ignored.md").exists()
    assert not (evidence_dir / "m4" / "ignored.dat").exists()


def test_capture_missing_m4_dir_produces_skip_note(tmp_path: Path) -> None:
    """When project_dir/m4/ does not exist, capture must record a skip note
    and not fail."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "nom4-slug-cap"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps(
            {"files": {"report.md": "report.md", "stderr.log": "stderr.log"}},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # No m4/ directory created

    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n', encoding="utf-8"
    )

    run = ActorRun(
        id="nom4cap-run",
        scenario_name="nom4cap_test",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "nom4-slug-cap"},
    )
    scenario = Scenario(name="nom4cap_test")

    adapter.capture(scenario, run, evidence_dir)

    # Verify capture.notes records the missing m4/ directory
    notes_text = (evidence_dir / "capture.notes").read_text(encoding="utf-8")
    assert "m4" in notes_text.lower(), (
        "capture.notes must mention the missing m4/ directory"
    )

    # Verify manifest doesn't have m4/ entries
    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    for key in manifest.get("files", {}):
        assert not key.startswith("m4/"), (
            f"manifest.files must not contain m4/ entries when m4/ absent: got {key}"
        )


def test_capture_manifest_file_labels_include_all_captured_artifacts(
    tmp_path: Path,
) -> None:
    """The manifest.files dict must register every captured artifact with
    its relative path label, including runs artifacts and tree.txt."""
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "labels-slug"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "report.md").write_text("# report\n", encoding="utf-8")
    (evidence_dir / "stderr.log").write_text("ok\n", encoding="utf-8")
    (evidence_dir / "manifest.json").write_text(
        json.dumps(
            {"files": {"report.md": "report.md", "stderr.log": "stderr.log"}},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # Create a rich project directory with multiple run artifacts
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "plan.json").write_text(
        json.dumps({"steps": []}) + "\n", encoding="utf-8"
    )
    run_dir = project_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        '{"type":"run_started","hash":"sha256:aa"}\n', encoding="utf-8"
    )
    (run_dir / "run.json").write_text(
        json.dumps({"status": "success"}) + "\n", encoding="utf-8"
    )
    (run_dir / "lease.json").write_text(
        json.dumps({"holder": "agent-1", "epoch": 1}) + "\n",
        encoding="utf-8",
    )
    audit_dir = run_dir / "audit"
    audit_dir.mkdir(parents=True)
    (audit_dir / "ledger.jsonl").write_text(
        '{"kind":"audit_entry","hash":"sha256:cc"}\n', encoding="utf-8"
    )

    run = ActorRun(
        id="labels-run",
        scenario_name="labels_test",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "labels-slug"},
    )
    scenario = Scenario(name="labels_test")

    adapter.capture(scenario, run, evidence_dir)

    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    files = manifest["files"]

    # Required evidence artifacts (capture.notes is written separately
    # after manifest update and is not listed in manifest.files)
    expected_labels = [
        "report.md",
        "stderr.log",
        "plan.json",
        "tree.txt",
    ]
    for label in expected_labels:
        assert label in files, (
            f"manifest.files must contain {label}"
        )
        assert files[label] == label, (
            f"manifest.files[{label!r}] label must match key, got {files[label]!r}"
        )

    # Run artifacts
    run_labels = [
        "runs/run-1/events.jsonl",
        "runs/run-1/run.json",
        "runs/run-1/lease.json",
        "runs/run-1/audit/ledger.jsonl",
    ]
    for label in run_labels:
        assert label in files, (
            f"manifest.files must contain {label}"
        )
        assert files[label] == label, (
            f"manifest.files[{label!r}] label must match key, got {files[label]!r}"
        )


def test_capture_sterilizes_fake_structural_m4_report_and_stdout(tmp_path: Path) -> None:
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "sterile-m4-slug"
    evidence_dir = tmp_path / "evidence"
    _write_capture_fixture(
        evidence_dir=evidence_dir,
        project_dir=project_dir,
        report_text="agent said it compiled and shipped api.json\n",
        stderr_text="",
        stdout_text="live actor output\n",
    )

    run = ActorRun(
        id="sterile-m4-run",
        scenario_name="timeline_compose_edit",
        mode=RunMode.STRUCTURAL,
        dispatcher="fake",
        workdir=str(workspace),
        extras={"project_slug": "sterile-m4-slug"},
    )
    scenario = Scenario(
        name="timeline_compose_edit",
        extras={"m4_checks": {"timeline_compose_edit": {"enabled": True}}},
    )

    adapter.capture(scenario, run, evidence_dir)

    report_text = (evidence_dir / "report.md").read_text(encoding="utf-8")
    stdout_text = (evidence_dir / "stdout.log").read_text(encoding="utf-8")
    assert "sterilized text intentionally avoids" in report_text
    assert len([line for line in report_text.splitlines() if line.strip()]) >= 30
    for section_num in range(1, 7):
        assert f"## {section_num}." in report_text
    assert "compiled" not in report_text
    assert "live actor output" not in stdout_text
    assert "verify behavior from frozen evidence files" in stdout_text


def test_capture_keeps_smoke_sterilized(tmp_path: Path) -> None:
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "smoke-slug"
    evidence_dir = tmp_path / "evidence"
    _write_capture_fixture(
        evidence_dir=evidence_dir,
        project_dir=project_dir,
        report_text="actor claims\n",
        stderr_text="",
        stdout_text="untrusted smoke stdout\n",
    )

    run = ActorRun(
        id="smoke-run",
        scenario_name="_smoke",
        mode=RunMode.STRUCTURAL,
        dispatcher="shell",
        workdir=str(workspace),
        extras={"project_slug": "smoke-slug"},
    )

    adapter.capture(Scenario(name="_smoke"), run, evidence_dir)

    report_text = (evidence_dir / "report.md").read_text(encoding="utf-8")
    stdout_text = (evidence_dir / "stdout.log").read_text(encoding="utf-8")
    assert "# _smoke structural evidence report" in report_text
    assert "untrusted smoke stdout" not in stdout_text


def test_capture_preserves_live_non_m4_actor_output(tmp_path: Path) -> None:
    adapter = AstridProjectAdapter(repo_root=tmp_path)
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".astrid-projects" / "live-slug"
    evidence_dir = tmp_path / "evidence"
    original_report = "real actor report\n"
    original_stdout = "real actor stdout\n"
    _write_capture_fixture(
        evidence_dir=evidence_dir,
        project_dir=project_dir,
        report_text=original_report,
        stderr_text="",
        stdout_text=original_stdout,
    )

    run = ActorRun(
        id="live-run",
        scenario_name="plain_live",
        mode=RunMode.LIVE,
        dispatcher="shell",
        workdir=str(workspace),
        extras={"project_slug": "live-slug"},
    )

    adapter.capture(Scenario(name="plain_live"), run, evidence_dir)

    assert (evidence_dir / "report.md").read_text(encoding="utf-8") == original_report
    assert (evidence_dir / "stdout.log").read_text(encoding="utf-8") == original_stdout
