# -*- coding: utf-8 -*-
"""Declarative UI Specification contract for Anim I/O."""

from __future__ import absolute_import, division, print_function

UI_SPEC = {
    "tool_id": "scartools_anim_io",
    "title": "Animation I/O Suite",
    "modes": ["export", "import"],
    "default_mode": "export",
    "formats": {
        "camera": ["fbx", "abc"],
        "geometry": ["abc", "fbx", "both"],
    },
}
