"""Command-kind census (adherence item 5).

Every command kind declared in the composed standard registry (core +
timeline/shots/references schema packs) must be fully implemented and
exercised. For each declared command kind the census asserts:

(a) a repository method implements it — the owning repository is resolved by
    convention: the core namespace noun maps to the kernel repository
    (projects -> ProjectRepository, tasks -> TaskRepository, runs ->
    RunRepository, media -> MediaRepository, evidence ->
    EvidenceRepository), and pack kinds resolve to the pack's declared
    repository class; the method name is the command verb, with an explicit
    mapping for the documented naming exceptions (``core.run.continue`` ->
    ``continue_run``, ``core.media.import`` -> ``import_prepared``,
    ``core.task.expire`` -> ``expire_overdue``);
(b) an emitted event kind counterpart is declared by the same pack
    (``x.y.z`` -> ``x.y.zed`` with the documented irregular pairs);
(c) at least one other v10 test references the command kind or its event
    kind — a declared-but-unexercised command is a contract gap.

The kind set is read from the frozen composed registry at runtime — never
hardcoded — so the census tracks the registry exactly as shipped, including
kinds a concurrent change is in the middle of declaring. A declared kind
whose method does not exist yet fails with a message naming the missing
method: that is load-bearing, not something to weaken around.
"""

from __future__ import annotations

import importlib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_TESTS_V10 = _ROOT / "tests" / "v10"

# (a) command verb -> repository method for the documented naming exceptions
# (Python keywords and domain names that legitimately differ from the verb).
_METHOD_EXCEPTIONS: dict[str, str] = {
    "core.run.continue": "continue_run",  # `continue` is a Python keyword
    "core.media.import": "import_prepared",  # `import` is a Python keyword
    "core.task.expire": "expire_overdue",  # domain name for the expiry command
}

# Core command namespace noun -> (repository module, repository class name).
# The kernel manifest declares only four repositories, so the evidence noun
# uses the documented convention mapping (adherence-item spec).
_CORE_NAMESPACE_REPOS: dict[str, tuple[str, str]] = {
    "project": ("astrid.core.repositories.projects", "ProjectRepository"),
    "task": ("astrid.core.repositories.tasks", "TaskRepository"),
    "run": ("astrid.core.repositories.runs", "RunRepository"),
    "media": ("astrid.core.repositories.media", "MediaRepository"),
    "evidence": ("astrid.core.repositories.evidence", "EvidenceRepository"),
}

# Schema-pack id -> repository module (the pack's declared repository lives
# in ``astrid/packs/<id>/repository.py``).
_PACK_REPOSITORY_MODULES: dict[str, str] = {
    "timeline": "astrid.packs.timeline.repository",
    "shots": "astrid.packs.shots.repository",
    "references": "astrid.packs.references.repository",
}

# (b) command kind -> event kind for the irregular documented pairs. The
# default rule is ``<prefix>.<verb-past-participle>`` (``create`` ->
# ``created``, ``verify`` -> ``verified``, ``retry`` -> ``retried``).
_EVENT_EXCEPTIONS: dict[str, str] = {
    "core.task.cancel": "core.task.cancelled",
    "core.run.cancel": "core.run.cancelled",
    "core.media.replace_location": "core.media.location_replaced",
    "timeline.replace_config": "timeline.config_replaced",
    "shot.add_item": "shot.item_added",
    "shot.remove_item": "shot.item_removed",
    "reference.associate": "reference.media_associated",
    "reference.set_primary": "reference.primary_changed",
}


def _past_participle(verb: str) -> str:
    """The registry's default verb -> past-participle event suffix."""
    if verb.endswith("y") and len(verb) > 1:
        return verb[:-1] + "ied"
    if verb.endswith("e"):
        return verb + "d"
    return verb + "ed"


def _expected_event_kind(command_kind: str) -> str:
    """The event kind a command kind must emit (documented mapping)."""
    if command_kind in _EVENT_EXCEPTIONS:
        return _EVENT_EXCEPTIONS[command_kind]
    prefix, verb = command_kind.rsplit(".", 1)
    return f"{prefix}.{_past_participle(verb)}"


def _repository_labels(
    command_kind: str, pack_id: str, registry
) -> list[tuple[str, type]]:
    """Resolve the repository classes owning one command kind.

    Returns ``("module.ClassName", class)`` pairs for every repository that
    may implement the command: the single kernel repository for core
    namespace nouns, or the pack's manifest-declared repositories.
    """
    if pack_id == "core":
        noun = command_kind.split(".")[1]
        module_name, class_name = _CORE_NAMESPACE_REPOS[noun]
        module = importlib.import_module(module_name)
        return [(f"{module_name}.{class_name}", getattr(module, class_name))]
    module_name = _PACK_REPOSITORY_MODULES[pack_id]
    module = importlib.import_module(module_name)
    declared = sorted(
        name for name, owner in registry.repositories.items() if owner == pack_id
    )
    if not declared:
        raise AssertionError(
            f"{command_kind}: pack {pack_id!r} declares no repository class"
        )
    return [
        (f"{module_name}.{name}", getattr(module, name)) for name in declared
    ]


def test_every_command_kind_has_a_repository_method(standard_registry) -> None:
    """(a) Every declared command kind has an implementing repository method."""
    missing: list[str] = []
    for kind, pack_id in standard_registry.command_kinds.items():
        method = _METHOD_EXCEPTIONS[kind] if kind in _METHOD_EXCEPTIONS else kind.rsplit(".", 1)[1]
        classes = _repository_labels(kind, pack_id, standard_registry)
        if not any(hasattr(cls, method) for _, cls in classes):
            where = " or ".join(label for label, _ in classes)
            missing.append(f"{kind}: no repository method {method!r} on {where}")
    assert not missing, (
        "declared command kinds with no implementing repository method:\n"
        + "\n".join(missing)
    )


def test_every_command_kind_has_a_declared_event_counterpart(
    standard_registry,
) -> None:
    """(b) Every declared command kind has a same-pack event kind emitted."""
    missing: list[str] = []
    for kind, pack_id in standard_registry.command_kinds.items():
        expected = _expected_event_kind(kind)
        owner = standard_registry.event_kinds.get(expected)
        if owner is None:
            missing.append(f"{kind}: expected event kind {expected!r} is not declared")
        elif owner != pack_id:
            missing.append(
                f"{kind}: event {expected!r} is declared by pack {owner!r}, "
                f"not {pack_id!r}"
            )
    assert not missing, (
        "declared command kinds without a same-pack event counterpart:\n"
        + "\n".join(missing)
    )


def test_every_command_kind_has_a_v10_test_reference(standard_registry) -> None:
    """(c) Every declared command kind (or its event) is exercised in v10."""
    files = sorted(
        path
        for path in _TESTS_V10.glob("*.py")
        if path.name != Path(__file__).name
    )
    sources = [path.read_text(encoding="utf-8") for path in files]
    unreferenced: list[str] = []
    for kind in standard_registry.command_kinds:
        event = _expected_event_kind(kind)
        if not any(kind in text or event in text for text in sources):
            unreferenced.append(f"{kind} (event {event})")
    assert not unreferenced, (
        "declared command kinds with no v10 test reference:\n"
        + "\n".join(unreferenced)
    )
