# -*- coding: utf-8 -*-
"""ScarTools Anim Export Tool (`anim_io`)."""

from __future__ import absolute_import, division, print_function

from .manifest import MANIFEST
from .operations import (
    export_shot_package,
    import_shot_package,
    discover_scene_assets,
    load_shot_manifest,
)


def show():
    """Launch the Anim Export tool window."""
    from .ui.windows import show_window
    return show_window()


def show_ui():
    return show()


def close_all_windows():
    from .ui.windows import close_all_windows as _close
    _close()


__all__ = [
    "MANIFEST",
    "show",
    "show_ui",
    "close_all_windows",
    "export_shot_package",
    "import_shot_package",
    "discover_scene_assets",
    "load_shot_manifest",
]
