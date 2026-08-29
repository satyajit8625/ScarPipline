"""Lazy registrar for tools shipped inside the ScarTools distribution."""

from __future__ import print_function

import importlib
import sys

from .menu import register_manifest


BUILTIN_TOOL_MODULES = (
    "scartools.tools.skin",
    "scartools.tools.character_finalizer",
    "scartools.tools.shader",
    "scartools.tools.modeling",
    "scartools.tools.udim",
    "scartools.tools.renamer",
    "scartools.tools.anim_io",
)

BUILTIN_TOOL_MANIFESTS = (
    "scartools.tools.skin.manifest:MANIFEST",
    "scartools.tools.character_finalizer.manifest:MANIFEST",
    "scartools.tools.shader.manifest:MANIFEST",
    "scartools.tools.modeling.manifest:MANIFEST",
    "scartools.tools.udim.manifest:MANIFEST",
    "scartools.tools.renamer.manifest:MANIFEST",
    "scartools.tools.anim_io.manifest:MANIFEST",
)



def _manifest(entry_point):
    module_name, attribute_name = entry_point.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, attribute_name)


def register_builtin_services(clear=True):
    from .framework import SERVICES, ServiceDefinition

    if clear:
        SERVICES.clear()
    registered = []
    for entry_point in BUILTIN_TOOL_MANIFESTS:
        manifest = _manifest(entry_point)
        for service in manifest.services:
            service_id, service_entry_point = service[:2]
            mutates_scene = bool(service[2]) if len(service) == 3 else False
            SERVICES.register(
                ServiceDefinition(service_id, service_entry_point, mutates_scene)
            )
            registered.append(service_id)
    return tuple(registered)


def register_builtin_tools(rebuild=True):
    register_builtin_services(clear=True)
    registered = []
    for entry_point in BUILTIN_TOOL_MANIFESTS:
        manifest = _manifest(entry_point)
        register_manifest(manifest, rebuild=False)
        registered.append(manifest.tool_id)

    if rebuild:
        from .menu import register_menu
        register_menu()
    return tuple(registered)


def close_builtin_windows():
    """Close only tool UIs that were actually imported in this Maya session."""
    closed = []
    for entry_point in BUILTIN_TOOL_MANIFESTS:
        manifest_module = entry_point.split(":", 1)[0]
        module = sys.modules.get(manifest_module)
        manifest = getattr(module, "MANIFEST", None) if module else None
        if manifest:
            try:
                if manifest.close_if_loaded():
                    closed.append(manifest.tool_id)
            except Exception:
                pass
    return tuple(closed)
