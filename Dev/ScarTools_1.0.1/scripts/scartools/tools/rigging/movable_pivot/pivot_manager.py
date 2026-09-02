# -*- coding: utf-8 -*-
"""Persistent Pivot Presets and Bookmarks Manager.

Stores named pivot states directly onto Maya DAG nodes using dynamic
JSON-serialized string attributes without mutating scene file structures.
"""

from __future__ import absolute_import, division, print_function

import json
import time
import maya.cmds as cmds

from .model import PivotPreset
from .pivot_math import (
    get_world_pivot_position,
    get_world_pivot_rotation,
    set_pivot_position_non_destructive,
    set_pivot_orientation_non_destructive,
)

PRESETS_ATTR = "_scartools_pivot_presets"
ORIGINAL_ATTR = "_scartools_orig_pivot"


def _ensure_attr(node, attr_name):
    """Ensure dynamic string attribute exists on node."""
    if not cmds.attributeQuery(attr_name, node=node, exists=True):
        cmds.addAttr(node, longName=attr_name, dataType="string", hidden=True)


def capture_initial_pivot(node):
    """Store initial pivot state on node if not already captured."""
    if not node or not cmds.objExists(node):
        return
    _ensure_attr(node, ORIGINAL_ATTR)
    val = cmds.getAttr("{}.{}".format(node, ORIGINAL_ATTR))
    if not val:
        orig = {
            "position": list(get_world_pivot_position(node)),
            "rotation": list(get_world_pivot_rotation(node)),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        cmds.setAttr("{}.{}".format(node, ORIGINAL_ATTR), json.dumps(orig), type="string")


def get_presets(node):
    """Retrieve list of PivotPreset objects stored on the node."""
    if not node or not cmds.objExists(node):
        return []
    if not cmds.attributeQuery(PRESETS_ATTR, node=node, exists=True):
        return []

    raw = cmds.getAttr("{}.{}".format(node, PRESETS_ATTR)) or "[]"
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            presets = [PivotPreset.from_dict(d) for d in data if d]
            return [p for p in presets if p]
    except Exception:
        pass
    return []


def save_preset(node, name):
    """Save current pivot state as a named preset on node."""
    if not node or not cmds.objExists(node):
        return False
    clean_name = str(name).strip() or "Pivot_01"
    capture_initial_pivot(node)

    current_presets = get_presets(node)
    # Remove existing preset with same name if present
    filtered = [p for p in current_presets if p.name.lower() != clean_name.lower()]

    new_preset = PivotPreset(
        name=clean_name,
        position=get_world_pivot_position(node),
        rotation=get_world_pivot_rotation(node),
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
    filtered.append(new_preset)

    _ensure_attr(node, PRESETS_ATTR)
    serialized = json.dumps([p.to_dict() for p in filtered], indent=2)
    cmds.setAttr("{}.{}".format(node, PRESETS_ATTR), serialized, type="string")
    return True


def apply_preset(node, name):
    """Apply a saved pivot preset to node."""
    if not node or not cmds.objExists(node):
        return False
    presets = get_presets(node)
    matched = next((p for p in presets if p.name.lower() == str(name).strip().lower()), None)
    if not matched:
        return False

    set_pivot_position_non_destructive(node, matched.position)
    if matched.rotation:
        set_pivot_orientation_non_destructive(node, matched.rotation)
    return True


def delete_preset(node, name):
    """Delete a named pivot preset from node."""
    if not node or not cmds.objExists(node):
        return False
    presets = get_presets(node)
    clean_name = str(name).strip().lower()
    filtered = [p for p in presets if p.name.lower() != clean_name]
    if len(filtered) == len(presets):
        return False

    _ensure_attr(node, PRESETS_ATTR)
    serialized = json.dumps([p.to_dict() for p in filtered], indent=2)
    cmds.setAttr("{}.{}".format(node, PRESETS_ATTR), serialized, type="string")
    return True


def rename_preset(node, old_name, new_name):
    """Rename a pivot preset."""
    if not node or not cmds.objExists(node):
        return False
    clean_old = str(old_name).strip().lower()
    clean_new = str(new_name).strip()
    if not clean_new:
        return False

    presets = get_presets(node)
    updated = False
    for p in presets:
        if p.name.lower() == clean_old:
            p.name = clean_new
            updated = True
            break

    if updated:
        _ensure_attr(node, PRESETS_ATTR)
        serialized = json.dumps([p.to_dict() for p in presets], indent=2)
        cmds.setAttr("{}.{}".format(node, PRESETS_ATTR), serialized, type="string")
        return True
    return False


def reset_pivot(node):
    """Reset pivot to original captured state or object bounding box center."""
    if not node or not cmds.objExists(node):
        return False

    if cmds.attributeQuery(ORIGINAL_ATTR, node=node, exists=True):
        raw = cmds.getAttr("{}.{}".format(node, ORIGINAL_ATTR)) or "{}"
        try:
            orig = json.loads(raw)
            if "position" in orig:
                set_pivot_position_non_destructive(node, orig["position"])
                if "rotation" in orig:
                    set_pivot_orientation_non_destructive(node, orig["rotation"])
                return True
        except Exception:
            pass

    # Fallback: Center of Bounding Box with zero rotation
    bb_center = cmds.xform(node, query=True, worldSpace=True, boundingBox=True)
    if bb_center and len(bb_center) == 6:
        cx = (bb_center[0] + bb_center[3]) * 0.5
        cy = (bb_center[1] + bb_center[4]) * 0.5
        cz = (bb_center[2] + bb_center[5]) * 0.5
        set_pivot_position_non_destructive(node, (cx, cy, cz))
    set_pivot_orientation_non_destructive(node, (0.0, 0.0, 0.0))
    return True
