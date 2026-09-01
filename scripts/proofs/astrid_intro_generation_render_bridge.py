#!/usr/bin/env python3
"""Custody-safe isolated proof for the Intro generation-to-render bridge.

The proof snapshots the live Intro read-only, then uses only public Astrid SDK
mutations and reads inside a disposable project root.  It deliberately reuses
the accepted text-binding proof's snapshot/bootstrap, deterministic plate, and
timeline helpers; no live generation or live project mutation is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TEXT_PROOF_PATH = REPO_ROOT / "scripts/proofs/astrid_intro_text_bindings.py"
DEFAULT_SOURCE_ROOT = Path(
    "/Users/peteromalley/Documents/reigh-workspace/Astrid/projects/.astrid-intro-kernel"
)
DEFAULT_SOURCE_PROJECT = Path(
    "/Users/peteromalley/Documents/reigh-workspace/Astrid/projects/astrid-intro"
)
DEFAULT_STORYBOARD = REPO_ROOT / "storyboards/astrid-intro.storyboard.json"
DEFAULT_PROOF_ROOT = Path(
    "/Volumes/ASTRID_RAM/generation-render-bridge-20260901/proof"
)
DEFAULT_EVIDENCE = Path(
    "/Volumes/ASTRID_RAM/generation-render-bridge-20260901/evidence"
)
DESIGN_SOURCE = DEFAULT_SOURCE_PROJECT / "generation-render-bridge.md"
DESIGN_CANONICAL = REPO_ROOT / "docs/generation/generation-render-bridge.md"
DESIGN_SHA256 = "aac23cc0a47d3dded05b5e0fb8fc3d30fdfc15119fa583e4ffd318dc6afe5639"
PROJECT = "astrid-intro"
TARGET_SECTION = "two_ideas"
TARGET_SEQUENCE = 1
PROOF_SCHEMA = "astrid.intro.generation-render-bridge-proof/v1"
PROXY_RECIPE = "astrid-intro-numbered-video-proxy/v1"


def _load_text_proof() -> Any:
    spec = importlib.util.spec_from_file_location("astrid_intro_text_proof", TEXT_PROOF_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load accepted text proof helpers")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unwrap(result: Any, operation: str) -> Any:
    if result.ok:
        return result.data
    error = result.error
    raise RuntimeError(
        f"{operation} failed: {getattr(error, 'code', 'unknown')}: "
        f"{getattr(error, 'message', error)}"
    )


def _role_items(shot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in shot.get("items", []):
        role = (item.get("metadata") or {}).get("role")
        if role:
            result[role] = item
    return result


def _install_deterministic_backend() -> None:
    from astrid.core.generation.backends.registry import GenerationBackendRegistry
    from astrid.core.pack.entrypoint import canonical_runtime_entrypoint
    from tests.v10.test_generation_roundtrip import (
        DeterministicImageBackend,
        _deterministic_registry,
        _FrozenDatetime,
    )

    # The accepted test fixture is the canonical no-network generator.  Patch
    # only the pack loader/clock at the sanctioned runtime boundary.
    with canonical_runtime_entrypoint("generation.generate_image"):
        from astrid.packs.generation.executors.generate_image import run as run_module

        registry: GenerationBackendRegistry = _deterministic_registry(
            DeterministicImageBackend
        )
        run_module.load_default_generation_backend_registry = lambda: registry
        run_module.datetime = _FrozenDatetime


def _media(client: Any, media_id: str) -> dict[str, Any]:
    return _unwrap(client.media.show(PROJECT, media_id), f"show media {media_id}")


def _locator(media: dict[str, Any]) -> Path:
    locations = [
        row for row in media.get("locations", []) if row.get("realm") == "managed_local"
    ]
    if len(locations) != 1:
        raise RuntimeError(f"media {media.get('id')} lacks one managed locator")
    return Path(str(locations[0]["locator"]))


def _snapshot_with_design(
    text: Any,
    *,
    proof_root: Path,
    source_root: Path,
    source_project: Path,
    storyboard: Path,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    if not DESIGN_SOURCE.is_file() or DESIGN_SOURCE.is_symlink():
        raise RuntimeError(f"live design source is unavailable: {DESIGN_SOURCE}")
    if not DESIGN_CANONICAL.is_file() or _sha256(DESIGN_CANONICAL) != DESIGN_SHA256:
        raise RuntimeError("tracked canonical design copy has the wrong SHA-256")
    design_before = text._facts(DESIGN_SOURCE)
    isolated, custody, info = text._snapshot(
        proof_root=proof_root,
        source_root=source_root,
        source_project=source_project,
        storyboard=storyboard,
    )
    design_after_snapshot = text._facts(DESIGN_SOURCE)
    if design_before != design_after_snapshot:
        raise RuntimeError("live design source changed during snapshot")
    custody[str(DESIGN_SOURCE)] = design_before
    return isolated, custody, info
def _bridge_authored_input_check(story: dict[str, Any], shots: list[dict[str, Any]], info: dict[str, Any]) -> None:
    """Apply the accepted bootstrap checks to the current 26-segment plan."""
    if len(story.get("sections", [])) != 25:
        raise RuntimeError("storyboard must contain exactly 25 sections")
    variants = [variant for section in story["sections"] for variant in section["image"]["variants"]]
    if len(variants) != 51:
        raise RuntimeError(f"expected 51 image variants, got {len(variants)}")
    plan = json.loads(Path(info["plan"]).read_text(encoding="utf-8"))
    segment_ids = {str(row["slug"]) for row in plan.get("segments", [])}
    section_ids = {str(section["id"]) for section in story["sections"]}
    if not section_ids <= segment_ids:
        raise RuntimeError("plan does not cover the storyboard sections")
    slides = json.loads(Path(info["compatibility"][0]).read_text(encoding="utf-8"))
    slide_ids = {str(row["slug"]) for row in slides.get("slides", [])}
    if slide_ids != section_ids:
        raise RuntimeError("slides compatibility manifest does not cover the storyboard")
    if len(shots) != 25 or {str(shot["metadata"].get("section_id")) for shot in shots} != section_ids:
        raise RuntimeError("shot closure does not map one-to-one through section_id")
    for shot in shots:
        roles = _role_items(shot)
        if "primary_visual" not in roles or "voiceover" not in roles:
            raise RuntimeError(f"shot {shot['id']} lacks canonical visual/voiceover roles")



def _ordered_shots(client: Any, text: Any) -> list[dict[str, Any]]:
    rows = _unwrap(client.shots.list(PROJECT), "list Intro shots")
    shots = [_unwrap(client.shots.show(PROJECT, row["id"]), "show Intro shot") for row in rows]
    shots.sort(key=lambda shot: int(shot["metadata"]["sequence"]))
    for shot in shots:
        shot["_media"] = {
            item["media_id"]: _media(client, item["media_id"])
            for item in shot.get("items", [])
        }
    return shots
def _timeline_ready(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hide candidate/history visuals from the accepted timeline helper."""
    ready = []
    for shot in shots:
        copy = dict(shot)
        primary_items = [
            item for item in shot["items"] if item["metadata"].get("role") == "primary_visual"
        ]
        active = next(
            (item for item in primary_items if item["metadata"].get("status") == "primary"),
            next((item for item in primary_items if item["metadata"].get("status") not in {"candidate", "superseded"}), primary_items[0] if primary_items else None),
        )
        copy["items"] = [
            item
            for item in shot["items"]
            if item not in primary_items or item is active
        ]
        ready.append(copy)
    return ready



