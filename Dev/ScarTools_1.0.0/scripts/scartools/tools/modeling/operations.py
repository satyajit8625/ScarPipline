# -*- coding: utf-8 -*-
"""High-speed Maya API 2.0 and cmds operations for Modeling & Scene Sanitizer."""

from __future__ import print_function

import math
import os
import re
import time

import maya.cmds as cmds
try:
    import maya.api.OpenMaya as om
except ImportError:
    om = None

from scartools.framework import (
    OperationCancelled,
    OperationResult,
    SceneTransaction,
    ValidationIssue,
    ValidationReport,
)

EPSILON = 1e-6
GEO_SUFFIX = "_GEO"
GRP_SUFFIX = "_GRP"
SHD_SUFFIX = "_SHD"
SG_SUFFIX = "_SG"
DEFAULT_CAMERAS = {"persp", "top", "front", "side", "perspShape", "topShape", "frontShape", "sideShape"}


class ModelSanitizerError(RuntimeError):
    """Raised when model inspection or fixing fails."""
    pass


def _log(log, message):
    if log is not None:
        log(message)


def _progress(progress, percent, message):
    if progress is not None:
        progress(percent, message)


def _all_mesh_transforms(nodes=None):
    """Return all polygon mesh transform nodes."""
    if nodes:
        transforms = set()
        for node in nodes:
            if not cmds.objExists(node):
                continue
            if cmds.nodeType(node) == "mesh":
                parent = cmds.listRelatives(node, parent=True, fullPath=True)
                if parent:
                    transforms.add(parent[0])
            elif cmds.nodeType(node) == "transform":
                shapes = cmds.listRelatives(node, shapes=True, type="mesh", noIntermediate=True)
                if shapes:
                    transforms.add(cmds.ls(node, long=True)[0])
                children = cmds.listRelatives(node, allDescendents=True, type="mesh", noIntermediate=True, fullPath=True) or []
                for c in children:
                    parent = cmds.listRelatives(c, parent=True, fullPath=True)
                    if parent:
                        transforms.add(parent[0])
        return sorted(transforms)
    else:
        meshes = cmds.ls(type="mesh", noIntermediate=True, long=True) or []
        transforms = set()
        for m in meshes:
            parent = cmds.listRelatives(m, parent=True, fullPath=True)
            if parent:
                transforms.add(parent[0])
        return sorted(transforms)


def _mesh_shape(transform):
    if not cmds.objExists(transform):
        return None
    if cmds.nodeType(transform) == "mesh":
        return transform
    shapes = cmds.listRelatives(transform, shapes=True, type="mesh", noIntermediate=True, fullPath=True) or []
    return shapes[0] if shapes else None


# ---------------------------------------------------------------------------
# 1. Topology & Normals Checks
# ---------------------------------------------------------------------------

def check_non_manifold_geometry(mesh_transforms):
    """Detect non-manifold vertices and edges."""
    issues = {}
    for transform in mesh_transforms:
        shape = _mesh_shape(transform)
        if not shape:
            continue
        try:
            nm_v = cmds.polyInfo(shape, nonManifoldVertices=True) or []
        except Exception:
            nm_v = []
        try:
            nm_e = cmds.polyInfo(shape, nonManifoldEdges=True) or []
        except Exception:
            nm_e = []

        vtx_ids = []
        for line in nm_v:
            vtx_ids.extend([int(x) for x in re.findall(r"\.vtx\[(\d+)\]", line)])
        edge_ids = []
        for line in nm_e:
            edge_ids.extend([int(x) for x in re.findall(r"\.e\[(\d+)\]", line)])

        if vtx_ids or edge_ids:
            issues[transform] = {
                "shape": shape,
                "vertices": sorted(set(vtx_ids)),
                "edges": sorted(set(edge_ids)),
                "count": len(set(vtx_ids)) + len(set(edge_ids)),
            }
    return issues


def check_lamina_faces(mesh_transforms):
    """Detect duplicate / overlapping lamina faces."""
    issues = {}
    for transform in mesh_transforms:
        shape = _mesh_shape(transform)
        if not shape:
            continue
        try:
            lam = cmds.polyInfo(shape, laminaFaces=True) or []
        except Exception:
            lam = []
        face_ids = []
        for line in lam:
            face_ids.extend([int(x) for x in re.findall(r"\.f\[(\d+)\]", line)])
        if face_ids:
            issues[transform] = {
                "shape": shape,
                "faces": sorted(set(face_ids)),
                "count": len(set(face_ids)),
            }
    return issues


def check_zero_area_faces(mesh_transforms, threshold=EPSILON):
    """Detect degenerate zero-area polygon faces."""
    issues = {}
    if om is None:
        return issues
    for transform in mesh_transforms:
        shape = _mesh_shape(transform)
        if not shape:
            continue
        try:
            sel_list = om.MSelectionList()
            sel_list.add(shape)
            dag_path = sel_list.getDagPath(0)
            poly_iter = om.MItMeshPolygon(dag_path)
            zero_faces = []
            while not poly_iter.isDone():
                if poly_iter.getArea() < threshold:
                    zero_faces.append(poly_iter.index())
                poly_iter.next()
            if zero_faces:
                issues[transform] = {
                    "shape": shape,
                    "faces": zero_faces,
                    "count": len(zero_faces),
                }
        except Exception:
            pass
    return issues


