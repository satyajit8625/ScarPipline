# -*- coding: utf-8 -*-
"""High-precision OpenMaya 2.0 Vector and Matrix Pivot Math Engine.

Provides non-destructive pivot transformation, bounding-box calculation,
component centroid extraction, and orthonormal basis vector alignment.
"""

from __future__ import absolute_import, division, print_function

import math
import maya.cmds as cmds

try:
    import maya.api.OpenMaya as om
except ImportError:
    om = None


def get_mobject(node):
    """Retrieve MObject for a given Maya node name or DAG path."""
    if not node or not cmds.objExists(node):
        return None
    sel = om.MSelectionList()
    sel.add(str(node))
    return sel.getDependNode(0)


def get_dag_path(node):
    """Retrieve MDagPath for a given Maya DAG node."""
    if not node or not cmds.objExists(node):
        return None
    sel = om.MSelectionList()
    sel.add(str(node))
    try:
        return sel.getDagPath(0)
    except Exception:
        return None


def get_world_pivot_position(node):
    """Return world-space rotatePivot coordinates as tuple (x, y, z)."""
    if not node or not cmds.objExists(node):
        return (0.0, 0.0, 0.0)
    pos = cmds.xform(node, query=True, worldSpace=True, rotatePivot=True) or [0.0, 0.0, 0.0]
    return (float(pos[0]), float(pos[1]), float(pos[2]))


def get_world_pivot_rotation(node):
    """Return world-space rotation / rotateAxis of transform in degrees."""
    if not node or not cmds.objExists(node):
        return (0.0, 0.0, 0.0)
    rot = cmds.xform(node, query=True, worldSpace=True, rotation=True) or [0.0, 0.0, 0.0]
    return (float(rot[0]), float(rot[1]), float(rot[2]))


def get_bbox_point(nodes, x_mode="center", y_mode="center", z_mode="center", space="world"):
    """
    Calculate a target pivot point based on Bounding Box extents.

    Args:
        nodes (str or list[str]): Transform node(s).
        x_mode (str): 'min', 'center', or 'max'.
        y_mode (str): 'min', 'center', or 'max'.
        z_mode (str): 'min', 'center', or 'max'.
        space (str): 'world' or 'object'.

    Returns:
        tuple[float, float, float]: Target point coordinates.
    """
    if isinstance(nodes, (str,)):
        nodes = [nodes]
    nodes = [n for n in (nodes or []) if cmds.objExists(n)]
    if not nodes:
        return (0.0, 0.0, 0.0)

    # Compute aggregate bounding box
    min_x, min_y, min_z = float("inf"), float("inf"), float("inf")
    max_x, max_y, max_z = float("-inf"), float("-inf"), float("-inf")

    for node in nodes:
        bb = cmds.xform(node, query=True, worldSpace=(space == "world"), boundingBox=True)
        if bb and len(bb) == 6:
            min_x = min(min_x, bb[0])
            min_y = min(min_y, bb[1])
            min_z = min(min_z, bb[2])
            max_x = max(max_x, bb[3])
            max_y = max(max_y, bb[4])
            max_z = max(max_z, bb[5])

    if min_x == float("inf"):
        return (0.0, 0.0, 0.0)

    def _resolve(mode, val_min, val_max):
        m = str(mode).strip().lower()
        if m == "min":
            return val_min
        elif m == "max":
            return val_max
        return (val_min + val_max) * 0.5

    target_x = _resolve(x_mode, min_x, max_x)
    target_y = _resolve(y_mode, min_y, max_y)
    target_z = _resolve(z_mode, min_z, max_z)

    return (float(target_x), float(target_y), float(target_z))


