"""Character Finalizer package with lazy API and UI loading."""

from scartools.version import VERSION, __version__


def show_ui():
    from .ui import show_ui as _show_ui
    return _show_ui()


show = show_ui


def inspect_character(*args, **kwargs):
    from .api import inspect_character as _inspect
    return _inspect(*args, **kwargs)


def build_plan(*args, **kwargs):
    from .api import build_plan as _build
    return _build(*args, **kwargs)


def finalize_character(*args, **kwargs):
    from .api import finalize_character as _finalize
    return _finalize(*args, **kwargs)


__all__ = [
    "VERSION",
    "__version__",
    "build_plan",
    "finalize_character",
    "inspect_character",
    "show",
    "show_ui",
]
