# -*- coding: utf-8 -*-
"""UDIM Texture Manager package with lazy API and UI loading."""

from .manifest import MANIFEST
from .operations import scan_udim_textures, generate_all_udim_previews, parse_udim_pattern, run_generate_udim


def show_ui():
    # Direct 1-click execution without window
    return run_generate_udim()


def close_all_windows():
    from .ui import close_all_windows as _close_all_windows
    return _close_all_windows()


__all__ = [
    "MANIFEST",
    "show_ui",
    "run_generate_udim",
    "close_all_windows",
    "scan_udim_textures",
    "generate_all_udim_previews",
    "parse_udim_pattern",
]

