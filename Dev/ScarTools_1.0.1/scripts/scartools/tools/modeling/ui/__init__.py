"""Lazy UI exports for Modeling & Scene Sanitizer."""

def show_ui():
    from .windows import show_ui as _show
    return _show()

show = show_ui

def close_all_windows():
    from .windows import close_all_windows as _close
    return _close()

__all__ = ["show_ui", "show", "close_all_windows"]
