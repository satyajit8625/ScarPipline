# -*- coding: utf-8 -*-
"""Tool manifest contract for Movable Pivot utility."""

from __future__ import absolute_import, division, print_function

from scartools.framework import ToolManifest
from scartools.version import VERSION

MANIFEST = ToolManifest(
    tool_id="scartools_movable_pivot",
    package="scartools.tools.rigging.movable_pivot",
    department="rigging",
    label="Movable Pivot...",
    version=VERSION,
    entry_point="scartools.tools.rigging.movable_pivot.ui:show_window",
    close_entry_point="scartools.tools.rigging.movable_pivot.ui:close_all_windows",
    controller_entry_point="scartools.tools.rigging.movable_pivot.controller:MovablePivotController",
    ui_spec_entry_point="scartools.tools.rigging.movable_pivot.ui_spec:UI_SPEC",
    annotation="Non-destructive matrix-based pivot editing, alignment, snapping, and preset manager.",
    icon_name="department_rigging.png",
    order=15,
    capabilities=(
        "rigging.pivot.move",
        "rigging.pivot.rotate",
        "rigging.pivot.snap",
        "rigging.pivot.presets",
        "rigging.pivot.reset",
    ),
    services=(
        ("rigging.movable_pivot.move_center", "scartools.tools.rigging.movable_pivot.operations:move_pivot_to_center", True),
        ("rigging.movable_pivot.move_world", "scartools.tools.rigging.movable_pivot.operations:move_pivot_to_world_origin", True),
        ("rigging.movable_pivot.move_bbox", "scartools.tools.rigging.movable_pivot.operations:move_pivot_to_bbox", True),
        ("rigging.movable_pivot.move_components", "scartools.tools.rigging.movable_pivot.operations:move_pivot_to_components", True),
        ("rigging.movable_pivot.rotate", "scartools.tools.rigging.movable_pivot.operations:rotate_pivot_to_axes", True),
        ("rigging.movable_pivot.snap", "scartools.tools.rigging.movable_pivot.operations:snap_pivot_to_object", True),
        ("rigging.movable_pivot.save_preset", "scartools.tools.rigging.movable_pivot.operations:save_pivot_preset", True),
        ("rigging.movable_pivot.apply_preset", "scartools.tools.rigging.movable_pivot.operations:apply_pivot_preset", True),
        ("rigging.movable_pivot.delete_preset", "scartools.tools.rigging.movable_pivot.operations:delete_pivot_preset", True),
        ("rigging.movable_pivot.reset", "scartools.tools.rigging.movable_pivot.operations:reset_pivot", True),
    ),
)
