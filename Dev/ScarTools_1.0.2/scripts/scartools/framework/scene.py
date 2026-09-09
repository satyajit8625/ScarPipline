# -*- coding: utf-8 -*-
"""Centralized Maya scene query, DAG path normalization, and node helper library.

Pure headless module suitable for mayapy and batch pipeline operations.
"""

from __future__ import absolute_import, division, print_function

import maya.cmds as cmds


def get_selected_transforms(mesh_only=False, hierarchy=False):
    """
    Return clean long DAG paths for selected Maya transforms.

    Args:
        mesh_only (bool): If True, filter transforms that own a valid mesh shape.
        hierarchy (bool): If True, expand to all descendants in selection.

    Returns:
        tuple[str]: Ordered tuple of unique full DAG long paths.
    """
    selected = cmds.ls(selection=True, long=True) or []
    if not selected:
        return ()

    if hierarchy:
        expanded = cmds.listRelatives(selected, allDescendents=True, fullPath=True, type="transform") or []
        nodes = list(selected) + list(expanded)
    else:
        nodes = list(selected)

    # Filter transforms
    transforms = []
    seen = set()
    for node in nodes:
        if node in seen:
            continue
        seen.add(node)
        if cmds.nodeType(node) == "transform":
            if mesh_only:
                if get_shape_node(node, shape_type="mesh"):
                    transforms.append(node)
            else:
                transforms.append(node)
        elif mesh_only and cmds.nodeType(node) == "mesh":
            parent = cmds.listRelatives(node, parent=True, fullPath=True)
            if parent and parent[0] not in seen:
                seen.add(parent[0])
                transforms.append(parent[0])

    return tuple(transforms)


def get_all_scene_meshes():
    """Return long DAG paths of all non-intermediate mesh transforms in active scene."""
    shapes = cmds.ls(type="mesh", long=True, noIntermediate=True) or []
    transforms = []
    seen = set()
    for shape in shapes:
        parent = cmds.listRelatives(shape, parent=True, fullPath=True)
        if parent:
            p = parent[0]
            if p not in seen:
                seen.add(p)
                transforms.append(p)
    return tuple(transforms)


def get_shape_node(transform, shape_type=None, no_intermediate=True):
    """
    Return the primary shape node DAG path under a given transform.

    Args:
        transform (str): Transform node name or DAG path.
        shape_type (str, optional): Target shape type filter (e.g. 'mesh', 'nurbsCurve').
        no_intermediate (bool): If True, ignore intermediate history shapes.

    Returns:
        str or None: Full DAG path of the shape node, or None if not found.
    """
    if not transform or not cmds.objExists(transform):
        return None

    if cmds.nodeType(transform) in ("mesh", "nurbsCurve", "nurbsSurface", "camera", "light"):
        return transform

    shapes = cmds.listRelatives(
        transform,
        shapes=True,
        fullPath=True,
        noIntermediate=no_intermediate,
        type=shape_type,
    ) or []
    return shapes[0] if shapes else None


def get_short_name(dag_path):
    """
    Return the leaf name of a DAG path or node without path separators or namespaces.

    Args:
        dag_path (str): Full or partial DAG path.

    Returns:
        str: Short node name.
    """
    if not dag_path:
        return ""
    leaf = str(dag_path).split("|")[-1]
    return leaf.split(":")[-1]


def split_namespace(node_name):
    """
    Split a node into (namespace, base_name).

    Returns:
        tuple[str, str]: (namespace, base_name). If no namespace, namespace is empty string.
    """
    if not node_name:
        return ("", "")
    leaf = str(node_name).split("|")[-1]
    if ":" in leaf:
        parts = leaf.rsplit(":", 1)
        return (parts[0], parts[1])
    return ("", leaf)


def get_connected_nodes(node, type_name=None, as_destination=True, as_source=True):
    """
    Find all connected nodes of a specific type.

    Args:
        node (str): Node name.
        type_name (str, optional): Maya node type filter.
        as_destination (bool): Query upstream connections.
        as_source (bool): Query downstream connections.

    Returns:
        tuple[str]: Connected node names.
    """
    if not node or not cmds.objExists(node):
        return ()

    kwargs = {
        "source": as_destination,
        "destination": as_source,
        "exactType": False,
    }
    if type_name:
        kwargs["type"] = type_name

    conns = cmds.listConnections(node, **kwargs) or []
    seen = set()
    result = []
    for c in conns:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return tuple(result)


__all__ = [
    "get_selected_transforms",
    "get_all_scene_meshes",
    "get_shape_node",
    "get_short_name",
    "split_namespace",
    "get_connected_nodes",
]


