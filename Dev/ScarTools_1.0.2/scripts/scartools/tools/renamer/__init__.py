# -*- coding: utf-8 -*-
"""Pipeline Renamer package with lazy API and UI loading."""

from .manifest import MANIFEST
from .operations import compute_new_name, preview_rename, execute_batch_rename


def show_ui():
    from .ui import show_ui as _show_ui
    return _show_ui()


def close_all_windows():
    from .ui import close_all_windows as _close_all_windows
    return _close_all_windows()


__all__ = [
    "MANIFEST",
    "show_ui",
    "close_all_windows",
    "compute_new_name",
    "preview_rename",
    "execute_batch_rename",
]
