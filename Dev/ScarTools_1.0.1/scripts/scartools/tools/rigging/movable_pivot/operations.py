# -*- coding: utf-8 -*-
"""Headless atomic operations layer for Movable Pivot utility.

All operations execute inside SceneTransaction blocks for single-step Ctrl+Z
undo rollback and emit structured diagnostic studio logs.
"""

from __future__ import absolute_import, division, print_function

import maya.cmds as cmds
from scartools.framework.transactions import SceneTransaction
from scartools.framework.logging import emit_log
from scartools.framework.scene import get_selected_transforms

from .pivot_math import (
    get_bbox_point,
    get_component_centroid_and_vectors,
    calculate_aligned_rotation,
    parse_axis_string,
    set_pivot_position_non_destructive,
    set_pivot_orientation_non_destructive,
    get_world_pivot_position,
    get_world_pivot_rotation,
)
from .pivot_manager import (
    save_preset as _mgr_save_preset,
    apply_preset as _mgr_apply_preset,
    delete_preset as _mgr_delete_preset,
    rename_preset as _mgr_rename_preset,
    reset_pivot as _mgr_reset_pivot,
    get_presets as _mgr_get_presets,
    capture_initial_pivot,
)
from .validation import validate_target_node, validate_snap_targets


def _resolve_nodes(nodes=None):
    """Resolve target nodes to clean full DAG long paths."""
    if nodes is None:
        sel = get_selected_transforms()
        return list(sel)
    if isinstance(nodes, (str,)):
        nodes = [nodes]
    resolved = []
    for n in nodes:
        if cmds.objExists(n):
            longs = cmds.ls(n, long=True)
            if longs:
                resolved.append(longs[0])
    return resolved


def move_pivot_to_center(nodes=None):
    """Move pivot to object geometric centroid / bounding box center."""
    target_nodes = _resolve_nodes(nodes)
    if not target_nodes:
        emit_log("No valid target object selected.", level="WARNING", source="MovablePivot")
        return False

    with SceneTransaction("MovablePivot_Center"):
        for node in target_nodes:
            capture_initial_pivot(node)
            pt = get_bbox_point(node, "center", "center", "center", space="world")
            set_pivot_position_non_destructive(node, pt)
            emit_log("Moved pivot of '{}' to Center: ({:.2f}, {:.2f}, {:.2f})".format(
                node.split("|")[-1], pt[0], pt[1], pt[2]
            ), level="SUCCESS", source="MovablePivot")
    return True


def move_pivot_to_world_origin(nodes=None):
    """Move pivot to world origin (0, 0, 0)."""
    target_nodes = _resolve_nodes(nodes)
    if not target_nodes:
        emit_log("No valid target object selected.", level="WARNING", source="MovablePivot")
        return False

    with SceneTransaction("MovablePivot_WorldOrigin"):
        for node in target_nodes:
            capture_initial_pivot(node)
            set_pivot_position_non_destructive(node, (0.0, 0.0, 0.0))
            emit_log("Moved pivot of '{}' to World Origin (0, 0, 0)".format(
                node.split("|")[-1]
            ), level="SUCCESS", source="MovablePivot")
    return True


def move_pivot_to_bbox(nodes=None, x="center", y="center", z="center", space="world"):
    """
    Move pivot to specified bounding box extents (e.g. Bottom Center: x=center, y=min, z=center).
    """
    target_nodes = _resolve_nodes(nodes)
    if not target_nodes:
        emit_log("No valid target object selected.", level="WARNING", source="MovablePivot")
        return False

    with SceneTransaction("MovablePivot_BBox"):
        for node in target_nodes:
            capture_initial_pivot(node)
            pt = get_bbox_point(node, x_mode=x, y_mode=y, z_mode=z, space=space)
            set_pivot_position_non_destructive(node, pt)
            emit_log("Moved pivot of '{}' to BBox [X:{}, Y:{}, Z:{}]: ({:.2f}, {:.2f}, {:.2f})".format(
                node.split("|")[-1], x, y, z, pt[0], pt[1], pt[2]
            ), level="SUCCESS", source="MovablePivot")
    return True


def move_pivot_to_components(nodes=None, components=None, align_orientation=False, orientation_source="face_normal"):
    """
    Move pivot to centroid of selected mesh components (vertices, edges, or faces).
    Optionally aligns pivot orientation to average normal / tangent.
    """
    target_nodes = _resolve_nodes(nodes)
    if not target_nodes:
        # Check if components selected in viewport
        comp_sel = cmds.ls(selection=True, flatten=True) or []
        if comp_sel and "." in comp_sel[0]:
            parent_transform = comp_sel[0].split(".")[0]
            target_nodes = _resolve_nodes([parent_transform])

    if not target_nodes:
        emit_log("No target object or component selection found.", level="WARNING", source="MovablePivot")
        return False

    with SceneTransaction("MovablePivot_Components"):
        for node in target_nodes:
            capture_initial_pivot(node)
            data = get_component_centroid_and_vectors(node, components=components)
            pos = data["position"]
            set_pivot_position_non_destructive(node, pos)

            if align_orientation and data.get("normal"):
                rot = calculate_aligned_rotation(
                    primary_axis_str="Y" if orientation_source == "face_normal" else "X",
                    target_dir_vec=data["normal"],
                    secondary_axis_str="Z",
                    up_dir_vec=data.get("tangent", (1, 0, 0)),
                )
                set_pivot_orientation_non_destructive(node, rot)

            emit_log("Moved pivot of '{}' to {} components centroid: ({:.2f}, {:.2f}, {:.2f})".format(
                node.split("|")[-1], data["type"], pos[0], pos[1], pos[2]
            ), level="SUCCESS", source="MovablePivot")
    return True