def get_scene_fps():
    """Query active Maya scene FPS cleanly with full fractional precision."""
    try:
        if hasattr(cmds, "currentTimeUnitToFPS"):
            return float(cmds.currentTimeUnitToFPS())
    except Exception:
        pass

    try:
        unit = str(cmds.currentUnit(query=True, time=True)).strip().lower()
        fps_map = {
            "game": 15.0,
            "film": 24.0,
            "pal": 25.0,
            "ntsc": 30.0,
            "show": 48.0,
            "palf": 50.0,
            "palfps": 50.0,
            "ntscf": 60.0,
            "ntscfps": 60.0,
            "23.976fps": 23.976,
            "29.97fps": 29.97,
            "29.97df": 29.97,
            "47.952fps": 47.952,
            "59.94fps": 59.94,
            "24fps": 24.0,
            "25fps": 25.0,
            "30fps": 30.0,
            "48fps": 48.0,
            "50fps": 50.0,
            "60fps": 60.0,
        }
        if unit in fps_map:
            return fps_map[unit]
        if unit.endswith("fps"):
            return float(unit[:-3])
    except Exception:
        pass
    return 24.0


def get_scene_frame_range():
    """Return active timeline (start_frame, end_frame) as integers."""
    try:
        if hasattr(cmds, "playbackOptions"):
            min_t = cmds.playbackOptions(q=True, minTime=True)
            max_t = cmds.playbackOptions(q=True, maxTime=True)
            if min_t is not None and max_t is not None:
                start = int(min_t)
                end = int(max_t)
                return (min(start, end), max(start, end))
    except Exception:
        pass
    return (1001, 1100)


class suspend_viewport_refresh(object):
    """
    Context manager that silently pauses 3D viewport drawing, suspends undo logging,
    disables Cached Playback, and restores selection during heavy operations.
    - Achieves fast export/import evaluation speed without GPU redraw overhead.
    - Does NOT trigger Maya's red outline box or 'Paused' watermark.
    - Does NOT suppress Qt dialogs or live progress popups.
    - Prevents undo memory bloat and background cache contention.
    - Restores scene selection state on exit to eliminate post-operation wireframe lag.
    """

    def __enter__(self):
        self._panel_states = {}
        self._prev_undo_state = None
        self._prev_cache_state = None
        self._prev_selection = None

        # 1. Snapshot active selection
        try:
            if hasattr(cmds, "ls"):
                self._prev_selection = cmds.ls(selection=True, long=True) or []
        except Exception:
            self._prev_selection = None

        # 2. Suspend Maya Undo Queue logging (preserves existing undo stack without memory bloat)
        try:
            if hasattr(cmds, "undoInfo"):
                self._prev_undo_state = cmds.undoInfo(query=True, stateWithoutFlush=True)
                cmds.undoInfo(stateWithoutFlush=False)
        except Exception:
            self._prev_undo_state = None

        # 3. Temporarily suspend Cached Playback (Maya 2020+) to free RAM and eliminate CPU contention
        try:
            if hasattr(cmds, "evaluator") and not cmds.about(batch=True):
                self._prev_cache_state = cmds.evaluator(query=True, enable=True, name="cache")
                if self._prev_cache_state:
                    cmds.evaluator(enable=False, name="cache")
        except Exception:
            self._prev_cache_state = None

        # 4. Silent Viewport Pause (disables modelPanel object display, zero red box)
        try:
            # Clear any lingering OGS pause state so no red border remains
            if hasattr(cmds, "ogs") and not cmds.about(batch=True):
                try:
                    cmds.ogs(pause=False)
                except Exception:
                    pass

            if hasattr(cmds, "getPanel") and hasattr(cmds, "modelEditor") and not cmds.about(batch=True):
                panels = cmds.getPanel(type="modelPanel") or []
                for p in panels:
                    try:
                        if cmds.modelEditor(p, query=True, exists=True):
                            was_visible = cmds.modelEditor(p, query=True, allObjects=True)
                            self._panel_states[p] = was_visible
                            cmds.modelEditor(p, edit=True, allObjects=False)
                    except Exception:
                        pass
        except Exception:
            pass
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 1. Restore Viewport 3D model panels
        if self._panel_states:
            for p, was_vis in self._panel_states.items():
                try:
                    if cmds.modelEditor(p, query=True, exists=True):
                        cmds.modelEditor(p, edit=True, allObjects=was_vis)
                except Exception:
                    pass
        try:
            if hasattr(cmds, "ogs") and not cmds.about(batch=True):
                cmds.ogs(pause=False)
        except Exception:
            pass

        # 2. Restore Cached Playback
        if self._prev_cache_state is not None:
            try:
                if hasattr(cmds, "evaluator") and not cmds.about(batch=True):
                    cmds.evaluator(enable=bool(self._prev_cache_state), name="cache")
            except Exception:
                pass

        # 3. Restore Maya Undo Queue state
        if self._prev_undo_state is not None:
            try:
                if hasattr(cmds, "undoInfo"):
                    cmds.undoInfo(stateWithoutFlush=self._prev_undo_state)
            except Exception:
                pass

        # 4. Restore original viewport selection (avoids dense wireframe highlight lag)
        try:
            if hasattr(cmds, "select") and hasattr(cmds, "objExists"):
                if self._prev_selection:
                    valid_sel = [n for n in self._prev_selection if cmds.objExists(n)]
                    if valid_sel:
                        cmds.select(valid_sel, replace=True)
                    else:
                        cmds.select(clear=True)
                else:
                    cmds.select(clear=True)
        except Exception:
            pass

        return False


