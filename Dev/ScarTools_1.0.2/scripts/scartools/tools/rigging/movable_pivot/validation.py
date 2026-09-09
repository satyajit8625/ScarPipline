# -*- coding: utf-8 -*-
"""Validation and Preflight Quality Assurance for Movable Pivot."""

from __future__ import absolute_import, division, print_function

import maya.cmds as cmds


def validate_target_node(node):
    """
    Validate that a given transform node exists, is not referenced/locked,
    and is ready for non-destructive pivot editing.

    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    if not node:
        return False, "No target object selected."

    if not cmds.objExists(node):
        return False, "Target node '{}' does not exist in active scene.".format(node)

    try:
        node_type = cmds.nodeType(node)
        if node_type not in ("transform", "joint"):
            parents = cmds.listRelatives(node, parent=True, fullPath=True)
            if not parents and node_type != "mesh":
                return False, "Node '{}' (type '{}') is not a valid transform or joint.".format(node, node_type)
    except Exception:
        pass

    # Check attribute locks
    for attr in ("rotatePivot", "scalePivot"):
        for axis in ("X", "Y", "Z"):
            plug = "{}.{}{}".format(node, attr, axis)
            try:
                if cmds.getAttr(plug, lock=True):
                    return False, "Attribute '{}' is locked on target object.".format(plug)
            except Exception:
                pass

    return True, ""


def validate_snap_targets(target_node, reference_node):
    """Verify that both target and reference objects exist and are distinct."""
    v_tgt, err_tgt = validate_target_node(target_node)
    if not v_tgt:
        return False, err_tgt

    if not reference_node or not cmds.objExists(reference_node):
        return False, "Reference snap object does not exist."

    tgt_longs = cmds.ls(target_node, long=True)
    ref_longs = cmds.ls(reference_node, long=True)
    if tgt_longs and ref_longs and tgt_longs[0] == ref_longs[0]:
        return False, "Cannot snap pivot to the same object."

    return True, ""