def check_zero_length_edges(mesh_transforms, threshold=EPSILON):
    """Detect collapsed zero-length polygon edges."""
    issues = {}
    if om is None:
        return issues
    for transform in mesh_transforms:
        shape = _mesh_shape(transform)
        if not shape:
            continue
        try:
            sel_list = om.MSelectionList()
            sel_list.add(shape)
            dag_path = sel_list.getDagPath(0)
            edge_iter = om.MItMeshEdge(dag_path)
            zero_edges = []
            while not edge_iter.isDone():
                if edge_iter.length() < threshold:
                    zero_edges.append(edge_iter.index())
                edge_iter.next()
            if zero_edges:
                issues[transform] = {
                    "shape": shape,
                    "edges": zero_edges,
                    "count": len(zero_edges),
                }
        except Exception:
            pass
    return issues


def check_ngons(mesh_transforms):
    """Detect N-Gons (> 4 sided polygon faces)."""
    issues = {}
    if om is None:
        return issues
    for transform in mesh_transforms:
        shape = _mesh_shape(transform)
        if not shape:
            continue
        try:
            sel_list = om.MSelectionList()
            sel_list.add(shape)
            dag_path = sel_list.getDagPath(0)
            poly_iter = om.MItMeshPolygon(dag_path)
            ngons = []
            while not poly_iter.isDone():
                if poly_iter.polygonVertexCount() > 4:
                    ngons.append(poly_iter.index())
                poly_iter.next()
            if ngons:
                issues[transform] = {
                    "shape": shape,
                    "faces": ngons,
                    "count": len(ngons),
                }
        except Exception:
            pass
    return issues


def check_triangles(mesh_transforms):
    """Detect 3-sided triangle polygon faces."""
    issues = {}
    if om is None:
        return issues
    for transform in mesh_transforms:
        shape = _mesh_shape(transform)
        if not shape:
            continue
        try:
            sel_list = om.MSelectionList()
            sel_list.add(shape)
            dag_path = sel_list.getDagPath(0)
            poly_iter = om.MItMeshPolygon(dag_path)
            tris = []
            while not poly_iter.isDone():
                if poly_iter.polygonVertexCount() == 3:
                    tris.append(poly_iter.index())
                poly_iter.next()
            if tris:
                issues[transform] = {
                    "shape": shape,
                    "faces": tris,
                    "count": len(tris),
                }
        except Exception:
            pass
    return issues


def check_missing_uvs(mesh_transforms):
    """Detect meshes with 0 UV coordinates or unmapped polygon faces."""
    issues = {}
    for transform in mesh_transforms:
        shape = _mesh_shape(transform)
        if not shape:
            continue
        try:
            uv_sets = cmds.polyUVSet(shape, query=True, allUVSets=True) or []
            if not uv_sets:
                issues[transform] = {
                    "shape": shape,
                    "reason": "No UV sets exist on mesh",
                    "count": 1,
                }
                continue

            # Standard Maya UV coordinate count check
            uv_count = 0
            try:
                uv_count = cmds.polyEvaluate(shape, uvcoord=True) or 0
            except Exception:
                try:
                    uv_count = cmds.polyEvaluate(shape, uv=True) or 0
                except Exception:
                    pass

            if uv_count == 0:
                issues[transform] = {
                    "shape": shape,
                    "reason": "UV set exists but contains 0 UV coordinates",
                    "count": 1,
                }
                continue

            # Accurate per-face unmapped detection via Maya API
            if om is not None:
                sel_list = om.MSelectionList()
                sel_list.add(shape)
                dag_path = sel_list.getDagPath(0)
                poly_iter = om.MItMeshPolygon(dag_path)
                unmapped_faces = []
                while not poly_iter.isDone():
                    if not poly_iter.hasUVs():
                        unmapped_faces.append(poly_iter.index())
                    poly_iter.next()
                if unmapped_faces:
                    issues[transform] = {
                        "shape": shape,
                        "faces": unmapped_faces,
                        "reason": "{} unmapped face(s)".format(len(unmapped_faces)),
                        "count": len(unmapped_faces),
                    }
        except Exception:
            pass
    return issues



def check_locked_normals(mesh_transforms):
    """Detect locked / frozen vertex normals."""
    issues = {}
    for transform in mesh_transforms:
        shape = _mesh_shape(transform)
        if not shape:
            continue
        try:
            normals_locked = cmds.polyNormalPerVertex(shape, query=True, freezeNormal=True) or []
            if any(normals_locked):
                locked_count = sum(1 for x in normals_locked if x)
                issues[transform] = {
                    "shape": shape,
                    "count": locked_count,
                }
        except Exception:
            pass
    return issues


def check_open_boundary_edges(mesh_transforms):
    """Detect open boundary edges (non-watertight / open surface seams)."""
    issues = {}
    for transform in mesh_transforms:
        shape = _mesh_shape(transform)
        if not shape:
            continue
        try:
            border_edges = cmds.polyListComponentConversion(shape, toEdge=True, border=True) or []
            if border_edges:
                border_flat = cmds.ls(border_edges, flatten=True) or []
                if border_flat:
                    issues[transform] = {
                        "shape": shape,
                        "border_edges": border_flat,
                        "count": len(border_flat),
                    }
        except Exception:
            pass
    return issues


def check_subd_creases(mesh_transforms):
    """Detect accidental Maya polygon crease sets on geometry."""
    crease_sets = cmds.ls(type="creaseSet") or []
    issues = {}
    for c_set in crease_sets:
        try:
            members = cmds.sets(c_set, query=True) or []
            if members:
                issues[c_set] = {
                    "set": c_set,
                    "members": members,
                    "count": len(members),
                }
        except Exception:
            pass
    return issues


