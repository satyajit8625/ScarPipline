"""Lazy Shader Tools UI exports."""


def show_ui(initial_tab=0):
    from .windows import show_ui as _show
    return _show(initial_tab=initial_tab)


def close_all_windows():
    from .windows import close_all_windows as _close
    return _close()


__all__ = ["show_ui", "close_all_windows"]
