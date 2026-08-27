"""Lazy Character Finalizer UI exports."""


def show_ui():
    from .windows import show_ui as _show_ui
    return _show_ui()


def close_all_windows():
    from .windows import close_all_windows as _close
    return _close()


__all__ = ["close_all_windows", "show_ui"]
