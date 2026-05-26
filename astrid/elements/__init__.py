"""Element content package with public re-exports for framework modules."""

from __future__ import annotations

from typing import Any

from astrid.core.element import catalog, cli, install, registry, schema

_EXPORTS = {
    "ELEMENT_KINDS": schema,
    "REQUIRED_ELEMENT_FILES": schema,
    "ElementConflict": registry,
    "ElementDefinition": schema,
    "ElementDependencies": schema,
    "ElementInstallError": install,
    "ElementInstallPlan": install,
    "ElementInstallResult": install,
    "ElementRegistry": registry,
    "ElementRegistryError": registry,
    "ElementSource": registry,
    "ElementValidationError": schema,
    "build_element_install_plan": install,
    "install_element": install,
    "load_default_registry": registry,
    "load_element_definition": schema,
    "validate_element_definition": schema,
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(_EXPORTS[name], name)
