"""Shader Tools package with lazy API and UI loading."""

from scartools.version import VERSION, __version__

import importlib


_API_NAMES = {
    "ShaderToolsError",
    "all_mesh_transforms",
    "collect_and_bundle_textures",
    "collect_shader_assignments",
    "export_shader_package",
    "export_shader_snapshot",
    "import_shader_package",
    "inspect_shader_package",
    "inspect_texture_paths",
    "load_shader_package",
    "mesh_transforms",
    "repath_texture_paths",
    "resolve_shader_snapshot",
    "sanitize_base_name",
}


def __getattr__(name):
    if name in _API_NAMES:
        api = importlib.import_module(".api", __name__)
        value = getattr(api, name)
        globals()[name] = value
        return value
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))


def __dir__():
    return sorted(set(globals()).union(_API_NAMES))


def show_ui(initial_tab=0):
    from .ui import show_ui as _show_ui
    return _show_ui(initial_tab=initial_tab)


show = show_ui


__all__ = [
    "VERSION",
    "__version__",
    "ShaderToolsError",
    "mesh_transforms",
    "all_mesh_transforms",
    "collect_shader_assignments",
    "collect_and_bundle_textures",
    "sanitize_base_name",
    "export_shader_package",
    "export_shader_snapshot",
    "load_shader_package",
    "inspect_shader_package",
    "inspect_texture_paths",
    "import_shader_package",
    "repath_texture_paths",
    "resolve_shader_snapshot",
    "show",
    "show_ui",
]