def _generation_recipe(
    client: Any,
    bindings: dict[str, Any],
    shots: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    target = next(shot for shot in shots if shot["metadata"]["section_id"] == TARGET_SECTION)
    previous = shots[TARGET_SEQUENCE - 1]
    following = shots[TARGET_SEQUENCE + 1]
    prompt = next(
        binding
        for binding in bindings["bindings"]
        if binding["kind"] == "prompt" and binding["shot_id"] == target["id"] and binding["slot"] is None
    )
    target_roles = _role_items(target)
    previous_roles = _role_items(previous)
    following_roles = _role_items(following)
    reference_media = [
        _media(client, previous_roles["primary_visual"]["media_id"]),
        _media(client, following_roles["primary_visual"]["media_id"]),
    ]
    recipe = {
        "schema": "astrid.shot-generation-recipe/v1",
        "project_id": target["project_id"],
        "shot_id": target["id"],
        "target_role": "primary_visual",
        "prompt_binding": {
            "id": prompt["binding_id"],
            "head": prompt["head"],
            "media_id": prompt["media_id"],
            "content_sha256": prompt["content_hash"],
        },
        "generator": {
            "capability_id": "generation.generate_image",
            "model": "z-image",
            "backend": "local",
            "mode": "t2i",
            "settings": {"seed": 20260901},
        },
        "inputs": [
            {
                "ordinal": ordinal,
                "role": role,
                "reference_id": f"intro-reference-{role}",
                "media_id": media["id"],
                "content_sha256": media["content_hash"],
            }
            for ordinal, (role, media) in enumerate(
                zip(("previous_shot", "next_shot"), reference_media, strict=True)
            )
        ],
        "parent_media_id": previous_roles["primary_visual"]["media_id"],
        "parent_content_sha256": previous_roles["primary_visual"]["metadata"]["content_sha256"],
    }
    return recipe, target, target_roles


def _run_generation(client: Any, isolated_root: Path, recipe: dict[str, Any], prompt: str) -> dict[str, Any]:
    from astrid.core.ids import generate_lowercase_ulid
    from astrid.core.store.uow import UnitOfWork
    from astrid.core.task_executor import ExecutionService
    from astrid.packs.generation.executors.generate_image.task_adapter import GenerateImageAdapter

    project = _unwrap(client.projects.show(PROJECT), "show Intro project")
    project_id = project["id"]
    run_id = generate_lowercase_ulid()
    spec = {
        "model": "z-image",
        "mode": "t2i",
        "execution": "local",
        "prompt": prompt,
        "count": 2,
        "seed": 20260901,
        "shot_generation_recipe": recipe,
    }
    fanout = UnitOfWork(client.app.writer).run(
        lambda uow: client.app.runs.create(
            uow,
            project_id=project_id,
            run_id=run_id,
            kind="generation",
            title="Astrid Intro shot 02 candidates",
            input={"shot_id": recipe["shot_id"], "target_role": "primary_visual"},
            children=[
                {
                    "capability": "generation.generate_image",
                    "spec": spec,
                    "input_manifest": [],
                    "max_attempts": 1,
                }
            ],
            idempotency_key="intro-bridge:generation-admission",
            created_at="2026-09-01T00:00:00.000000+00:00",
        ),
    )
    task_id = fanout.task_ids[0]
    claim = UnitOfWork(client.app.writer).run(
        lambda uow: client.app.tasks.claim(
            uow,
            project_id=project_id,
            executor_id="astrid-intro-bridge-proof",
            idempotency_key="intro-bridge:generation-claim",
            now="2026-09-01T00:01:00.000000+00:00",
        )
    )
    if claim is None or claim.task.id != task_id:
        raise RuntimeError("generation task was not claimed")
    executor = ExecutionService(projects_root=isolated_root, task_repo=client.app.tasks)
    execution = executor.execute(
        UnitOfWork(client.app.writer),
        project_id=project_id,
        task_id=task_id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=claim.attempt.status_version,
        idempotency_key="intro-bridge:generation-execute",
        handler=GenerateImageAdapter(projects_root=isolated_root),
        now="2026-09-01T00:02:00.000000+00:00",
    )
    if execution.outcome != "prepared" or execution.prepared is None:
        raise RuntimeError(f"generation execution did not prepare: {execution.outcome}")
    completion = executor.complete(
        UnitOfWork(client.app.writer),
        prepared=execution.prepared,
        media_repo=client.app.media,
        idempotency_key="intro-bridge:generation-complete",
        now="2026-09-01T00:03:00.000000+00:00",
    )
    if completion.outcome != "completed" or completion.completed is None:
        raise RuntimeError(f"generation completion failed: {completion.outcome}")
    outputs = [
        output
        for output in completion.completed.outputs
        if output.role == "output" and output.media_id is not None
    ]
    if len(outputs) != 2:
        raise RuntimeError(f"expected two candidate outputs, got {len(outputs)}")
    return {
        "run_id": run_id,
        "task_id": task_id,
        "spec": spec,
        "outputs": [
            {
                "ordinal": output.ordinal,
                "media_id": output.media_id,
                "content_hash": dict(output.params).get("content_hash"),
                "label": dict(output.params).get("label"),
            }
            for output in outputs
        ],
    }


def _attach_candidates(client: Any, generation: dict[str, Any], recipe: dict[str, Any], target: dict[str, Any]) -> None:
    references = recipe["inputs"]
    prompt = recipe["prompt_binding"]
    relations = []
    for candidate in generation["outputs"]:
        relations.extend(
            [
                {
                    "from_media_id": candidate["media_id"],
                    "to_media_id": prompt["media_id"],
                    "kind": "uses_as_input",
                    "ordinal": 0,
                    "metadata": {
                        "binding_id": prompt["id"],
                        "binding_head": prompt["head"],
                        "content_sha256": prompt["content_sha256"],
                    },
                },
                *[
                    {
                        "from_media_id": candidate["media_id"],
                        "to_media_id": reference["media_id"],
                        "kind": "uses_as_input",
                        "ordinal": reference["ordinal"] + 1,
                        "metadata": {
                            "role": reference["role"],
                            "reference_id": reference["reference_id"],
                            "content_sha256": reference["content_sha256"],
                        },
                    }
                    for reference in references
                ],
                {
                    "from_media_id": candidate["media_id"],
                    "to_media_id": recipe["parent_media_id"],
                    "kind": "variant_of",
                    "ordinal": 0,
                    "metadata": {"content_sha256": recipe["parent_content_sha256"]},
                },
            ]
        )
    _unwrap(client.media.relate(PROJECT, relations=relations, idempotency_key="intro-bridge:candidate-relations"), "relate candidates")
    for output in generation["outputs"]:
        result = _unwrap(
            client.shots.add_item(
                PROJECT,
                target["id"],
                media_id=output["media_id"],
                metadata={
                    "role": "primary_visual",
                    "status": "candidate",
                    "run_id": generation["run_id"],
                    "task_id": generation["task_id"],
                    "recipe": recipe,
                    "content_sha256": _media(client, output["media_id"])["content_hash"],
                },
                idempotency_key=f"intro-bridge:candidate-item:{output['ordinal']}",
            ),
            "attach candidate",
        )
        if result["item"]["media_id"] != output["media_id"]:
            raise RuntimeError("candidate item points at the wrong output media")



def _render_result(client: Any, timeline_ref: str, expected_version: int, output_path: Path) -> dict[str, Any]:
    import re

    result = client.invoke_result(
        "rendering.render",
        kind="executor",
        project=PROJECT,
        inputs={"timeline_ref": timeline_ref, "expected_version": expected_version, "backend": "ffmpeg"},
    )
    if not result.ok:
        raise RuntimeError(f"managed render failed: {result.error}")
    artifacts = [a for a in (result.outputs.get("artifacts") or []) if isinstance(a, dict)]
    result_artifacts = [a for a in artifacts if a.get("role") == "result"]
    provenance_artifacts = [a for a in artifacts if str(a.get("label", "")).endswith(".provenance.json")]
    if len(result_artifacts) != 1 or len(provenance_artifacts) != 1:
        raise RuntimeError("managed render did not expose result and provenance artifacts")
    artifact = dict(result_artifacts[0])
    digest = str(artifact.get("content_hash", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise RuntimeError("render result is not a lowercase SHA-256")
    managed = Path(str(artifact.get("path") or artifact.get("locator") or ""))
    if not managed.is_file() or _sha256(managed) != digest:
        raise RuntimeError("managed render bytes do not match result hash")
    provenance = dict(provenance_artifacts[0])
    provenance_path = Path(str(provenance.get("path") or provenance.get("locator") or ""))
    if not provenance_path.is_file():
        raise RuntimeError("render provenance artifact is missing")
    provenance_json = json.loads(provenance_path.read_text(encoding="utf-8"))
    if int(provenance_json.get("canonical_timeline", {}).get("config_version", -1)) != expected_version:
        raise RuntimeError("provenance does not pin the saved timeline version")
    probe = json.loads(_run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(managed)]))
    streams = probe.get("streams", [])
    if not any(s.get("codec_type") == "video" and s.get("codec_name") == "h264" for s in streams):
        raise RuntimeError("render lacks h264 video")
    if not any(s.get("codec_type") == "audio" and s.get("codec_name") == "aac" for s in streams):
        raise RuntimeError("render lacks aac audio")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(managed, output_path)
    if _sha256(output_path) != digest:
        raise RuntimeError("review MP4 copy changed managed render bytes")
    return {
        "artifact": artifact,
        "provenance_artifact": provenance,
        "managed_path": str(managed),
        "review_path": str(output_path),
        "output_sha256": digest,
        "provenance": provenance_json,
        "probe": probe,
        "streams": [{"codec_type": s.get("codec_type"), "codec_name": s.get("codec_name"), "channels": s.get("channels"), "sample_rate": s.get("sample_rate")} for s in streams],
    }


def _run(command: list[str]) -> str:
    import subprocess

    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def _proof(args: argparse.Namespace) -> dict[str, Any]:
    text = _load_text_proof()
    proof_root = Path(args.proof_root or DEFAULT_PROOF_ROOT)
    evidence = Path(args.evidence_dir or DEFAULT_EVIDENCE)
    if proof_root.exists():
        shutil.rmtree(proof_root)
    proof_root.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    storyboard = Path(args.storyboard or DEFAULT_STORYBOARD)
    isolated_root, custody_before, info = _snapshot_with_design(
        text,
        proof_root=proof_root,
        source_root=Path(args.source_root or DEFAULT_SOURCE_ROOT),
        source_project=Path(args.source_project or DEFAULT_SOURCE_PROJECT),
        storyboard=storyboard,
    )
    os.environ["ASTRID_PROOF_HOME"] = str(proof_root / "home")
    shutil.rmtree(proof_root / "home", ignore_errors=True)
    _json_write(evidence / "custody-before.json", custody_before)
    copied_story = json.loads(Path(info["storyboard"]).read_text(encoding="utf-8"))
    _json_write(proof_root / "storyboard.json", copied_story)
    _install_deterministic_backend()

    from astrid.sdk.client import AstridClient

    with AstridClient.open(isolated_root) as client:
        shots = _ordered_shots(client, text)
        original_wavs = {
            shot["id"]: _media(client, _role_items(shot)["voiceover"]["media_id"])["content_hash"]
            for shot in shots
        }
        original_check = text._crosscheck_authored_inputs
        text._crosscheck_authored_inputs = _bridge_authored_input_check
        try:
            bindings = text._bootstrap(client, copied_story, shots, evidence, info)
        finally:
            text._crosscheck_authored_inputs = original_check
        target_seed = next(shot for shot in shots if shot["metadata"]["section_id"] == TARGET_SECTION)
        legacy_primary = next(item for item in target_seed["items"] if item["metadata"].get("role") == "primary_visual")
        if legacy_primary["metadata"].get("status") != "primary":
            baseline_meta = dict(legacy_primary["metadata"])
            baseline_meta["status"] = "primary"
            _unwrap(client.shots.add_item(PROJECT, target_seed["id"], media_id=legacy_primary["media_id"], metadata=baseline_meta, idempotency_key="intro-bridge:baseline-primary"), "seed statusful primary")
            _unwrap(client.shots.remove_item(PROJECT, target_seed["id"], legacy_primary["id"], idempotency_key="intro-bridge:remove-legacy-primary"), "remove legacy primary")
            shots = _ordered_shots(client, text)
        recipe, target, target_roles = _generation_recipe(client, bindings, shots)
        target_prompt = next(
            binding for binding in bindings["bindings"] if binding["binding_id"] == recipe["prompt_binding"]["id"]
        )
        prompt_text = text._text_for_binding(client, target_prompt)
        generation = _run_generation(client, isolated_root, recipe, prompt_text)
        _json_write(
            evidence / "admission.json",
            {"run_id": generation["run_id"], "task_id": generation["task_id"], "spec": generation["spec"], "recipe": recipe, "output_count": len(generation["outputs"])},
        )
        _attach_candidates(client, generation, recipe, target)
        before = _unwrap(client.shots.show(PROJECT, target["id"]), "read candidates before promotion")
        primary_before = next(item for item in before["items"] if item["metadata"].get("role") == "primary_visual" and item["metadata"].get("status") == "primary")
        candidates_before = [item for item in before["items"] if item["metadata"].get("status") == "candidate"]
        if len(candidates_before) != 2:
            raise RuntimeError("candidate attachment changed the candidate count unexpectedly")
        _json_write(evidence / "candidate-before-promotion.json", {"shot_id": target["id"], "primary_item_id": primary_before["id"], "primary_media_id": primary_before["media_id"], "candidates": candidates_before, "event_head_seq": before["event_head_seq"]})

        task_read = _unwrap(client.tasks.show(generation["task_id"], project_id=PROJECT), "public task read")
        run_read = _unwrap(client.runs.show(PROJECT, generation["run_id"], include_evidence=True), "public run read")
        media_reads = [_media(client, output["media_id"]) for output in generation["outputs"]]
        _json_write(evidence / "public-read-trace.json", {"task": task_read, "run": run_read, "media": media_reads, "shot": before})
        if task_read["spec"] != generation["spec"] or not run_read["child_outputs"]:
            raise RuntimeError("public reads did not expose frozen generation context")

        legacy_plate = target_roles["render_plate"]
        old_plate = _unwrap(
            client.shots.add_item(
                PROJECT,
                target["id"],
                media_id=legacy_plate["media_id"],
                metadata={
                    "role": "plate",
                    "kind": "plate",
                    "recipe": "astrid-intro-captioned-plate/v1",
                    "source_item_id": primary_before["id"],
                    "source_media_id": primary_before["media_id"],
                    "source_content_sha256": primary_before["metadata"]["content_sha256"],
                    "content_sha256": legacy_plate["metadata"]["content_sha256"],
                },
                idempotency_key="intro-bridge:old-plate-seed",
            ),
            "seed stale plate",
        )
        old_plate = old_plate["item"]
        # This proof-only proxy has the generic dependency vocabulary consumed by
        # the pure analyzer while the Intro's existing feedback role stays intact.
        old_proxy = _unwrap(
            client.shots.add_item(
                PROJECT,
                target["id"],
                media_id=old_plate["media_id"],
                metadata={
                    "role": "proxy",
                    "kind": "proxy",
                    "recipe": PROXY_RECIPE,
                    "shot_number": 2,
                    "source_item_id": old_plate["id"],
                    "source_media_id": old_plate["media_id"],
                    "source_content_sha256": old_plate["metadata"]["content_sha256"],
                },
                idempotency_key="intro-bridge:old-proxy-seed",
            ),
            "seed old review proxy",
        )
        next_roles = _role_items(shots[TARGET_SEQUENCE + 1])
        transition = _unwrap(
            client.shots.add_item(
                PROJECT,
                target["id"],
                media_id=target_roles.get("incoming_transition", target_roles["render_plate"])["media_id"],
                metadata={
                    "kind": "generative_transition",
                    "from_media_id": primary_before["media_id"],
                    "from_content_sha256": primary_before["metadata"]["content_sha256"],
                    "to_media_id": next_roles["primary_visual"]["media_id"],
                    "to_content_sha256": next_roles["primary_visual"]["metadata"]["content_sha256"],
                },
                idempotency_key="intro-bridge:stale-transition-seed",
            ),
            "seed stale transition",
        )

        interrupted = {"stage": "candidates-attached-before-promotion", "run_id": generation["run_id"], "task_id": generation["task_id"], "candidate_item_ids": [item["id"] for item in candidates_before]}
        _json_write(proof_root / "interrupted-resume.json", interrupted)

    # Reopen after the intentional interruption. All lineage below comes from
    # public task/run/media/shot reads, never from the source or a direct query.
    with AstridClient.open(isolated_root) as client:
        resumed_task = _unwrap(client.tasks.show(generation["task_id"], project_id=PROJECT), "resume task")
        resumed_run = _unwrap(client.runs.show(PROJECT, generation["run_id"], include_evidence=True), "resume run")
        resumed_shot = _unwrap(client.shots.show(PROJECT, target["id"]), "resume shot")
        if resumed_task["id"] != generation["task_id"] or not resumed_run["child_outputs"]:
            raise RuntimeError("reopen lost generation lineage")
        timeline_assets = [{"id": "timeline-shot-02", "metadata": {"source_item_id": primary_before["id"], "source_media_id": primary_before["media_id"], "source_content_sha256": primary_before["metadata"]["content_sha256"]}}]
        promoted = _unwrap(client.shots.promote_candidate(PROJECT, target["id"], candidates_before[0]["id"], expected_head_seq=resumed_shot["event_head_seq"], timeline_assets=timeline_assets, idempotency_key="intro-bridge:promote-shot-02"), "promote candidate")
        _json_write(evidence / "promotion.json", promoted)
        _json_write(evidence / "invalidation.json", promoted["invalidation"])
        stale_ids = {entry.get("item_id") or entry.get("asset_id") for entry in promoted["invalidation"]["stale"]}
        blocked_ids = {entry.get("item_id") for entry in promoted["invalidation"]["blocked_on_generation"]}
        if old_plate["id"] not in stale_ids or old_proxy["item"]["id"] not in stale_ids or "timeline-shot-02" not in stale_ids or transition["item"]["id"] not in blocked_ids:
            raise RuntimeError(f"invalidation omitted required dependencies: {promoted['invalidation']}")
        replay = _unwrap(client.shots.promote_candidate(PROJECT, target["id"], candidates_before[0]["id"], expected_head_seq=resumed_shot["event_head_seq"], timeline_assets=timeline_assets, idempotency_key="intro-bridge:promote-shot-02"), "replay promotion")
        if replay != promoted:
            raise RuntimeError("promotion replay was not byte-identical")

        all_shots = _ordered_shots(client, text)
        target_after = next(shot for shot in all_shots if shot["id"] == target["id"])
        active_visual = next(item for item in target_after["items"] if item["metadata"].get("role") == "primary_visual" and item["metadata"].get("status") == "primary")
        if active_visual["media_id"] != candidates_before[0]["media_id"]:
            raise RuntimeError("promotion did not install the selected candidate")
        if not any(item["id"] == primary_before["id"] and item["metadata"].get("status") == "superseded" for item in target_after["items"]):
            raise RuntimeError("promotion did not retain the old primary")

        builder = text._load_helpers(proof_root, info)
        ranges = builder._shot_frame_ranges(all_shots, builder._canvas(copied_story)[2])
        start, end = ranges[target["id"]]
        edited_plates = proof_root / "refreshed-plates"
        new_plate_path = edited_plates / "two_ideas.mp4"
        caption_path = edited_plates / "two_ideas.caption.txt"
        binding = next(b for b in bindings["bindings"] if b["kind"] == "transcript" and b["shot_id"] == target["id"])
        builder._render_plate(source=_locator(_media(client, active_visual["media_id"])), caption=text._text_for_binding(client, binding), output=new_plate_path, caption_file=caption_path, width=builder._canvas(copied_story)[0], height=builder._canvas(copied_story)[1], fps=builder._canvas(copied_story)[2], frame_count=end - start)
        new_plate = _media(client, _unwrap(client.media.import_file(project=PROJECT, path=new_plate_path, idempotency_key="intro-bridge:refresh-plate-import"), "import refreshed plate")["id"])
        new_plate_item = _unwrap(client.shots.add_item(PROJECT, target["id"], media_id=new_plate["id"], position=2, metadata={"role": "render_plate", "recipe": "astrid-intro-captioned-plate/v1", "content_sha256": new_plate["content_hash"], "source_item_id": active_visual["id"], "source_media_id": active_visual["media_id"], "source_content_sha256": active_visual["metadata"]["content_sha256"]}, idempotency_key="intro-bridge:refresh-plate-item"), "attach refreshed plate")
        _unwrap(client.media.relate(PROJECT, relations=[{"from_media_id": new_plate["id"], "to_media_id": active_visual["media_id"], "kind": "derived_from", "ordinal": 0, "metadata": {"role": "captioned_render_plate", "recipe": "astrid-intro-captioned-plate/v1"}}], idempotency_key="intro-bridge:refresh-plate-lineage"), "relate refreshed plate")
        _unwrap(client.shots.remove_item(PROJECT, target["id"], legacy_plate["id"], idempotency_key="intro-bridge:remove-legacy-plate"), "remove legacy plate")
        _unwrap(client.shots.remove_item(PROJECT, target["id"], old_plate["id"], idempotency_key="intro-bridge:remove-old-plate"), "remove stale plate")

        new_proxy_path = proof_root / "review-proxies" / "two_ideas-review-numbered.mp4"
        builder._render_numbered_video_proxy(source=_locator(new_plate), output=new_proxy_path, width=builder._canvas(copied_story)[0], height=builder._canvas(copied_story)[1], fps=builder._canvas(copied_story)[2], frame_count=end - start, shot_label="SHOT 02")
        new_proxy = _media(client, _unwrap(client.media.import_file(project=PROJECT, path=new_proxy_path, idempotency_key="intro-bridge:refresh-proxy-import"), "import refreshed proxy")["id"])
        new_proxy_item = _unwrap(client.shots.add_item(PROJECT, target["id"], media_id=new_proxy["id"], metadata={"role": "proxy", "kind": "proxy", "recipe": PROXY_RECIPE, "shot_number": 2, "shot_label": "SHOT 02", "content_sha256": new_proxy["content_hash"], "source_item_id": new_plate_item["item"]["id"], "source_media_id": new_plate["id"], "source_content_sha256": new_plate["content_hash"]}, idempotency_key="intro-bridge:refresh-proxy-item"), "attach refreshed proxy")
        _unwrap(client.shots.remove_item(PROJECT, target["id"], old_proxy["item"]["id"], idempotency_key="intro-bridge:remove-old-proxy"), "remove stale proxy")
        _unwrap(client.media.relate(PROJECT, relations=[{"from_media_id": new_proxy["id"], "to_media_id": new_plate["id"], "kind": "derived_from", "ordinal": 0, "metadata": {"role": "shot_feedback_proxy", "recipe": PROXY_RECIPE}}], idempotency_key="intro-bridge:refresh-proxy-lineage"), "relate refreshed proxy")
        transition_after = next(item for item in _unwrap(client.shots.show(PROJECT, target["id"]), "read transition after refresh")["items"] if item["id"] == transition["item"]["id"])
        if {
            key: transition_after.get(key)
            for key in ("id", "media_id", "metadata")
        } != {
            key: transition["item"].get(key)
            for key in ("id", "media_id", "metadata")
        }:
            raise RuntimeError("refresh mutated the blocked generative transition")
        _json_write(evidence / "refresh.json", {"affected_shot_id": target["id"], "plate": {"before_item_id": old_plate["id"], "after_item_id": new_plate_item["item"]["id"], "before_media_id": old_plate["media_id"], "after_media_id": new_plate["id"], "rebuilt": True}, "proxy": {"before_item_id": old_proxy["item"]["id"], "after_item_id": new_proxy_item["item"]["id"], "before_media_id": old_proxy["item"]["media_id"], "after_media_id": new_proxy["id"], "rebuilt": True}, "rebuild_counts": {"plates": 1, "numbered_review_proxies": 1}, "unchanged": {"generative_transition_item_id": transition["item"]["id"], "generative_transition_unchanged": True}, "selected_candidate": {"item_id": active_visual["id"], "media_id": active_visual["media_id"], "content_sha256": active_visual["metadata"]["content_sha256"]}})

        current_shots = _ordered_shots(client, text)
        old_plate_by_shot = {shot["id"]: _media(client, _role_items(shot)["render_plate"]["media_id"]) for shot in current_shots[1:]}
        baseline_config, baseline_registry = text._timeline(shots, copied_story, output_name="intro-generation-bridge-baseline.mp4", plate_by_shot={shot["id"]: _media(client, _role_items(shot)["render_plate"]["media_id"]) for shot in shots[1:]})
        timeline_slug = "intro-generation-render-bridge"
        created = _unwrap(client.timelines.create(project=PROJECT, slug=timeline_slug, name="Astrid Intro generation render bridge", config=baseline_config, registry=baseline_registry, idempotency_key="intro-bridge:timeline-create"), "create bridge timeline")
        final_config, final_registry = text._timeline(_timeline_ready(current_shots), copied_story, output_name="astrid-intro-generation-render-bridge-review.mp4", plate_by_shot=old_plate_by_shot)
        target_asset = final_registry["assets"][f"plate_{TARGET_SECTION}"]
        target_asset.update({"generationId": active_visual["id"], "variantId": active_visual["media_id"]})
        saved = _unwrap(client.timelines.save(PROJECT, timeline_slug, config=final_config, registry=final_registry, expected_version=created["config_version"], idempotency_key="intro-bridge:timeline-save-promoted"), "save promoted timeline")
        if saved["config_version"] != created["config_version"] + 1:
            raise RuntimeError("timeline save did not advance exactly one version")
        rendered = _render_result(client, timeline_slug, saved["config_version"], proof_root / "render" / "astrid-intro-generation-render-bridge-review.mp4")
        if rendered["provenance"].get("canonical_timeline", {}).get("config_version") != saved["config_version"]:
            raise RuntimeError("render provenance is not pinned to saved timeline version")
        _json_write(evidence / "timeline-render.json", {"timeline": {"slug": timeline_slug, "created_version": created["config_version"], "saved_version": saved["config_version"], "save": saved}, "selected_candidate": {"item_id": active_visual["id"], "media_id": active_visual["media_id"], "content_sha256": active_visual["metadata"]["content_sha256"]}, "render": rendered})

        final_shots = _ordered_shots(client, text)
        final_wavs = {shot["id"]: _media(client, _role_items(shot)["voiceover"]["media_id"])["content_hash"] for shot in final_shots}
        if final_wavs != original_wavs:
            raise RuntimeError("voiceover identities changed during generation bridge proof")
        custody_after = {path: text._facts(Path(path)) for path in custody_before}
        if custody_after != custody_before:
            raise RuntimeError("live custody changed during isolated generation bridge proof")
        _json_write(evidence / "custody-after.json", custody_after)
        proof = {"schema": PROOF_SCHEMA, "project": PROJECT, "proof_root": str(proof_root), "evidence_dir": str(evidence), "criteria": {"C1": True, "C2": True, "C3": True, "C4": True, "C5": True, "C6": True, "C7": True, "C8": True}, "admission": {"run_id": generation["run_id"], "task_id": generation["task_id"], "candidate_count": 2}, "promotion": {"selected_candidate_item_id": active_visual["id"], "selected_candidate_media_id": active_visual["media_id"], "old_primary_item_id": primary_before["id"], "replay_identical": True}, "invalidation": promoted["invalidation"], "refresh": {"plates_rebuilt": 1, "numbered_review_proxies_rebuilt": 1, "generative_transition": "blocked_on_generation", "transition_unchanged": True}, "timeline": {"slug": timeline_slug, "version": saved["config_version"], "selected_candidate_content_sha256": active_visual["metadata"]["content_sha256"]}, "render": rendered, "custody_equal": True, "voiceover_identity_preserved": True, "review_mp4": str(proof_root / "render/astrid-intro-generation-render-bridge-review.mp4")}
        _json_write(evidence / "intro-proof.json", proof)
        artifact_hashes = {"design_source_sha256": _sha256(DESIGN_SOURCE), "design_canonical_sha256": _sha256(DESIGN_CANONICAL), "intro-proof": _sha256(evidence / "intro-proof.json"), "evidence": {path.name: _sha256(path) for path in sorted(evidence.glob("*.json")) if path.name != "artifact-hashes.json"}}
        _json_write(evidence / "artifact-hashes.json", artifact_hashes)
        return proof


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof-root", default=os.environ.get("PROOF_ROOT"))
    parser.add_argument("--evidence-dir", default=os.environ.get("EVIDENCE_DIR"))
    parser.add_argument("--source-root", default=os.environ.get("INTRO_SOURCE_ROOT"))
    parser.add_argument("--source-project", default=os.environ.get("INTRO_SOURCE_PROJECT"))
    parser.add_argument("--storyboard", default=os.environ.get("STORYBOARD"))
    args = parser.parse_args(argv)
    print(json.dumps(_proof(args), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