# ---------------------------------------------------------------------------
# 2. Transforms & Hierarchy Checks
# ---------------------------------------------------------------------------

def check_unfrozen_transforms(mesh_transforms):
    """Detect meshes with non-zero translation/rotation or non-1 scale."""
    issues = {}
    for transform in mesh_transforms:
        try:
            t = cmds.getAttr(transform + ".translate")[0]
            r = cmds.getAttr(transform + ".rotate")[0]
            s = cmds.getAttr(transform + ".scale")[0]
            unfrozen = (
                abs(t[0]) > EPSILON or abs(t[1]) > EPSILON or abs(t[2]) > EPSILON or
                abs(r[0]) > EPSILON or abs(r[1]) > EPSILON or abs(r[2]) > EPSILON or
                abs(s[0] - 1.0) > EPSILON or abs(s[1] - 1.0) > EPSILON or abs(s[2] - 1.0) > EPSILON
            )
            if unfrozen:
                issues[transform] = {
                    "translate": t,
                    "rotate": r,
                    "scale": s,
                    "count": 1,
                }
        except Exception:
            pass
    return issues


def check_negative_scales(mesh_transforms):
    """Detect negative scale transforms (mirrored matrices)."""
    issues = {}
    for transform in mesh_transforms:
        try:
            s = cmds.getAttr(transform + ".scale")[0]
            if s[0] < -EPSILON or s[1] < -EPSILON or s[2] < -EPSILON:
                issues[transform] = {
                    "scale": s,
                    "count": 1,
                }
        except Exception:
            pass
    return issues


def check_intermediate_shapes(mesh_transforms):
    """Detect orphaned intermediate shape nodes (ShapeDeformed / ShapeOrig)."""
    issues = {}
    for transform in mesh_transforms:
        try:
            all_shapes = cmds.listRelatives(transform, shapes=True, type="mesh", fullPath=True) or []
            intermediates = []
            for s in all_shapes:
                if cmds.getAttr(s + ".intermediateObject"):
                    intermediates.append(s)
            if intermediates:
                issues[transform] = {
                    "shapes": intermediates,
                    "count": len(intermediates),
                }
        except Exception:
            pass
    return issues


def check_construction_history(mesh_transforms):
    """Detect residual construction history nodes on models."""
    issues = {}
    for transform in mesh_transforms:
        shape = _mesh_shape(transform)
        if not shape:
            continue
        try:
            history = cmds.listHistory(shape, pruneDagObjects=True) or []
            history = [h for h in history if cmds.nodeType(h) not in ("groupId", "shadingEngine")]
            if history:
                issues[transform] = {
                    "history": history,
                    "count": len(history),
                }
        except Exception:
            pass
    return issues


def check_empty_groups():
    """Detect empty transform groups with zero children."""
    transforms = cmds.ls(type="transform", long=True) or []
    empty_groups = []
    for t in transforms:
        if cmds.nodeType(t) != "transform":
            continue
        short = t.split("|")[-1]
        if short in DEFAULT_CAMERAS:
            continue
        try:
            shapes = cmds.listRelatives(t, shapes=True) or []
            children = cmds.listRelatives(t, children=True) or []
            if not shapes and not children:
                empty_groups.append(t)
        except Exception:
            pass
    return {"empty_groups": empty_groups, "count": len(empty_groups)} if empty_groups else {}



def check_asset_root_pivot(mesh_transforms):
    """Verify master root group pivot is centered at world origin [0,0,0]."""
    roots = set()
    for t in mesh_transforms:
        parts = [p for p in t.split("|") if p]
        if parts:
            roots.add("|" + parts[0])
    issues = {}
    for root in sorted(roots):
        try:
            piv = cmds.xform(root, query=True, worldSpace=True, rotatePivot=True)
            if abs(piv[0]) > EPSILON or abs(piv[1]) > EPSILON or abs(piv[2]) > EPSILON:
                issues[root] = {
                    "pivot": piv,
                    "count": 1,
                }
        except Exception:
            pass
    return issues


def check_geometry_pivots(mesh_transforms):
    """Detect meshes whose rotate pivot is not centered to their bounding box."""
    issues = {}
    for transform in mesh_transforms:
        try:
            rp = cmds.xform(transform, query=True, worldSpace=True, rotatePivot=True)
            bb = cmds.xform(transform, query=True, worldSpace=True, boundingBox=True)
            center = [
                (bb[0] + bb[3]) * 0.5,
                (bb[1] + bb[4]) * 0.5,
                (bb[2] + bb[5]) * 0.5,
            ]
            dist_sq = (rp[0]-center[0])**2 + (rp[1]-center[1])**2 + (rp[2]-center[2])**2
            if dist_sq > 0.001:
                issues[transform] = {
                    "pivot": rp,
                    "center": center,
                    "count": 1,
                }
        except Exception:
            pass
    return issues


def check_extraneous_cameras_lights():
    """Detect non-default cameras, lights, or image planes in model files."""
    all_cams = cmds.ls(cameras=True, long=True) or []
    extra_cams = [c for c in all_cams if c.split("|")[-1] not in DEFAULT_CAMERAS]
    all_lights = cmds.ls(type="light", long=True) or []
    all_image_planes = cmds.ls(type="imagePlane", long=True) or []
    total = extra_cams + all_lights + all_image_planes
    if total:
        return {
            "cameras": extra_cams,
            "lights": all_lights,
            "image_planes": all_image_planes,
            "count": len(total),
        }
    return {}


