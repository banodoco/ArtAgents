"""Attested-command parsing, identity validation, and iterate-feedback I/O."""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from typing import Literal

from astrid.core.project.sidecar import write_json_sidecar
from astrid.core.task.env import is_author_test_mode, task_actor_env
from astrid.core.task.gate_base import ITERATE_FEEDBACK_PREFIX, GateDecision, _reject
from astrid.core.task.plan import Step, step_dir_for_path


@dataclass(frozen=True)
class AttestedArgs:
    agent: str | None
    evidence: tuple[str, ...] = ()
    item: str | None = None
    human: str | None = None


def _extract_iterate_feedback(evidence: tuple[str, ...]) -> str | None:
    for item in evidence:
        if item.startswith(ITERATE_FEEDBACK_PREFIX):
            return item[len(ITERATE_FEEDBACK_PREFIX):]
    return None


def write_iteration_feedback(decision: GateDecision, feedback: str) -> None:
    if (
        decision.slug is None
        or decision.run_id is None
        or decision.iteration is None
        or decision.project_root is None
        or not decision.plan_step_path
    ):
        return
    iter_dir = step_dir_for_path(
        decision.slug,
        decision.run_id,
        decision.plan_step_path,
        step_version=decision.step_version,
        iteration=decision.iteration,
        root=decision.project_root.parent,
    )
    iter_dir.mkdir(parents=True, exist_ok=True)
    feedback_path = iter_dir / "feedback.json"
    cumulative: list[str] = []
    if decision.iteration > 1:
        prev_dir = step_dir_for_path(
            decision.slug,
            decision.run_id,
            decision.plan_step_path,
            step_version=decision.step_version,
            iteration=decision.iteration - 1,
            root=decision.project_root.parent,
        )
        prev_path = prev_dir / "feedback.json"
        if prev_path.exists():
            try:
                prev = json.loads(prev_path.read_text(encoding="utf-8"))
                if isinstance(prev, list):
                    cumulative = [str(x) for x in prev]
            except (json.JSONDecodeError, OSError):
                cumulative = []
    cumulative.append(feedback)
    write_json_sidecar(feedback_path, cumulative)


def match_attested_command(incoming: str, expected_prefix: str) -> tuple[bool, AttestedArgs]:
    """Strip identity/evidence/item tokens and compare the canonical remainder.
    """
    try:
        tokens = shlex.split(incoming)
    except ValueError:
        return False, AttestedArgs(agent=None)
    agent: str | None = None
    human: str | None = None
    item: str | None = None
    evidence: list[str] = []
    remaining: list[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "--agent" and i + 1 < len(tokens):
            agent = tokens[i + 1]
            i += 2
            continue
        if token == "--human" and i + 1 < len(tokens):
            human = tokens[i + 1]
            i += 2
            continue
        if token == "--item" and i + 1 < len(tokens):
            item = tokens[i + 1]
            i += 2
            continue
        if token == "--evidence" and i + 1 < len(tokens):
            evidence.append(tokens[i + 1])
            i += 2
            continue
        remaining.append(token)
        i += 1
    try:
        expected_tokens = shlex.split(expected_prefix)
    except ValueError:
        return False, AttestedArgs(
            agent=agent, human=human, evidence=tuple(evidence), item=item
        )
    rejoined = " ".join(shlex.quote(token) for token in remaining)
    expected = " ".join(shlex.quote(token) for token in expected_tokens)
    matched = rejoined == expected
    return matched, AttestedArgs(
        agent=agent, human=human, evidence=tuple(evidence), item=item
    )


def validate_attested_identity(
    *,
    slug: str,
    step: Step,
    args: AttestedArgs,
    run_started_actor: str | None,
) -> tuple[Literal["agent", "human"], str]:
    human = args.human
    supplied = sum(value is not None for value in (args.agent, args.human))
    if supplied == 0:
        _reject(slug, "attested step requires --agent or --human", abort=False)
    if supplied > 1:
        _reject(slug, "attested step rejects multiple identity flags", abort=False)
    if step.ack.kind == "agent":
        if args.agent is None:
            _reject(slug, "attested step ack.kind=agent requires --agent", abort=False)
        return "agent", args.agent
    # ack.kind == "human"; legacy plan ack.kind="actor" is normalized at load time.
    if human is None:
        _reject(slug, "attested step ack.kind=human requires --human", abort=False)
    if is_author_test_mode():
        # Author-test mode: skip ASTRID_ACTOR-match and self-ack checks so the
        # harness can drive attestations under a synthetic human identity.
        return "human", human
    if task_actor_env() != human:
        _reject(slug, "attested --human does not match ASTRID_ACTOR env", abort=False)
    # FLAG-005: self-ack rejection only applies to human attestations because agents
    # do not start runs in V1; an agent_id on run_started would be required to
    # symmetrically block agent self-acks, which is out of scope for Phase 2.
    if (
        run_started_actor is not None
        and run_started_actor == human
        and task_actor_env() == human
    ):
        _reject(slug, "self-ack rejected", abort=False)
    return "human", human
