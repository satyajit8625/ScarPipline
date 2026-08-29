# -*- coding: utf-8 -*-
"""Controller for Animation Export & Import Suite."""

from __future__ import absolute_import, division, print_function

from scartools.framework import ToolController
from .operations import (
    export_shot_package,
    import_shot_package,
    discover_scene_assets,
    load_shot_manifest,
)


class AnimIOController(ToolController):
    """Controller coordinating Anim I/O operations and UI state."""

    def __init__(self):
        super(AnimIOController, self).__init__(tool_id="scartools_anim_io")

    def discover_assets(self):
        return discover_scene_assets()

    def export_shot(self, **kwargs):
        return export_shot_package(**kwargs)

    def import_shot(self, **kwargs):
        return import_shot_package(**kwargs)

    def load_manifest(self, path):
        return load_shot_manifest(path)