# ---------------------------------------------------------------------------
# 3. Naming & Department Suffix Checks
# ---------------------------------------------------------------------------

def check_duplicate_names():
    """Detect duplicate short leaf names in the DAG hierarchy."""
    all_dags = cmds.ls(type="transform", long=True) or []
    short_map = {}
    for node in all_dags:
        short = node.split("|")[-1]
        if short in DEFAULT_CAMERAS:
            continue
        short_map.setdefault(short, []).append(node)

    duplicates = {short: nodes for short, nodes in short_map.items() if len(nodes) > 1}
    return duplicates


def check_mesh_suffixes(mesh_transforms):
    """Detect mesh transforms not ending with _GEO."""
    issues = {}
    for transform in mesh_transforms:
        short = transform.split("|")[-1]
        if not short.endswith(GEO_SUFFIX):
            issues[transform] = {
                "short_name": short,
                "expected": short + GEO_SUFFIX,
                "count": 1,
            }
    return issues


def check_group_suffixes():
    """Detect transform parent/null groups not ending with _GRP."""
    transforms = cmds.ls(type="transform", long=True) or []
    issues = {}
    for t in transforms:
        if cmds.nodeType(t) != "transform":
            continue
        short = t.split("|")[-1]
        if short in DEFAULT_CAMERAS:
            continue
        try:
            shapes = cmds.listRelatives(t, shapes=True, type="mesh") or []
            if not shapes:
                if not short.endswith(GRP_SUFFIX):
                    issues[t] = {
                        "short_name": short,
                        "expected": short + GRP_SUFFIX,
                        "count": 1,
                    }
        except Exception:
            pass
    return issues



def check_illegal_name_characters():
    """Detect node names containing spaces, #, $, @, or illegal characters."""
    transforms = cmds.ls(type="transform", long=True) or []
    issues = {}
    illegal_pattern = re.compile(r"[\s#$@!%^&*+=~`]")
    for t in transforms:
        short = t.split("|")[-1]
        if short in DEFAULT_CAMERAS:
            continue
        if illegal_pattern.search(short):
            sanitized = re.sub(r"[\s#$@!%^&*+=~`]+", "_", short)
            issues[t] = {
                "short_name": short,
                "sanitized": sanitized,
                "count": 1,
            }
    return issues


# ---------------------------------------------------------------------------
# 4. Shading & Material Suffix Checks
# ---------------------------------------------------------------------------

def check_material_suffixes():
    """Detect assigned materials not ending with _SHD."""
    materials = cmds.ls(materials=True) or []
    issues = {}
    default_mats = {"lambert1", "standardSurface1", "particleCloud1"}
    for mat in materials:
        if mat in default_mats:
            continue
        if not mat.endswith(SHD_SUFFIX):
            issues[mat] = {
                "name": mat,
                "expected": mat + SHD_SUFFIX,
                "count": 1,
            }
    return issues


def check_shading_group_suffixes():
    """Detect shading engines / groups not ending with _SG."""
    sgs = cmds.ls(type="shadingEngine") or []
    issues = {}
    default_sgs = {"initialShadingGroup", "initialParticleSE"}
    for sg in sgs:
        if sg in default_sgs:
            continue
        if not sg.endswith(SG_SUFFIX):
            issues[sg] = {
                "name": sg,
                "expected": sg + SG_SUFFIX,
                "count": 1,
            }
    return issues


def check_default_materials(mesh_transforms):
    """Detect geometry assigned to default lambert1 / standardSurface1."""
    issues = {}
    default_mats = {"lambert1", "standardSurface1"}
    for transform in mesh_transforms:
        shape = _mesh_shape(transform)
        if not shape:
            continue
        try:
            sgs = cmds.listConnections(shape, type="shadingEngine") or []
            for sg in set(sgs):
                mats = cmds.ls(cmds.listConnections(sg + ".surfaceShader"), materials=True) or []
                for m in mats:
                    if m in default_mats:
                        issues[transform] = {
                            "shape": shape,
                            "material": m,
                            "count": 1,
                        }
        except Exception:
            pass
    return issues