def rotate_pivot_to_axes(nodes=None, primary_axis="X", target_source="world", secondary_axis="Y", up_source="world"):
    """
    Rotate and align pivot orientation to target vector sources non-destructively.
    """
    target_nodes = _resolve_nodes(nodes)
    if not target_nodes:
        emit_log("No valid target object selected.", level="WARNING", source="MovablePivot")
        return False

    # Resolve target and up vectors
    target_vec = parse_axis_string(primary_axis)
    up_vec = parse_axis_string(secondary_axis)

    with SceneTransaction("MovablePivot_Rotate"):
        for node in target_nodes:
            capture_initial_pivot(node)
            rot = calculate_aligned_rotation(
                primary_axis_str=primary_axis,
                target_dir_vec=target_vec,
                secondary_axis_str=secondary_axis,
                up_dir_vec=up_vec,
            )
            set_pivot_orientation_non_destructive(node, rot)
            emit_log("Aligned pivot rotation of '{}' to [Pri:{}, Sec:{}]: ({:.1f}°, {:.1f}°, {:.1f}°)".format(
                node.split("|")[-1], primary_axis, secondary_axis, rot[0], rot[1], rot[2]
            ), level="SUCCESS", source="MovablePivot")
    return True


def snap_pivot_to_object(target_nodes=None, reference_node=None, snap_pos=True, snap_rot=True):
    """Snap pivot position and/or orientation from reference object."""
    targets = _resolve_nodes(target_nodes)
    if not targets:
        emit_log("No target object selected for snapping.", level="WARNING", source="MovablePivot")
        return False

    if not reference_node or not cmds.objExists(reference_node):
        # Use second item in selection if multi-selected
        sel = cmds.ls(selection=True, long=True) or []
        if len(sel) >= 2:
            targets = [sel[0]]
            reference_node = sel[1]
        else:
            emit_log("Select target object first, then reference object to snap.", level="WARNING", source="MovablePivot")
            return False

    is_valid, err = validate_snap_targets(targets[0], reference_node)
    if not is_valid:
        emit_log(err, level="WARNING", source="MovablePivot")
        return False

    ref_pos = get_world_pivot_position(reference_node)
    ref_rot = get_world_pivot_rotation(reference_node)

    with SceneTransaction("MovablePivot_Snap"):
        for node in targets:
            capture_initial_pivot(node)
            if snap_pos:
                set_pivot_position_non_destructive(node, ref_pos)
            if snap_rot:
                set_pivot_orientation_non_destructive(node, ref_rot)
            emit_log("Snapped pivot of '{}' to reference '{}'".format(
                node.split("|")[-1], reference_node.split("|")[-1]
            ), level="SUCCESS", source="MovablePivot")
    return True


def save_pivot_preset(nodes=None, preset_name="Pivot_01"):
    """Save current pivot position and orientation as a preset."""
    targets = _resolve_nodes(nodes)
    if not targets:
        emit_log("No object selected to save preset.", level="WARNING", source="MovablePivot")
        return False

    for node in targets:
        success = _mgr_save_preset(node, preset_name)
        if success:
            emit_log("Saved pivot preset '{}' on '{}'.".format(preset_name, node.split("|")[-1]), level="SUCCESS", source="MovablePivot")
    return True


def apply_pivot_preset(nodes=None, preset_name="Pivot_01"):
    """Apply saved pivot preset to node."""
    targets = _resolve_nodes(nodes)
    if not targets:
        emit_log("No object selected to apply preset.", level="WARNING", source="MovablePivot")
        return False

    with SceneTransaction("MovablePivot_ApplyPreset"):
        for node in targets:
            success = _mgr_apply_preset(node, preset_name)
            if success:
                emit_log("Applied pivot preset '{}' to '{}'.".format(preset_name, node.split("|")[-1]), level="SUCCESS", source="MovablePivot")
    return True


def delete_pivot_preset(nodes=None, preset_name="Pivot_01"):
    """Delete saved pivot preset from node."""
    targets = _resolve_nodes(nodes)
    if not targets:
        return False
    for node in targets:
        _mgr_delete_preset(node, preset_name)
        emit_log("Deleted pivot preset '{}' from '{}'.".format(preset_name, node.split("|")[-1]), level="INFO", source="MovablePivot")
    return True


def reset_pivot(nodes=None):
    """Restore original pivot position and rotation or center bounding box."""
    targets = _resolve_nodes(nodes)
    if not targets:
        emit_log("No object selected to reset pivot.", level="WARNING", source="MovablePivot")
        return False

    with SceneTransaction("MovablePivot_Reset"):
        for node in targets:
            _mgr_reset_pivot(node)
            emit_log("Reset pivot on '{}' to original position.".format(node.split("|")[-1]), level="SUCCESS", source="MovablePivot")
    return True
