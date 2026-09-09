"""Skin Tools public API. Importing it never loads Qt."""

from scartools.version import VERSION, __version__

import importlib


_API_NAMES = {
    "SkinIOError",
    "copy_skin_weights",
    "copy_skin_cluster",
    "batch_export",
    "batch_import",
    "export_skin_weights",
    "export_skin_package",
    "import_skin_weights",
    "import_skin_package",
    "load_skin_package",
    "mirror_skin_weights",
    "mirror_skin_weights_from_selected",
    "remove_unused_influences",
    "remove_unused_influences_from_selected",
    "selected_meshes",
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
    """Open the Export / Import interface."""
    from .ui import show_ui as _show_ui
    return _show_ui()


def show_skin_utilities():
    """Open the main window on the Utilities tab."""
    from .ui import show_skin_utilities as _show_skin_utilities
    return _show_skin_utilities()


show = show_ui
show_utilities = show_skin_utilities


__all__ = [
    "VERSION",
    "__version__",
    "SkinIOError",
    "show",
    "show_ui",
    "show_utilities",
    "show_skin_utilities",
    "copy_skin_weights",
    "copy_skin_cluster",
    "export_skin_weights",
    "export_skin_package",
    "batch_export",
    "import_skin_weights",
    "import_skin_package",
    "load_skin_package",
    "batch_import",
    "mirror_skin_weights",
    "mirror_skin_weights_from_selected",
    "remove_unused_influences",
    "remove_unused_influences_from_selected",
    "selected_meshes",
]
