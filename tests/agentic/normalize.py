from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"


def _scenario_path(name: str, *, scenarios_dir: Path) -> Path:
    candidate = scenarios_dir / name
    if candidate.suffix != ".yaml":
        candidate = candidate.with_suffix(".yaml")
    return candidate


def discover_scenarios(
    scenario_names: Sequence[str] | None = None,
    *,
    scenarios_dir: Path = SCENARIOS_DIR,
) -> list[Path]:
    """Resolve scenario YAMLs for the Sisypy normalization path.

    With no explicit names, this returns only the 36 production scenarios:
    every ``*.yaml`` file whose basename does not start with ``_``.
    Explicit names preserve caller order and may include underscore fixtures
    such as ``_smoke``.
    """
    if scenario_names:
        resolved: list[Path] = []
        for name in scenario_names:
            path = _scenario_path(name, scenarios_dir=scenarios_dir)
            if not path.is_file():
                raise FileNotFoundError(f"scenario {name!r} not found at {path}")
            resolved.append(path)
        return resolved

    return sorted(
        path
        for path in scenarios_dir.glob("*.yaml")
        if not path.name.startswith("_")
    )


def _normalized_agent_spec(agent_spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    base = deepcopy(dict(agent_spec))
    count = base.pop("count", 1)
    subagent_type = base.pop("subagent_type", None)
    if subagent_type is not None:
        config = deepcopy(base.get("config") or {})
        if not isinstance(config, dict):
            config = {}
        config.setdefault("subagent_type", subagent_type)
        base["config"] = config

    copies = count if isinstance(count, int) and count > 0 else 1
    return [deepcopy(base) for _ in range(copies)]


def normalize_scenario(scenario: Mapping[str, Any]) -> dict[str, Any]:
    """Return a Sisypy-ready scenario dict without dropping legacy keys."""
    normalized = deepcopy(dict(scenario))

    agents = normalized.get("agents")
    if isinstance(agents, list):
        expanded_agents: list[Any] = []
        for agent_spec in agents:
            if isinstance(agent_spec, Mapping):
                expanded_agents.extend(_normalized_agent_spec(agent_spec))
            else:
                expanded_agents.append(deepcopy(agent_spec))
        normalized["agents"] = expanded_agents

    extras = deepcopy(normalized.get("extras") or {})
    if normalized.get("target_orchestrator") is not None:
        extras["target_orchestrator"] = normalized["target_orchestrator"]
    if normalized.get("acceptance") is not None:
        extras["legacy_acceptance"] = deepcopy(normalized["acceptance"])

    assessment = normalized.get("assessment")
    if isinstance(assessment, dict) and "universal_checks" in assessment:
        extras["universal_checks"] = assessment.pop("universal_checks")

    if extras or "extras" in normalized:
        normalized["extras"] = extras

    return normalized
