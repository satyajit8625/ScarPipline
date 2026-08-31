# -*- coding: utf-8 -*-
"""Declarative ScarTools manifest for Animation Export & Import Suite."""

from __future__ import absolute_import, division, print_function

from scartools.framework import ToolManifest
from scartools.version import VERSION

MANIFEST = ToolManifest(
    tool_id="scartools_anim_io",
    package="scartools.tools.anim_io",
    department="animation",
    label="Animation Export...",
    version=VERSION,
    entry_point="scartools.tools.anim_io:show_ui",
    close_entry_point="scartools.tools.anim_io.ui:close_all_windows",
    controller_entry_point="scartools.tools.anim_io.controller:AnimIOController",
    ui_spec_entry_point="scartools.tools.anim_io.ui_spec:UI_SPEC",
    annotation="Shot animation packaging, Alembic & FBX cache extraction to studio pipeline folders.",
    icon_name="department_animation.png",
    order=10,
    capabilities=(
        "anim.export.shot_package",
        "anim.export.camera",
        "anim.export.characters",
        "anim.export.props",
        "anim.import.shot_assembly",
        "anim.manifest.build",
    ),
    services=(
        ("anim.export_shot", "scartools.tools.anim_io.api:export_shot_package", True),
        ("anim.import_shot", "scartools.tools.anim_io.api:import_shot_package", True),
        ("anim.discover_assets", "scartools.tools.anim_io.api:discover_scene_assets", False),
    ),
)