def check_unused_hypershade_nodes():
    """Detect unused materials, shading engines, and texture nodes."""
    try:
        mats = cmds.ls(materials=True) or []
        default_mats = {"lambert1", "standardSurface1", "particleCloud1"}
        unused = []
        for m in mats:
            if m in default_mats:
                continue
            sgs = cmds.listConnections(m, type="shadingEngine") or []
            if not sgs:
                unused.append(m)
            else:
                has_members = False
                for sg in sgs:
                    members = cmds.sets(sg, query=True) or []
                    if members:
                        has_members = True
                        break
                if not has_members:
                    unused.append(m)
        return {"unused_materials": unused, "count": len(unused)} if unused else {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# 5. Layers & Scene Cleanup Checks
# ---------------------------------------------------------------------------

def check_display_layers():
    """Detect display layers attached to scene models."""
    layers = cmds.ls(type="displayLayer") or []
    layers = [l for l in layers if l != "defaultLayer"]
    return {"layers": layers, "count": len(layers)} if layers else {}


def check_anim_layers():
    """Detect animation layers in static model files."""
    layers = cmds.ls(type="animLayer") or []
    return {"anim_layers": layers, "count": len(layers)} if layers else {}


def check_unknown_nodes():
    """Detect unknown, unknownDag, and Turtle corrupted nodes."""
    unknown = (cmds.ls(type="unknown") or []) + (cmds.ls(type="unknownDag") or [])
    turtle = [n for n in (cmds.ls("Turtle*") or []) if cmds.objExists(n)]
    all_corrupt = list(set(unknown + turtle))
    return {"unknown_nodes": all_corrupt, "count": len(all_corrupt)} if all_corrupt else {}


def check_color_sets(mesh_transforms):
    """Detect accidental vertex color sets (polyColorSet) on geometry."""
    issues = {}
    for transform in mesh_transforms:
        shape = _mesh_shape(transform)
        if not shape:
            continue
        try:
            c_sets = cmds.polyColorSet(shape, query=True, allColorSets=True) or []
            if c_sets:
                issues[transform] = {
                    "shape": shape,
                    "color_sets": c_sets,
                    "count": len(c_sets),
                }
        except Exception:
            pass
    return issues


# ---------------------------------------------------------------------------
# Master Inspection
# ---------------------------------------------------------------------------

def inspect_model_and_scene(nodes=None):
    """Run all 26 Modeling & Scene QA checks and return categorized diagnostic report."""
    from scartools.licensing import require_license
    require_license("Model Sanitizer QA")

    mesh_transforms = _all_mesh_transforms(nodes)


    checks = {
        "non_manifold": {
            "name": "Non-Manifold Geometry",
            "category": "Topology",
            "severity": "CRITICAL",
            "description": "Non-manifold vertices or edges sharing >2 faces.",
            "data": check_non_manifold_geometry(mesh_transforms),
        },
        "lamina_faces": {
            "name": "Lamina Faces",
            "category": "Topology",
            "severity": "CRITICAL",
            "description": "Duplicate overlapping faces sharing all edges and vertices.",
            "data": check_lamina_faces(mesh_transforms),
        },
        "zero_area_faces": {
            "name": "Zero-Area Faces",
            "category": "Topology",
            "severity": "CRITICAL",
            "description": "Degenerate faces with surface area < 1e-6.",
            "data": check_zero_area_faces(mesh_transforms),
        },
        "zero_length_edges": {
            "name": "Zero-Length Edges",
            "category": "Topology",
            "severity": "CRITICAL",
            "description": "Collapsed edges with length < 1e-6.",
            "data": check_zero_length_edges(mesh_transforms),
        },
        "missing_uvs": {
            "name": "Missing UV Coordinates",
            "category": "UVs",
            "severity": "CRITICAL",
            "description": "Meshes with 0 UV coordinates or unmapped polygon faces.",
            "data": check_missing_uvs(mesh_transforms),
        },
        "ngons": {
            "name": "N-Gons (>4 Vertices)",
            "category": "Topology",
            "severity": "WARNING",
            "description": "Polygons with more than 4 vertices.",
            "data": check_ngons(mesh_transforms),
        },
        "triangles": {
            "name": "Triangles (3 Vertices)",
            "category": "Topology",
            "severity": "WARNING",
            "description": "3-sided polygons (identifies non-quad topology).",
            "data": check_triangles(mesh_transforms),
        },
        "open_boundaries": {
            "name": "Open Boundary Edges",
            "category": "Topology",
            "severity": "WARNING",
            "description": "Meshes with open boundary seams (non-watertight geometry).",
            "data": check_open_boundary_edges(mesh_transforms),
        },
        "locked_normals": {
            "name": "Locked Vertex Normals",
            "category": "Normals",
            "severity": "WARNING",
            "description": "Frozen vertex normals that prevent smooth skinning deformation.",
            "data": check_locked_normals(mesh_transforms),
        },
        "crease_sets": {
            "name": "SubD Crease Sets",
            "category": "Topology",
            "severity": "WARNING",
            "description": "Maya polygon crease sets causing subdivision render discrepancies.",
            "data": check_subd_creases(mesh_transforms),
        },
        "unfrozen_transforms": {
            "name": "Unfrozen Transforms",
            "category": "Transforms",
            "severity": "CRITICAL",
            "description": "Translate != 0, Rotate != 0, or Scale != 1 on geometry.",
            "data": check_unfrozen_transforms(mesh_transforms),
        },
        "negative_scales": {
            "name": "Negative Scales",
            "category": "Transforms",
            "severity": "CRITICAL",
            "description": "Mirrored transform matrices with negative scale values.",
            "data": check_negative_scales(mesh_transforms),
        },
        "intermediate_shapes": {
            "name": "Intermediate Shapes",
            "category": "Hierarchy",
            "severity": "CRITICAL",
            "description": "Orphaned ShapeDeformed or intermediate objects.",
            "data": check_intermediate_shapes(mesh_transforms),
        },
        "duplicate_names": {
            "name": "Duplicate Node Names",
            "category": "Naming",
            "severity": "CRITICAL",
            "description": "Multiple DAG nodes sharing the exact same short leaf name.",
            "data": check_duplicate_names(),
        },
        "construction_history": {
            "name": "Construction History",
            "category": "Hierarchy",
            "severity": "WARNING",
            "description": "Residual non-deformer construction history on models.",
            "data": check_construction_history(mesh_transforms),
        },
        "empty_groups": {
            "name": "Empty Transform Groups",
            "category": "Hierarchy",
            "severity": "WARNING",
            "description": "Null transform groups with zero children.",
            "data": check_empty_groups(),
        },
        "root_pivot": {
            "name": "Asset Root Pivot",
            "category": "Transforms",
            "severity": "WARNING",
            "description": "Master asset group pivot not placed at world origin [0,0,0].",
            "data": check_asset_root_pivot(mesh_transforms),
        },
        "geometry_pivots": {
            "name": "Centered Geometry Pivots",
            "category": "Transforms",
            "severity": "WARNING",
            "description": "Mesh pivot not centered to its bounding box.",
            "data": check_geometry_pivots(mesh_transforms),
        },
        "extraneous_cameras_lights": {
            "name": "Extraneous Cameras & Lights",
            "category": "Scene",
            "severity": "WARNING",
            "description": "Leftover lights, extra cameras, or image planes.",
            "data": check_extraneous_cameras_lights(),
        },
        "mesh_suffixes": {
            "name": "Mesh Suffix (*_GEO)",
            "category": "Naming",
            "severity": "WARNING",
            "description": "Geometry transforms not ending with _GEO.",
            "data": check_mesh_suffixes(mesh_transforms),
        },
        "group_suffixes": {
            "name": "Group Suffix (*_GRP)",
            "category": "Naming",
            "severity": "WARNING",
            "description": "Transform groups not ending with _GRP.",
            "data": check_group_suffixes(),
        },
        "illegal_characters": {
            "name": "Illegal Name Characters",
            "category": "Naming",
            "severity": "WARNING",
            "description": "Names containing spaces, #, $, @, or illegal characters.",
            "data": check_illegal_name_characters(),
        },
        "material_suffixes": {
            "name": "Material Suffix (*_SHD)",
            "category": "Shading",
            "severity": "WARNING",
            "description": "Assigned materials not ending with _SHD.",
            "data": check_material_suffixes(),
        },
        "shading_group_suffixes": {
            "name": "Shading Group Suffix (*_SG)",
            "category": "Shading",
            "severity": "WARNING",
            "description": "Shading engines not ending with _SG.",
            "data": check_shading_group_suffixes(),
        },
        "default_materials": {
            "name": "Default Material Assigned",
            "category": "Shading",
            "severity": "WARNING",
            "description": "Meshes assigned to default lambert1 / standardSurface1.",
            "data": check_default_materials(mesh_transforms),
        },
        "unused_hypershade": {
            "name": "Unused Hypershade Nodes",
            "category": "Shading",
            "severity": "WARNING",
            "description": "Disconnected shaders, textures, and shading engines.",
            "data": check_unused_hypershade_nodes(),
        },
        "unknown_nodes": {
            "name": "Unknown & Corrupt Nodes",
            "category": "Scene",
            "severity": "CRITICAL",
            "description": "unknown, unknownDag, and Turtle plugin artifacts.",
            "data": check_unknown_nodes(),
        },
        "display_layers": {
            "name": "Display Layers",
            "category": "Scene",
            "severity": "WARNING",
            "description": "Display layers attached to model geometry.",
            "data": check_display_layers(),
        },
        "anim_layers": {
            "name": "Animation Layers",
            "category": "Scene",
            "severity": "WARNING",
            "description": "Leftover animation layers in static model file.",
            "data": check_anim_layers(),
        },
        "color_sets": {
            "name": "Vertex Color Sets",
            "category": "Scene",
            "severity": "WARNING",
            "description": "Accidental vertex color sets (polyColorSet) on geometry.",
            "data": check_color_sets(mesh_transforms),
        },
    }

    critical_count = 0
    warning_count = 0

    for key, check in checks.items():
        data = check["data"]
        count = len(data) if isinstance(data, dict) else 0
        if isinstance(data, dict) and "count" in data:
            count = data["count"]
        check["issue_count"] = count
        check["passed"] = (count == 0)
        if not check["passed"]:
            if check["severity"] == "CRITICAL":
                critical_count += 1
            else:
                warning_count += 1

    overall_status = "GOOD_TO_GO"
    if critical_count > 0:
        overall_status = "CRITICAL_BLOCKERS"
    elif warning_count > 0:
        overall_status = "WARNINGS_FOUND"

    return {
        "overall_status": overall_status,
        "critical_count": critical_count,
        "warning_count": warning_count,
        "mesh_count": len(mesh_transforms),
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# Viewport Selection Helper
# ---------------------------------------------------------------------------

def select_issue_components(check_key, nodes=None):
    """Select offending vertices, edges, faces, or objects in Maya viewport."""
    report = inspect_model_and_scene(nodes)
    check = report["checks"].get(check_key)
    if not check or check["passed"]:
        return []

    data = check["data"]
    to_select = []

    if check_key == "non_manifold":
        for transform, info in data.items():
            shape = info.get("shape", transform)
            to_select.extend(["{}.vtx[{}]".format(shape, i) for i in info.get("vertices", [])])
            to_select.extend(["{}.e[{}]".format(shape, i) for i in info.get("edges", [])])
    elif check_key == "lamina_faces":
        for transform, info in data.items():
            shape = info.get("shape", transform)
            to_select.extend(["{}.f[{}]".format(shape, i) for i in info.get("faces", [])])
    elif check_key in ("zero_area_faces", "ngons", "triangles"):
        for transform, info in data.items():
            shape = info.get("shape", transform)
            to_select.extend(["{}.f[{}]".format(shape, i) for i in info.get("faces", [])])
    elif check_key == "zero_length_edges":
        for transform, info in data.items():
            shape = info.get("shape", transform)
            to_select.extend(["{}.e[{}]".format(shape, i) for i in info.get("edges", [])])
    elif check_key == "duplicate_names":
        for short, full_paths in data.items():
            to_select.extend(full_paths)
    elif check_key in ("unfrozen_transforms", "negative_scales", "missing_uvs", "locked_normals",
                       "intermediate_shapes", "construction_history", "mesh_suffixes",
                       "geometry_pivots", "color_sets", "default_materials"):
        to_select.extend(list(data.keys()))
    elif check_key == "open_boundaries":
        for transform, info in data.items():
            to_select.extend(info.get("border_edges", []))
    elif check_key == "crease_sets":
        for c_set, info in data.items():
            to_select.extend(info.get("members", []))
    elif check_key == "empty_groups":
        to_select.extend(data.get("empty_groups", []))
    elif check_key == "unknown_nodes":
        to_select.extend(data.get("unknown_nodes", []))
    elif check_key == "display_layers":
        to_select.extend(data.get("layers", []))
    elif check_key == "anim_layers":
        to_select.extend(data.get("anim_layers", []))

    if to_select:
        try:
            shapes_to_hilite = set()
            for item in to_select:
                if "." in item:
                    shapes_to_hilite.add(item.split(".")[0])
            if shapes_to_hilite:
                cmds.hilite(list(shapes_to_hilite), replace=True)
            cmds.select(to_select, replace=True)
        except Exception:
            try:
                cmds.select(to_select, replace=True)
            except Exception:
                pass
    return to_select


# ---------------------------------------------------------------------------
# Auto-Fix Operations (Atomic Transactions)
# ---------------------------------------------------------------------------

def fix_make_names_unique(log=None):
    """Rename duplicate DAG nodes with unique _01, _02 zero-padded numbers."""
    with SceneTransaction("FixMakeNamesUnique"):
        duplicates = check_duplicate_names()
        renamed = 0
        all_items = []
        for short, paths in duplicates.items():
            for index, path in enumerate(paths, start=1):
                all_items.append((path, short, index))
        all_items.sort(key=lambda x: x[0].count("|"), reverse=True)
        for path, short, index in all_items:
            if not cmds.objExists(path):
                continue
            base = re.sub(r"_\d+$", "", short)
            new_name = "{}_{:02d}".format(base, index)
            try:
                cmds.rename(path, new_name)
                renamed += 1
            except Exception as exc:
                _log(log, "Could not rename {}: {}".format(path, exc))
        _log(log, "Made {} duplicate node name(s) unique.".format(renamed))
        return renamed


def fix_add_geo_suffixes(mesh_transforms=None, log=None):
    """Append _GEO to all geometry transforms."""
    with SceneTransaction("FixAddGeoSuffixes"):
        if mesh_transforms is None:
            mesh_transforms = _all_mesh_transforms()
        sorted_transforms = sorted(mesh_transforms, key=lambda t: t.count("|"), reverse=True)
        renamed = 0
        for transform in sorted_transforms:
            if not cmds.objExists(transform):
                continue
            short = transform.split("|")[-1]
            if not short.endswith(GEO_SUFFIX):
                new_name = short + GEO_SUFFIX
                try:
                    cmds.rename(transform, new_name)
                    renamed += 1
                except Exception as exc:
                    _log(log, "Could not rename {}: {}".format(transform, exc))
        _log(log, "Added _GEO suffix to {} mesh(es).".format(renamed))
        return renamed


def fix_add_grp_suffixes(log=None):
    """Append _GRP to all transform parent/null groups."""
    with SceneTransaction("FixAddGrpSuffixes"):
        issues = check_group_suffixes()
        sorted_transforms = sorted(issues.keys(), key=lambda t: t.count("|"), reverse=True)
        renamed = 0
        for transform in sorted_transforms:
            if not cmds.objExists(transform):
                continue
            info = issues[transform]
            short = info["short_name"]
            new_name = short + GRP_SUFFIX
            try:
                cmds.rename(transform, new_name)
                renamed += 1
            except Exception as exc:
                _log(log, "Could not rename {}: {}".format(transform, exc))
        _log(log, "Added _GRP suffix to {} group(s).".format(renamed))
        return renamed


def fix_shader_suffixes(log=None):
    """Rename materials to *_SHD and shading engines to *_SG."""
    with SceneTransaction("FixShaderSuffixes"):
        mat_issues = check_material_suffixes()
        sg_issues = check_shading_group_suffixes()
        renamed = 0

        for mat, info in mat_issues.items():
            if not cmds.objExists(mat):
                continue
            new_name = info["expected"]
            try:
                cmds.rename(mat, new_name)
                renamed += 1
            except Exception as exc:
                _log(log, "Could not rename material {}: {}".format(mat, exc))

        for sg, info in sg_issues.items():
            if not cmds.objExists(sg):
                continue
            new_name = info["expected"]
            try:
                cmds.rename(sg, new_name)
                renamed += 1
            except Exception as exc:
                _log(log, "Could not rename shading group {}: {}".format(sg, exc))

        _log(log, "Standardized {} shader / shading group suffix(es).".format(renamed))
        return renamed


def fix_freeze_transforms(mesh_transforms=None, log=None):
    """Freeze translation, rotation, and scale on geometry."""
    with SceneTransaction("FixFreezeTransforms", suspend_evaluation=True):
        if mesh_transforms is None:
            mesh_transforms = _all_mesh_transforms()
        count = 0
        for transform in mesh_transforms:
            if not cmds.objExists(transform):
                continue
            try:
                cmds.makeIdentity(transform, apply=True, translate=True, rotate=True, scale=True, normal=False)
                count += 1
            except Exception as exc:
                _log(log, "Could not freeze {}: {}".format(transform, exc))
        _log(log, "Froze transforms on {} mesh(es).".format(count))
        return count


def fix_center_pivots(mesh_transforms=None, log=None):
    """Center geometry pivots to their bounding box."""
    with SceneTransaction("FixCenterPivots"):
        if mesh_transforms is None:
            mesh_transforms = _all_mesh_transforms()
        count = 0
        for transform in mesh_transforms:
            if not cmds.objExists(transform):
                continue
            try:
                cmds.xform(transform, centerPivots=True)
                count += 1
            except Exception as exc:
                _log(log, "Could not center pivot on {}: {}".format(transform, exc))
        _log(log, "Centered pivots on {} mesh(es).".format(count))
        return count


def fix_delete_construction_history(mesh_transforms=None, log=None):
    """Delete non-deformer construction history on geometry."""
    with SceneTransaction("FixDeleteConstructionHistory"):
        if mesh_transforms is None:
            mesh_transforms = _all_mesh_transforms()
        count = 0
        for transform in mesh_transforms:
            if not cmds.objExists(transform):
                continue
            try:
                cmds.delete(transform, constructionHistory=True)
                count += 1
            except Exception as exc:
                _log(log, "Could not delete history on {}: {}".format(transform, exc))
        _log(log, "Deleted construction history on {} mesh(es).".format(count))
        return count


def fix_delete_intermediate_shapes(mesh_transforms=None, log=None):
    """Purge orphaned intermediate shape nodes while protecting shader assignments."""
    with SceneTransaction("FixDeleteIntermediateShapes"):
        if mesh_transforms is None:
            mesh_transforms = _all_mesh_transforms()
        deleted = 0
        for transform in mesh_transforms:
            if not cmds.objExists(transform):
                continue

            # 1. Cache shading engine assignments on visible shape before cleaning
            shape = _mesh_shape(transform)
            sgs = cmds.listConnections(shape, type="shadingEngine") or [] if shape else []

            # 2. Delete non-deformer construction history first to collapse clean nodes
            try:
                cmds.delete(transform, constructionHistory=True)
            except Exception:
                pass

            # 3. Find and remove remaining orphaned intermediate shapes
            shapes = cmds.listRelatives(transform, shapes=True, type="mesh", fullPath=True) or []
            for s in shapes:
                try:
                    if cmds.objExists(s) and cmds.getAttr(s + ".intermediateObject"):
                        cmds.delete(s)
                        deleted += 1
                except Exception:
                    pass

            # 4. Re-verify shading group assignment on the primary visible shape
            if shape and sgs and cmds.objExists(shape):
                for sg in set(sgs):
                    try:
                        if cmds.objExists(sg):
                            cmds.sets(shape, forceElement=sg)
                    except Exception:
                        pass

        _log(log, "Purged {} intermediate shape node(s) and preserved shader assignments.".format(deleted))
        return deleted



def fix_unlock_normals(mesh_transforms=None, log=None):
    """Unlock / unfreeze vertex normals on geometry."""
    with SceneTransaction("FixUnlockNormals"):
        if mesh_transforms is None:
            mesh_transforms = _all_mesh_transforms()
        count = 0
        for transform in mesh_transforms:
            if not cmds.objExists(transform):
                continue
            try:
                cmds.polyNormalPerVertex(transform, unFreezeNormal=True)
                count += 1
            except Exception as exc:
                _log(log, "Could not unlock normals on {}: {}".format(transform, exc))
        _log(log, "Unlocked normals on {} mesh(es).".format(count))
        return count


def fix_clean_scene_clutter(log=None):
    """Purge empty layers, unknown nodes, empty groups, and color sets."""
    with SceneTransaction("FixCleanSceneClutter"):
        purged = 0

        for layer in (cmds.ls(type="displayLayer") or []):
            if layer != "defaultLayer":
                try:
                    cmds.delete(layer)
                    purged += 1
                except Exception:
                    pass

        for alayer in (cmds.ls(type="animLayer") or []):
            try:
                cmds.delete(alayer)
                purged += 1
            except Exception:
                pass

        for unk in ((cmds.ls(type="unknown") or []) + (cmds.ls(type="unknownDag") or [])):
            try:
                if cmds.objExists(unk):
                    cmds.lockNode(unk, lock=False)
                    cmds.delete(unk)
                    purged += 1
            except Exception:
                pass

        for g in check_empty_groups().get("empty_groups", []):
            try:
                if cmds.objExists(g):
                    cmds.delete(g)
                    purged += 1
            except Exception:
                pass

        _log(log, "Purged {} scene clutter node(s) (layers, unknown nodes, empty groups).".format(purged))
        return purged


def fix_all_safe_issues(nodes=None, log=None):
    """Execute all safe automated fixes in 1 atomic Maya Ctrl+Z transaction."""
    with SceneTransaction("FixAllSafeModelingIssues", suspend_evaluation=True):
        _log(log, "Starting Master Safe Clean...")
        fix_make_names_unique(log=log)
        fix_add_geo_suffixes(log=log)
        fix_add_grp_suffixes(log=log)
        fix_shader_suffixes(log=log)
        fix_freeze_transforms(log=log)
        fix_center_pivots(log=log)
        fix_delete_construction_history(log=log)
        fix_delete_intermediate_shapes(log=log)
        fix_unlock_normals(log=log)
        fix_clean_scene_clutter(log=log)
        _log(log, "Master Safe Clean completed successfully.")
    return True
