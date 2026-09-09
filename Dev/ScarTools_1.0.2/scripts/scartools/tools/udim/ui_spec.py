# -*- coding: utf-8 -*-
"""Declarative UI specification for UDIM Texture Manager."""

from __future__ import absolute_import, division, print_function

UI_SPEC = {
    "tool_id": "scartools_udim",
    "title": "UDIM TEXTURE MANAGER",
    "subtitle": "Audit, convert, and generate Viewport 2.0 texture previews for multi-tile UVs",
    "accent": "texturing",
    "actions": (
        ("GENERATE ALL UDIM PREVIEWS", "export"),
        ("CONVERT TO <UDIM>", "primary"),
    ),
}
