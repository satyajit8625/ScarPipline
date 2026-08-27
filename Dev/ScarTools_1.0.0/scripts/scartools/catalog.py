"""Read-only discovery API for ScarTools launchers and pipeline automation."""

import importlib

from .builtin import BUILTIN_TOOL_MANIFESTS


def iter_manifests():
    """Yield built-in manifests without loading tool core or Qt modules."""
    for entry_point in BUILTIN_TOOL_MANIFESTS:
        module_name, attribute_name = entry_point.split(":", 1)
        module = importlib.import_module(module_name)
        yield getattr(module, attribute_name)


def manifests():
    return tuple(iter_manifests())


def find_tool(tool_id):
    for manifest in iter_manifests():
        if manifest.tool_id == tool_id:
            return manifest
    return None


def find_capability(capability):
    return tuple(
        manifest
        for manifest in iter_manifests()
        if capability in manifest.capabilities
    )


def find_service(service_id):
    """Return a lazily callable suite service definition."""
    from .framework import SERVICES
    service = SERVICES.get(service_id)
    if service is None:
        from .builtin import register_builtin_services
        register_builtin_services(clear=False)
        service = SERVICES.get(service_id)
    return service


def manifest_data():
    """Return JSON-safe data for external launchers or diagnostics."""
    return tuple(manifest.as_dict() for manifest in iter_manifests())


__all__ = [
    "iter_manifests",
    "manifests",
    "find_tool",
    "find_capability",
    "find_service",
    "manifest_data",
]
