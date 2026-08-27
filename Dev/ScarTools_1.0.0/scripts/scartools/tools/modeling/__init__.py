"""Modeling & Scene Sanitizer package with lazy API and UI loading."""

from scartools.version import VERSION, __version__

import importlib

_API_NAMES = {
    "ModelSanitizerError",
    "inspect_model_and_scene",
    "inspect_model",
    "select_issue_components",
    "select_model_issues",
    "fix_all_safe_issues",
    "fix_model_issues",
    "clean_scene_clutter",
    "fix_make_names_unique",
    "fix_add_geo_suffixes",
    "fix_add_grp_suffixes",
    "fix_shader_suffixes",
    "fix_freeze_transforms",
    "fix_center_pivots",
    "fix_delete_construction_history",
    "fix_delete_intermediate_shapes",
    "fix_unlock_normals",
    "fix_clean_scene_clutter",
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

def show_ui():
    from .ui import show_ui as _show_ui
    return _show_ui()

show = show_ui

__all__ = [
    "VERSION",
    "__version__",
    "ModelSanitizerError",
    "inspect_model_and_scene",
    "inspect_model",
    "select_issue_components",
    "select_model_issues",
    "fix_all_safe_issues",
    "fix_model_issues",
    "clean_scene_clutter",
    "show",
    "show_ui",
]