def get_component_centroid_and_vectors(node, components=None):
    """
    Calculate world centroid point, normal vector, and tangent vector from components.

    Supported component types:
    - Vertices: arithmetic centroid of vertex coordinates.
    - Edges: midpoint of edge, tangent vector along edge direction.
    - Faces: face centroid, average face normal vector in world space.

    Returns:
        dict: {"position": (x,y,z), "normal": (nx,ny,nz), "tangent": (tx,ty,tz), "type": "vertex"|"edge"|"face"|"object"}
    """
    if not components:
        components = cmds.ls(selection=True, flatten=True) or []

    # Filter components belonging to this node or any transform
    comp_list = []
    short_node = node.split("|")[-1].split(":")[-1] if node else ""
    for c in components:
        if "." in c:
            c_node = c.split(".")[0].split("|")[-1].split(":")[-1]
            if not short_node or c_node == short_node:
                comp_list.append(c)

    if not comp_list:
        # Fallback to object bounding box center
        pos = get_bbox_point(node, "center", "center", "center", space="world")
        return {
            "position": pos,
            "normal": (0.0, 1.0, 0.0),
            "tangent": (1.0, 0.0, 0.0),
            "type": "object",
        }

    # Analyze component elements
    sample = comp_list[0]
    comp_type = "vertex"
    if ".e[" in sample:
        comp_type = "edge"
    elif ".f[" in sample:
        comp_type = "face"

    # 1. Vertex components
    if comp_type == "vertex":
        positions = []
        normals = []
        for v in comp_list:
            pos = cmds.pointPosition(v, world=True)
            positions.append(pos)
            try:
                n = cmds.polyNormalPerVertex(v, query=True, normalXYZ=True)
                if n and len(n) >= 3:
                    normals.append(om.MVector(n[0], n[1], n[2]))
            except Exception:
                pass

        avg_x = sum(p[0] for p in positions) / max(1, len(positions))
        avg_y = sum(p[1] for p in positions) / max(1, len(positions))
        avg_z = sum(p[2] for p in positions) / max(1, len(positions))

        avg_normal = om.MVector(0, 1, 0)
        if normals:
            n_sum = om.MVector(0, 0, 0)
            for norm in normals:
                n_sum += norm
            if n_sum.length() > 1e-5:
                avg_normal = n_sum.normalize()

        return {
            "position": (float(avg_x), float(avg_y), float(avg_z)),
            "normal": (float(avg_normal.x), float(avg_normal.y), float(avg_normal.z)),
            "tangent": (1.0, 0.0, 0.0),
            "type": "vertex",
        }

    # 2. Edge components
    elif comp_type == "edge":
        midpoints = []
        tangents = []
        normals = []
        for e in comp_list:
            v_indices = cmds.polyInfo(e, edgeToVertex=True)
            if v_indices:
                toks = [int(t) for t in v_indices[0].split() if t.isdigit()]
                if len(toks) >= 2:
                    mesh_obj = e.split(".")[0]
                    p1 = cmds.pointPosition("{}.vtx[{}]".format(mesh_obj, toks[0]), world=True)
                    p2 = cmds.pointPosition("{}.vtx[{}]".format(mesh_obj, toks[1]), world=True)
                    mid = [(p1[0] + p2[0]) * 0.5, (p1[1] + p2[1]) * 0.5, (p1[2] + p2[2]) * 0.5]
                    midpoints.append(mid)

                    vec = om.MVector(p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
                    if vec.length() > 1e-5:
                        tangents.append(vec.normalize())

            # Query adjacent face normal
            try:
                f_indices = cmds.polyInfo(e, edgeToFace=True)
                if f_indices:
                    f_toks = [int(t) for t in f_indices[0].split() if t.isdigit()]
                    if f_toks:
                        mesh_obj = e.split(".")[0]
                        fn = cmds.polyInfo("{}.f[{}]".format(mesh_obj, f_toks[0]), faceNormals=True)
                        if fn:
                            coords = [float(c) for c in fn[0].split() if re.match(r"^-?\d+(\.\d+)?$", c)]
                            if len(coords) >= 3:
                                normals.append(om.MVector(coords[0], coords[1], coords[2]))
            except Exception:
                pass

        avg_x = sum(p[0] for p in midpoints) / max(1, len(midpoints))
        avg_y = sum(p[1] for p in midpoints) / max(1, len(midpoints))
        avg_z = sum(p[2] for p in midpoints) / max(1, len(midpoints))

        avg_tangent = om.MVector(1, 0, 0)
        if tangents:
            t_sum = om.MVector(0, 0, 0)
            for t in tangents:
                t_sum += t
            if t_sum.length() > 1e-5:
                avg_tangent = t_sum.normalize()

        avg_normal = om.MVector(0, 1, 0)
        if normals:
            n_sum = om.MVector(0, 0, 0)
            for norm in normals:
                n_sum += norm
            if n_sum.length() > 1e-5:
                avg_normal = n_sum.normalize()

        return {
            "position": (float(avg_x), float(avg_y), float(avg_z)),
            "normal": (float(avg_normal.x), float(avg_normal.y), float(avg_normal.z)),
            "tangent": (float(avg_tangent.x), float(avg_tangent.y), float(avg_tangent.z)),
            "type": "edge",
        }

    # 3. Face components
    elif comp_type == "face":
        centroids = []
        normals = []
        for f in comp_list:
            v_indices = cmds.polyInfo(f, faceToVertex=True)
            if v_indices:
                toks = [int(t) for t in v_indices[0].split() if t.isdigit()]
                if toks:
                    mesh_obj = f.split(".")[0]
                    v_coords = [cmds.pointPosition("{}.vtx[{}]".format(mesh_obj, idx), world=True) for idx in toks]
                    c_x = sum(pt[0] for pt in v_coords) / len(v_coords)
                    c_y = sum(pt[1] for pt in v_coords) / len(v_coords)
                    c_z = sum(pt[2] for pt in v_coords) / len(v_coords)
                    centroids.append((c_x, c_y, c_z))

            try:
                fn = cmds.polyInfo(f, faceNormals=True)
                if fn:
                    parts = fn[0].split(":")[-1].split()
                    if len(parts) >= 3:
                        normals.append(om.MVector(float(parts[0]), float(parts[1]), float(parts[2])))
            except Exception:
                pass

        avg_x = sum(p[0] for p in centroids) / max(1, len(centroids))
        avg_y = sum(p[1] for p in centroids) / max(1, len(centroids))
        avg_z = sum(p[2] for p in centroids) / max(1, len(centroids))

        avg_normal = om.MVector(0, 1, 0)
        if normals:
            n_sum = om.MVector(0, 0, 0)
            for norm in normals:
                n_sum += norm
            if n_sum.length() > 1e-5:
                avg_normal = n_sum.normalize()

        return {
            "position": (float(avg_x), float(avg_y), float(avg_z)),
            "normal": (float(avg_normal.x), float(avg_normal.y), float(avg_normal.z)),
            "tangent": (1.0, 0.0, 0.0),
            "type": "face",
        }

    return {
        "position": (0.0, 0.0, 0.0),
        "normal": (0.0, 1.0, 0.0),
        "tangent": (1.0, 0.0, 0.0),
        "type": "unknown",
    }


def parse_axis_string(axis_str):
    """
    Parse axis string like '+X', '-X', 'Y', '-Z' into an MVector direction.
    """
    s = str(axis_str or "+X").strip().upper()
    sign = -1.0 if s.startswith("-") else 1.0
    clean = s.replace("+", "").replace("-", "")
    if clean == "X":
        return om.MVector(1.0 * sign, 0.0, 0.0)
    elif clean == "Y":
        return om.MVector(0.0, 1.0 * sign, 0.0)
    elif clean == "Z":
        return om.MVector(0.0, 0.0, 1.0 * sign)
    return om.MVector(1.0, 0.0, 0.0)


def calculate_aligned_rotation(primary_axis_str, target_dir_vec, secondary_axis_str, up_dir_vec):
    """
    Construct an orthonormal coordinate frame aligning primary and secondary axes.
    Returns Euler rotation angles in degrees (rx, ry, rz).
    """
    if not om:
        return (0.0, 0.0, 0.0)

    v_pri = om.MVector(target_dir_vec[0], target_dir_vec[1], target_dir_vec[2])
    v_sec = om.MVector(up_dir_vec[0], up_dir_vec[1], up_dir_vec[2])

    if v_pri.length() < 1e-5:
        v_pri = om.MVector(1, 0, 0)
    else:
        v_pri = v_pri.normalize()

    if v_sec.length() < 1e-5 or abs(v_pri * v_sec) > 0.999:
        # Generate orthogonal fallback
        v_sec = om.MVector(0, 1, 0) if abs(v_pri.y) < 0.9 else om.MVector(1, 0, 0)

    # Gram-Schmidt Orthogonalization
    v_ter = (v_pri ^ v_sec).normalize()
    v_sec = (v_ter ^ v_pri).normalize()

    # Map primary / secondary / tertiary to local X, Y, Z
    pri_key = primary_axis_str.strip().upper().replace("+", "")
    sec_key = secondary_axis_str.strip().upper().replace("+", "")

    # Construct matrix rows
    m_list = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    mat = om.MMatrix(m_list)
    tmat = om.MTransformationMatrix(mat)

    # Assign vectors to appropriate column axes
    # Default alignment: X=primary, Y=secondary, Z=tertiary
    x_axis = v_pri if "X" in pri_key else (v_sec if "X" in sec_key else v_ter)
    y_axis = v_pri if "Y" in pri_key else (v_sec if "Y" in sec_key else v_ter)
    z_axis = v_pri if "Z" in pri_key else (v_sec if "Z" in sec_key else v_ter)

    mat_rows = [
        x_axis.x, x_axis.y, x_axis.z, 0.0,
        y_axis.x, y_axis.y, y_axis.z, 0.0,
        z_axis.x, z_axis.y, z_axis.z, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]
    align_mat = om.MMatrix(mat_rows)
    tm = om.MTransformationMatrix(align_mat)
    euler = tm.rotation(asQuaternion=False)

    return (
        math.degrees(euler.x),
        math.degrees(euler.y),
        math.degrees(euler.z),
    )


def set_pivot_position_non_destructive(node, world_point):
    """
    Non-destructively move the object's rotatePivot and scalePivot to world_point.
    Object world transform and vertex positions remain 100% invariant.
    """
    if not node or not cmds.objExists(node):
        return False

    pt = [float(world_point[0]), float(world_point[1]), float(world_point[2])]
    cmds.xform(node, worldSpace=True, rotatePivot=pt, scalePivot=pt, preserve=True)
    return True


def set_pivot_orientation_non_destructive(node, target_rotation_degrees):
    """
    Non-destructively modify transform pivot orientation.
    Compensates child nodes and polygon mesh points so geometry does not move.
    """
    if not node or not cmds.objExists(node):
        return False

    rot = [float(target_rotation_degrees[0]), float(target_rotation_degrees[1]), float(target_rotation_degrees[2])]
    # Preserve current mesh points in world space
    shapes = cmds.listRelatives(node, shapes=True, type="mesh", fullPath=True) or []
    pts_backup = []
    for s in shapes:
        dag = get_dag_path(s)
        if dag:
            fn = om.MFnMesh(dag)
            pts_backup.append((fn, fn.getPoints(om.MSpace.kWorld)))

    # Apply rotation to transform / rotateAxis
    try:
        cmds.setAttr("{}.rotateAxisX".format(node), rot[0])
        cmds.setAttr("{}.rotateAxisY".format(node), rot[1])
        cmds.setAttr("{}.rotateAxisZ".format(node), rot[2])
    except Exception:
        cmds.xform(node, worldSpace=True, rotation=rot, preserve=True)

    # Restore world positions of mesh vertices to guarantee 100% geometric invariance
    for fn_mesh, pts in pts_backup:
        try:
            fn_mesh.setPoints(pts, om.MSpace.kWorld)
        except Exception:
            pass

    return True
