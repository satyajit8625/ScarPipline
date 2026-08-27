"""Lazy Skin Tools UI exports."""


def show_ui():
    from .windows import show_ui as _show
    return _show()


def show_skin_utilities():
    from .windows import show_skin_utilities as _show
    return _show()


def close_all_windows():
    from .windows import close_all_windows as _close
    return _close()

__all__ = ["show_ui", "show_skin_utilities", "close_all_windows"]
