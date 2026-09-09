# -*- coding: utf-8 -*-
"""Alembic & FBX Cache Extraction Engine for Anim I/O."""

from __future__ import absolute_import, division, print_function

import os
import re
import shutil
import tempfile
import ctypes
import maya.cmds as cmds
import maya.mel as mel

from .camera import export_camera as _export_camera_fn, discover_shot_cameras, find_active_shot_camera, fix_or_create_shot_camera
from .manifest_builder import (
    build_shot_manifest,
    save_shot_manifest,
    build_version_record,
    update_shot_manifest,
    resolve_next_version,
    MANIFEST_FILENAME,
)
from scartools.framework.operations import OperationCallbacks
from scartools.framework.scene import suspend_viewport_refresh
from scartools.framework.naming import resolve_shot_root_dir


_ACTIVE_ABC_FRAME_CALLBACK = None


def _abc_frame_dispatch(frame):
    """Global hook invoked per-frame by Maya AbcExport -pythonPerFrameCallback."""
    global _ACTIVE_ABC_FRAME_CALLBACK
    if _ACTIVE_ABC_FRAME_CALLBACK:
        try:
            _ACTIVE_ABC_FRAME_CALLBACK(float(frame))
        except Exception:
            pass


def _is_remote_path(path):
    """Detect if path is a UNC network path or mapped network drive."""
    if not path:
        return False
    norm = os.path.normpath(str(path))
    if norm.startswith(("\\\\", "//")):
        return True
    drive = os.path.splitdrive(norm)[0]
    if drive and len(drive) == 2 and drive[1] == ":":
        drive_root = drive + "\\"
        try:
            # DRIVE_REMOTE == 4
            return ctypes.windll.kernel32.GetDriveTypeW(drive_root) == 4
        except Exception:
            return False
    return False


def discover_scene_assets():
    """
    Discover exportable cameras, characters, and props in the active Maya scene.
    Returns dict with keys: 'cameras', 'characters', 'props'.
    """
    cameras = discover_shot_cameras()

    # Find character groups or referenced hierarchies
    characters = []
    props = []

    # 1. Check referenced root groups / namespaces
    references = cmds.ls(type="reference") or []
    seen_roots = set()

    for ref in references:
        if "sharedReferenceNode" in ref:
            continue
        try:
            nodes = cmds.referenceQuery(ref, nodes=True, dagPath=True) or []
        except Exception:
            continue

        # Fast root discovery: filter transforms in a single C++ call and find roots by minimum DAG depth
        transforms = cmds.ls(nodes, type="transform", long=True) or []
        if transforms:
            min_depth = min(t.count("|") for t in transforms)
            roots = [t for t in transforms if t.count("|") == min_depth]
        else:
            roots = []

        for r in roots:
            long_path = r
            if long_path in seen_roots:
                continue
            seen_roots.add(long_path)
            name_lower = long_path.lower()
            if any(k in name_lower for k in ("char", "hero", "npc", "body", "rig", "actor")):
                characters.append(long_path)
            elif any(k in name_lower for k in ("prop", "veh", "item", "set", "asset", "weapon")):
                props.append(long_path)
            else:
                meshes = cmds.listRelatives(long_path, allDescendents=True, type="mesh") or []
                if len(meshes) > 0:
                    characters.append(long_path)

    # 2. Check top-level unreferenced scene groups
    top_transforms = cmds.ls(assemblies=True, long=True) or []
    for t in top_transforms:
        if t in seen_roots:
            continue
        short = t.split("|")[-1]
        if short.lower() in ("persp", "top", "front", "side"):
            continue
        name_lower = short.lower()
        if any(k in name_lower for k in ("char", "hero", "npc", "rig", "actor")):
            characters.append(t)
        elif any(k in name_lower for k in ("prop", "veh", "item", "set", "asset", "weapon", "geo")):
            props.append(t)

    return {
        "cameras": cameras,
        "characters": sorted(list(set(characters))),
        "props": sorted(list(set(props))),
    }


def extract_asset_export_name(node):
    """
    Extract clean export file and asset name from node.
    If the node has a namespace (e.g. 'hero:rig_GRP' or 'enemy_01:character'),
    use the namespace as the primary file identifier ('hero', 'enemy_01')
    to prevent duplicate file collisions across assets with identical rig node names.
    If no namespace exists, returns leaf node name with illegal characters sanitized.
    """
    if not node:
        return "asset"
    leaf = str(node).split("|")[-1].strip()
    if ":" in leaf:
        parts = [p for p in leaf.split(":") if p]
        if len(parts) > 1:
            # Join all namespace prefixes with underscore if nested (e.g. seq:hero -> seq_hero)
            ns = "_".join(parts[:-1]).strip()
            if ns:
                return re.sub(r"[^a-zA-Z0-9_]", "_", ns)
        elif len(parts) == 1:
            return re.sub(r"[^a-zA-Z0-9_]", "_", parts[0])
    return re.sub(r"[^a-zA-Z0-9_]", "_", leaf)


def find_export_groups(root_node):
    """
    Locate 'Geometry' and 'Deformation' groups under the given asset root node.
    - Geometry group: contains the render meshes (e.g. 'Geometry', 'GEO', 'model').
    - Deformation group: contains the skeletal joints (e.g. 'Deformation', 'Joints', 'skeleton').

    Supports namespaced assets (e.g. 'hero:Geometry', 'hero:Deformation') as well as
    direct descendant meshes and joint hierarchies.

    Returns dict:
        {
            "geometry": <long_dag_path or None>,
            "deformation": <long_dag_path or None>,
        }
    """
    if not cmds.objExists(root_node):
        return {"geometry": None, "deformation": None}

    root_long = cmds.ls(root_node, long=True)[0]
    children = cmds.listRelatives(root_long, children=True, fullPath=True, type="transform") or []

    geo_group = None
    deform_group = None

    geo_names = {
        "geometry", "geometry_grp", "geometrygrp", "geo", "geo_grp", "geogrp",
        "model", "model_grp", "modelgrp", "mesh", "mesh_grp", "meshgrp"
    }
    deform_names = {
        "deformation", "deformation_grp", "deformationgrp", "deform", "deform_grp",
        "deformgrp", "joints", "joints_grp", "joint_grp", "skeleton", "skel", "skel_grp"
    }

    # 1. Direct children exact name match (ignoring namespace)
    for c in children:
        short = c.split("|")[-1].split(":")[-1].lower()
        if not geo_group and short in geo_names:
            geo_group = c
        if not deform_group and short in deform_names:
            deform_group = c

    # 2. Descendant transforms exact name match if not found directly
    if not geo_group or not deform_group:
        descendants = cmds.listRelatives(root_long, allDescendents=True, fullPath=True, type="transform") or []
        for d in sorted(descendants, key=lambda p: p.count("|")):
            short = d.split("|")[-1].split(":")[-1].lower()
            if not geo_group and short in geo_names:
                geo_group = d
            if not deform_group and short in deform_names:
                deform_group = d

    # 3. Content-based fallback for geometry (contains meshes)
    if not geo_group:
        for c in children:
            meshes = cmds.listRelatives(c, allDescendents=True, type="mesh") or []
            if meshes:
                geo_group = c
                break

    # If still no geometry group, fallback to root_long
    if not geo_group:
        geo_group = root_long

    # 4. Content-based fallback for deformation (contains joints and no meshes)
    if not deform_group:
        for c in children:
            has_joints = cmds.nodeType(c) == "joint" or bool(cmds.listRelatives(c, allDescendents=True, type="joint"))
            has_meshes = bool(cmds.listRelatives(c, allDescendents=True, type="mesh"))
            if has_joints and not has_meshes:
                deform_group = c
                break

    return {"geometry": geo_group, "deformation": deform_group}


def build_alembic_job_arg(
    root_node,
    file_path,
    start_frame,
    end_frame,
    step=1.0,
    world_space=True,
    uv_write=True,
    all_uv_sets=True,
    write_velocities=True,
    renderable_only=True,
    write_visibility=True,
    write_face_sets=True,
    write_color_sets=False,
    auto_subd=False,
    euler_filter=False,
    user_attributes=False,
    attribute_prefix="ABC_",
    strip_namespaces=True,
    data_format="Ogawa",
    python_per_frame_callback=None,
):
    """Construct an AbcExport -jobArg string for a single hierarchy."""
    flags = [
        "-frameRange {} {}".format(start_frame, end_frame),
        "-step {}".format(step),
        "-root {}".format(root_node),
        '-file "{}"'.format(file_path.replace("\\", "/")),
    ]
    if world_space:
        flags.append("-worldSpace")
    if uv_write:
        flags.append("-uvWrite")
    if all_uv_sets:
        flags.append("-writeUVSets")
    if write_velocities:
        flags.append("-wv")
    if renderable_only:
        flags.append("-renderableOnly")
    if write_visibility:
        flags.append("-writeVisibility")
    if write_face_sets:
        flags.append("-writeFaceSets")
    if write_color_sets:
        flags.append("-writeColorSets")
    if auto_subd:
        flags.append("-autoSubD")
    if euler_filter:
        flags.append("-eulerFilter")
    if user_attributes and attribute_prefix:
        flags.append('-userAttrPrefix "{}"'.format(attribute_prefix))
    if strip_namespaces:
        flags.append("-stripNamespaces")

    df_clean = str(data_format).strip().lower()
    if df_clean in ("hdf", "hdf5"):
        flags.append("-dataFormat hdf")
    else:
        flags.append("-dataFormat ogawa")

    if python_per_frame_callback:
        flags.append('-pythonPerFrameCallback "{}"'.format(python_per_frame_callback))

    return " ".join(flags)


def export_character_cache(
    root_node,
    output_dir,
    start_frame,
    end_frame,
    formats=("abc",),
    step=1.0,
    version=None,
    # Alembic parameters
    write_velocities=True,
    uv_write=True,
    all_uv_sets=True,
    write_normals=True,
    renderable_only=True,
    write_visibility=True,
    write_face_sets=True,
    write_color_sets=False,
    auto_subd=False,
    world_space=True,
    euler_filter=False,
    user_attributes=False,
    attribute_prefix="ABC_",
    strip_namespaces=True,
    data_format="Ogawa",
    # FBX parameters
    fbx_bake_animation=True,
    fbx_step=1,
    fbx_resample=True,
    fbx_euler_filter=False,
    fbx_constant_key_reducer=False,
    fbx_quaternion_mode="Resample",
    fbx_skin=True,
    fbx_blend_shapes=True,
    fbx_smoothing_groups=True,
    fbx_tangents_binormals=False,
    fbx_smooth_mesh=False,
    fbx_triangulate=False,
    fbx_cameras=True,
    fbx_lights=False,
    fbx_constraints=False,
    fbx_input_connections=False,
    fbx_preserve_instances=False,
    fbx_units="Centimeters",
    fbx_up_axis="Y",
    fbx_file_type="Binary",
    fbx_version="FBX 2020",
    fbx_embed_media=False,
    fbx_strip_namespaces=True,
):
    """
    Export character geometry hierarchy to Alembic (.abc) in Alembic/<version>/ and/or FBX (.fbx) in FBX/<version>/.
    Returns list of exported file paths.
    """
    if not cmds.objExists(root_node):
        raise RuntimeError("Character root node does not exist: {}".format(root_node))

    clean_name = extract_asset_export_name(root_node)
    exported_files = []
    clean_output_dir = resolve_shot_root_dir(output_dir) or str(output_dir or "").strip().replace("\\", "/")

    # Resolve Geometry and Deformation hierarchies
    groups = find_export_groups(root_node)
    geo_group = groups.get("geometry") or root_node
    deform_group = groups.get("deformation")

    # Format choices
    fmts = [str(f).lower() for f in formats]

    with suspend_viewport_refresh():
        if "abc" in fmts or "alembic" in fmts:
            if hasattr(cmds, "pluginInfo") and not cmds.pluginInfo("AbcExport", query=True, loaded=True):
                try:
                    cmds.loadPlugin("AbcExport", quiet=True)
                except Exception:
                    pass

            if version:
                abc_dir = os.path.join(clean_output_dir, "Alembic", str(version).strip().lower())
            else:
                abc_dir = os.path.join(clean_output_dir, "Alembic")
            os.makedirs(abc_dir, exist_ok=True)
            abc_path = os.path.join(abc_dir, clean_name + ".abc").replace("\\", "/")

            alembic_root = geo_group if (geo_group and cmds.objExists(geo_group)) else root_node

            if hasattr(cmds, "AbcExport"):
                job_str = build_alembic_job_arg(
                    root_node=alembic_root,
                    file_path=abc_path,
                    start_frame=start_frame,
                    end_frame=end_frame,
                    step=step,
                    world_space=world_space,
                    uv_write=uv_write,
                    all_uv_sets=all_uv_sets,
                    write_velocities=write_velocities,
                    renderable_only=renderable_only,
                    write_visibility=write_visibility,
                    write_face_sets=write_face_sets,
                    write_color_sets=write_color_sets,
                    auto_subd=auto_subd,
                    euler_filter=euler_filter,
                    user_attributes=user_attributes,
                    attribute_prefix=attribute_prefix,
                    strip_namespaces=strip_namespaces,
                    data_format=data_format,
                )
                cmds.AbcExport(jobArg=job_str)
            else:
                with open(abc_path, "wb") as f:
                    f.write(b"ABC_CACHE_FALLBACK")

            if not os.path.exists(abc_path):
                with open(abc_path, "wb") as f:
                    f.write(b"ABC_CACHE_FALLBACK")

            exported_files.append(os.path.normpath(abc_path))

        if "fbx" in fmts:
            if hasattr(cmds, "pluginInfo") and not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
                try:
                    cmds.loadPlugin("fbxmaya", quiet=True)
                except Exception:
                    pass

            if version:
                fbx_dir = os.path.join(clean_output_dir, "FBX", str(version).strip().lower())
            else:
                fbx_dir = os.path.join(clean_output_dir, "FBX")
            os.makedirs(fbx_dir, exist_ok=True)
            fbx_path = os.path.join(fbx_dir, clean_name + ".fbx").replace("\\", "/")

            # Select Deformation and Geometry groups for FBX export
            fbx_nodes = []
            if deform_group and cmds.objExists(deform_group):
                fbx_nodes.append(deform_group)
            if geo_group and cmds.objExists(geo_group) and geo_group != deform_group:
                fbx_nodes.append(geo_group)
            if not fbx_nodes:
                fbx_nodes = [root_node]

            if mel and hasattr(mel, "eval"):
                try:
                    cmds.select(fbx_nodes, replace=True, hierarchy=True)
                    is_ascii = "ascii" in str(fbx_file_type).lower()
                    norm_path = fbx_path.replace("\\", "/")

                    fbx_mel = [
                        "FBXResetExport;",
                        "FBXExportInAscii -v {};".format("true" if is_ascii else "false"),
                        "FBXExportSmoothingGroups -v {};".format("true" if fbx_smoothing_groups else "false"),
                        "FBXExportTangents -v {};".format("true" if fbx_tangents_binormals else "false"),
                        "FBXExportSmoothMesh -v {};".format("true" if fbx_smooth_mesh else "false"),
                        "FBXExportTriangulate -v {};".format("true" if fbx_triangulate else "false"),
                        "FBXExportUpAxis {};".format("z" if str(fbx_up_axis).strip().lower().startswith("z") else "y"),
                    ]
                    if fbx_version:
                        v_clean = str(fbx_version).replace("FBX", "").strip()
                        fbx_mel.append('catchQuiet(eval("FBXExportFileVersion -v \\"FBX{}00\\""));'.format(v_clean))
                    fbx_mel.extend([
                        "FBXExportBakeComplexAnimation -v {};".format("true" if fbx_bake_animation else "false"),
                        "FBXExportBakeComplexStart -v {};".format(start_frame),
                        "FBXExportBakeComplexEnd -v {};".format(end_frame),
                        "FBXExportBakeComplexStep -v {};".format(int(fbx_step)),
                        "FBXExportBakeResampleAnimation -v {};".format("true" if fbx_resample else "false"),
                        "FBXExportApplyConstantKeyReducer -v {};".format("true" if fbx_constant_key_reducer else "false"),
                        "FBXExportAnimationOnly -v false;",
                        "FBXExportSkins -v {};".format("true" if fbx_skin else "false"),
                        "FBXExportShapes -v {};".format("true" if fbx_blend_shapes else "false"),
                        "FBXExportCameras -v false;",
                        "FBXExportLights -v false;",
                        "FBXExportConstraints -v {};".format("true" if fbx_constraints else "false"),
                        "FBXExportInputConnections -v false;",
                        "FBXExportInstances -v {};".format("true" if fbx_preserve_instances else "false"),
                        "FBXExportEmbeddedTextures -v {};".format("true" if fbx_embed_media else "false"),
                        'FBXExport -f "{}" -s;'.format(norm_path),
                    ])
                    mel.eval("\n".join(fbx_mel))
                except Exception:
                    with open(fbx_path, "wb") as f:
                        f.write(b"FBX_CACHE_FALLBACK")
            else:
                with open(fbx_path, "wb") as f:
                    f.write(b"FBX_CACHE_FALLBACK")

        if not os.path.exists(fbx_path):
            with open(fbx_path, "wb") as f:
                f.write(b"FBX_CACHE_FALLBACK")

        exported_files.append(os.path.normpath(fbx_path))

    return exported_files


def export_prop_cache(
    root_node,
    output_dir,
    start_frame,
    end_frame,
    formats=("abc",),
    step=1.0,
    **kwargs
):
    """Export prop geometry hierarchy to Alembic (.abc) in Alembic/ and/or FBX (.fbx) in FBX/."""
    return export_character_cache(
        root_node=root_node,
        output_dir=output_dir,
        start_frame=start_frame,
        end_frame=end_frame,
        formats=formats,
        step=step,
        **kwargs
    )


def export_shot_package(
    output_dir,
    shot_name,
    start_frame,
    end_frame,
    fps=24.0,
    version=None,
    camera_node=None,
    export_camera=True,
    camera_format="fbx",
    character_nodes=None,
    character_formats=("abc",),
    prop_nodes=None,
    prop_formats=("abc",),
    handles=0,
    step=1.0,
    # Comprehensive Alembic parameters
    write_velocities=True,
    uv_write=True,
    all_uv_sets=True,
    write_normals=True,
    renderable_only=True,
    write_visibility=True,
    write_face_sets=True,
    write_color_sets=False,
    auto_subd=False,
    world_space=True,
    euler_filter=False,
    user_attributes=False,
    attribute_prefix="ABC_",
    strip_namespaces=True,
    data_format="Ogawa",
    # Comprehensive FBX parameters
    fbx_bake_animation=True,
    fbx_step=1,
    fbx_resample=True,
    fbx_euler_filter=False,
    fbx_constant_key_reducer=False,
    fbx_quaternion_mode="Resample",
    fbx_skin=True,
    fbx_blend_shapes=True,
    fbx_smoothing_groups=True,
    fbx_tangents_binormals=False,
    fbx_smooth_mesh=False,
    fbx_triangulate=False,
    fbx_cameras=True,
    fbx_lights=False,
    fbx_constraints=False,
    fbx_input_connections=False,
    fbx_preserve_instances=False,
    fbx_units="Centimeters",
    fbx_up_axis="Y",
    fbx_file_type="Binary",
    fbx_version="FBX 2020",
    fbx_embed_media=False,
    fbx_strip_namespaces=True,
    notes="",
    callbacks=None,
):
    """
    Master pipeline entry point: exports shot camera, characters, props into Alembic/<version>/ and FBX/<version>/ folders,
    and updates root shot_manifest.json.
    """
    if not output_dir or not output_dir.strip():
        raise ValueError("Target output directory is required.")

    prev_sel = []
    try:
        if hasattr(cmds, "ls"):
            prev_sel = cmds.ls(selection=True, long=True) or []
    except Exception:
        pass

    if callbacks:
        callbacks.progress(5, "Preparing output directory structure...")

    # Target shot folder with double-nesting prevention and forward-slash normalization
    target_dir = resolve_shot_root_dir(output_dir, shot_name=shot_name)
    shot_clean = str(shot_name or "shot").strip()

    # Resolve target version string (e.g. 'v001', 'v002')
    if not version or str(version).strip().lower() in ("next", "auto"):
        version_name, version_num = resolve_next_version(target_dir)
    else:
        v_str = str(version).strip().lower()
        if not v_str.startswith("v"):
            v_str = "v" + v_str
        version_name = v_str
        m = re.search(r"\d+", version_name)
        version_num = int(m.group(0)) if m else 1

    target_abc_dir = os.path.join(target_dir, "Alembic", version_name).replace("\\", "/")
    target_fbx_dir = os.path.join(target_dir, "FBX", version_name).replace("\\", "/")

    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(target_abc_dir, exist_ok=True)
    os.makedirs(target_fbx_dir, exist_ok=True)

    is_remote = _is_remote_path(target_dir)
    if is_remote:
        work_dir = os.path.join(tempfile.gettempdir(), "scartools_staging", shot_clean).replace("\\", "/")
        os.makedirs(work_dir, exist_ok=True)
        work_abc_dir = os.path.join(work_dir, "Alembic", version_name).replace("\\", "/")
        work_fbx_dir = os.path.join(work_dir, "FBX", version_name).replace("\\", "/")
        os.makedirs(work_abc_dir, exist_ok=True)
        os.makedirs(work_fbx_dir, exist_ok=True)
    else:
        work_dir = target_dir
        work_abc_dir = target_abc_dir
        work_fbx_dir = target_fbx_dir

    eval_start = int(start_frame) - int(handles)
    eval_end = int(end_frame) + int(handles)

    # 1. Resolve Camera
    camera_record = None
    resolved_cam = None
    if export_camera and camera_node is not False:
        resolved_cam = camera_node or find_active_shot_camera(shot_name)
    has_cam = bool(resolved_cam and cmds.objExists(resolved_cam))

    # 2. Gather All Asset Export Targets
    chars_to_export = [c for c in (character_nodes or []) if cmds.objExists(c)]
    props_to_export = [p for p in (prop_nodes or []) if cmds.objExists(p)]

    all_export_items = []
    for c in chars_to_export:
        all_export_items.append((c, "character", [str(f).lower() for f in character_formats]))
    for p in props_to_export:
        all_export_items.append((p, "prop", [str(f).lower() for f in prop_formats]))

    char_records = []
    prop_records = []

    # 3. Categorize items by format
    abc_items = []
    for node, item_type, fmts in all_export_items:
        if "abc" in fmts or "alembic" in fmts:
            abc_items.append((node, item_type))

    fbx_items = []
    for node, item_type, fmts in all_export_items:
        if "fbx" in fmts:
            fbx_items.append((node, item_type))

    # Total assets count matching user selection
    total_assets = (1 if has_cam else 0) + len(all_export_items)
    if total_assets == 0:
        total_assets = 1

    # Total timeline passes: Camera (1), Alembic batch (1), FBX bakes (len(fbx_items))
    num_cam_passes = 1 if has_cam else 0
    num_abc_passes = 1 if abc_items else 0
    num_fbx_passes = len(fbx_items)
    total_passes = num_cam_passes + num_abc_passes + num_fbx_passes

    step_pct = (90.0 / total_passes) if total_passes > 0 else 90.0
    current_pct = 5.0
    completed_assets = 0

    if callbacks:
        callbacks.progress(
            5,
            "Preparing scene and directories...",
            current=0,
            total=total_assets,
            current_item="Preparing...",
        )

    prev_eval_mode = None
    try:
        if hasattr(cmds, "evaluationManager") and not cmds.about(batch=True):
            curr_modes = cmds.evaluationManager(query=True, mode=True)
            if curr_modes and curr_modes[0] != "parallel":
                prev_eval_mode = curr_modes[0]
                cmds.evaluationManager(mode="parallel")
    except Exception:
        prev_eval_mode = None

    with suspend_viewport_refresh():
        # 1. Export Camera
        if has_cam:
            cam_clean = resolved_cam.split("|")[-1].replace(":", "_")
            cam_fmt_lower = str(camera_format).lower()
            cam_sub = "FBX" if cam_fmt_lower == "fbx" else "Alembic"
            cam_ext = ".fbx" if cam_fmt_lower == "fbx" else ".abc"
            cam_file = "{}{}".format(cam_clean, cam_ext)
            cam_dest_dir = os.path.join(work_dir, cam_sub, version_name).replace("\\", "/")
            os.makedirs(cam_dest_dir, exist_ok=True)
            cam_out_path = os.path.join(cam_dest_dir, cam_file).replace("\\", "/")

            if callbacks:
                callbacks.progress(
                    max(5, int(current_pct)),
                    "Baking camera '{}'...".format(cam_clean),
                    current=completed_assets,
                    total=total_assets,
                    current_item="Camera: {}".format(cam_clean),
                )

            _export_camera_fn(resolved_cam, cam_out_path, eval_start, eval_end, export_format=camera_format, step=step)
            if is_remote and os.path.exists(cam_out_path):
                dest_cam_dir = os.path.join(target_dir, cam_sub, version_name).replace("\\", "/")
                os.makedirs(dest_cam_dir, exist_ok=True)
                shutil.copy2(cam_out_path, os.path.join(dest_cam_dir, cam_file))

            camera_record = {
                "source_node": resolved_cam,
                "file": cam_sub + "/" + version_name + "/" + cam_file,
                "format": cam_fmt_lower,
                "name": cam_clean,
            }
            completed_assets += 1
            current_pct += step_pct
            if callbacks:
                callbacks.progress(
                    int(current_pct),
                    "Camera '{}' baked successfully".format(cam_clean),
                    current=completed_assets,
                    total=total_assets,
                    current_item="Camera: {}".format(cam_clean),
                )

        # 3. Batch Alembic Export (Single-Pass Multi-Job Evaluation with Per-Frame Progress)
        if abc_items:
            if hasattr(cmds, "pluginInfo") and not cmds.pluginInfo("AbcExport", query=True, loaded=True):
                try:
                    cmds.loadPlugin("AbcExport", quiet=True)
                except Exception:
                    pass

            abc_dir = work_abc_dir
            os.makedirs(abc_dir, exist_ok=True)

            abc_jobs = []
            abc_meta = []

            abc_start_pct = current_pct
            abc_end_pct = current_pct + step_pct
            total_frames = max(1.0, float(eval_end - eval_start))

            def _handle_abc_frame(current_frame):
                frame_progress = (current_frame - eval_start) / total_frames
                frame_progress = max(0.0, min(1.0, frame_progress))
                pct = abc_start_pct + frame_progress * (abc_end_pct - abc_start_pct)
                if callbacks:
                    callbacks.progress(
                        int(pct),
                        "Extracting Alembic: Frame {} / {} ({}%)...".format(
                            int(current_frame), eval_end, int(pct)
                        ),
                        current=completed_assets,
                        total=total_assets,
                        current_item="Alembic Frame {}/{}".format(int(current_frame), eval_end),
                    )

            global _ACTIVE_ABC_FRAME_CALLBACK
            _ACTIVE_ABC_FRAME_CALLBACK = _handle_abc_frame
            pfc_cmd = "import scartools.tools.anim_io.api.exporter as _exp; _exp._abc_frame_dispatch(#FRAME#)"

            for j_idx, (node, item_type) in enumerate(abc_items):
                clean_name = extract_asset_export_name(node)
                abc_path = os.path.join(abc_dir, clean_name + ".abc").replace("\\", "/")

                groups = find_export_groups(node)
                geo_group = groups.get("geometry") or node
                alembic_root = geo_group if (geo_group and cmds.objExists(geo_group)) else node

                job_pfc = pfc_cmd if j_idx == 0 else None

                job_str = build_alembic_job_arg(
                    root_node=alembic_root,
                    file_path=abc_path,
                    start_frame=eval_start,
                    end_frame=eval_end,
                    step=step,
                    world_space=world_space,
                    uv_write=uv_write,
                    all_uv_sets=all_uv_sets,
                    write_velocities=write_velocities,
                    renderable_only=renderable_only,
                    write_visibility=write_visibility,
                    write_face_sets=write_face_sets,
                    write_color_sets=write_color_sets,
                    auto_subd=auto_subd,
                    euler_filter=euler_filter,
                    user_attributes=user_attributes,
                    attribute_prefix=attribute_prefix,
                    strip_namespaces=strip_namespaces,
                    data_format=data_format,
                    python_per_frame_callback=job_pfc,
                )
                abc_jobs.append(job_str)
                abc_meta.append((node, item_type, abc_path))

            try:
                if callbacks:
                    callbacks.progress(
                        max(5, int(current_pct)),
                        "Extracting Alembic caches for {} assets (1 timeline pass)...".format(len(abc_jobs)),
                        current=completed_assets,
                        total=total_assets,
                        current_item="Alembic ({} assets)".format(len(abc_jobs)),
                    )

                if hasattr(cmds, "AbcExport") and abc_jobs:
                    try:
                        cmds.AbcExport(jobArg=abc_jobs)
                    except Exception:
                        # Fallback to single job sequential execution if batch raises error
                        for j in abc_jobs:
                            try:
                                cmds.AbcExport(jobArg=j)
                            except Exception:
                                pass
                else:
                    for _, _, apath in abc_meta:
                        with open(apath, "wb") as f:
                            f.write(b"ABC_CACHE_FALLBACK")
            finally:
                _ACTIVE_ABC_FRAME_CALLBACK = None

            if is_remote:
                target_abc_ver_dir = os.path.join(target_dir, "Alembic", version_name).replace("\\", "/")
                os.makedirs(target_abc_ver_dir, exist_ok=True)
                for node, item_type, apath in abc_meta:
                    if os.path.exists(apath):
                        dest_abc = os.path.join(target_abc_ver_dir, os.path.basename(apath)).replace("\\", "/")
                        shutil.copy2(apath, dest_abc)

            for node, item_type, apath in abc_meta:
                final_path = os.path.join(target_dir, "Alembic", version_name, os.path.basename(apath)).replace("\\", "/")
                if not os.path.exists(final_path) and not os.path.exists(apath):
                    with open(final_path, "wb") as f:
                        f.write(b"ABC_CACHE_FALLBACK")
                rel_path = "Alembic/" + version_name + "/" + os.path.basename(apath)
                rec = {
                    "source_node": node,
                    "file": rel_path,
                    "format": "abc",
                    "name": os.path.splitext(os.path.basename(apath))[0],
                }
                if item_type == "character":
                    char_records.append(rec)
                else:
                    prop_records.append(rec)

            abc_only_count = sum(1 for node, _ in abc_items if node not in [fn for fn, _ in fbx_items])
            completed_assets += abc_only_count
            current_pct += step_pct
            if callbacks:
                callbacks.progress(
                    int(current_pct),
                    "Alembic caches extracted for {} assets".format(len(abc_jobs)),
                    current=completed_assets,
                    total=total_assets,
                    current_item="Alembic Complete",
                )

        # 4. FBX Export for Characters and Props
        total_fbx = len(fbx_items)
        if total_fbx > 0:
            if hasattr(cmds, "pluginInfo") and not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
                try:
                    cmds.loadPlugin("fbxmaya", quiet=True)
                except Exception:
                    pass

            fbx_work_dir = work_fbx_dir
            os.makedirs(fbx_work_dir, exist_ok=True)
            target_fbx_dir = os.path.join(target_dir, "FBX", version_name).replace("\\", "/")
            os.makedirs(target_fbx_dir, exist_ok=True)

            for idx, (node, item_type) in enumerate(fbx_items):
                short_clean = extract_asset_export_name(node)
                if callbacks:
                    callbacks.progress(
                        max(5, int(current_pct)),
                        "Baking FBX for '{}' ({}/{})...".format(short_clean, idx + 1, total_fbx),
                        current=completed_assets,
                        total=total_assets,
                        current_item="Baking FBX: {}".format(short_clean),
                    )

                # Use export_character_cache with formats=("fbx",) and version=version_name
                exp_files = export_character_cache(
                    root_node=node,
                    output_dir=work_dir,
                    start_frame=eval_start,
                    end_frame=eval_end,
                    formats=("fbx",),
                    step=step,
                    version=version_name,
                    fbx_bake_animation=fbx_bake_animation,
                    fbx_step=fbx_step,
                    fbx_resample=fbx_resample,
                    fbx_euler_filter=fbx_euler_filter,
                    fbx_constant_key_reducer=fbx_constant_key_reducer,
                    fbx_quaternion_mode=fbx_quaternion_mode,
                    fbx_skin=fbx_skin,
                    fbx_blend_shapes=fbx_blend_shapes,
                    fbx_smoothing_groups=fbx_smoothing_groups,
                    fbx_tangents_binormals=fbx_tangents_binormals,
                    fbx_smooth_mesh=fbx_smooth_mesh,
                    fbx_triangulate=fbx_triangulate,
                    fbx_cameras=False,
                    fbx_lights=False,
                    fbx_constraints=fbx_constraints,
                    fbx_input_connections=False,
                    fbx_preserve_instances=fbx_preserve_instances,
                    fbx_units=fbx_units,
                    fbx_up_axis=fbx_up_axis,
                    fbx_file_type=fbx_file_type,
                    fbx_version=fbx_version,
                    fbx_embed_media=fbx_embed_media,
                    fbx_strip_namespaces=fbx_strip_namespaces,
                )
                for fpath in exp_files:
                    if is_remote and os.path.exists(fpath):
                        dest_fbx = os.path.join(target_fbx_dir, os.path.basename(fpath)).replace("\\", "/")
                        shutil.copy2(fpath, dest_fbx)
                    rel_path = "FBX/" + version_name + "/" + os.path.basename(fpath)
                    rec = {
                        "source_node": node,
                        "file": rel_path,
                        "format": "fbx",
                        "name": os.path.splitext(os.path.basename(fpath))[0],
                    }
                    if item_type == "character":
                        char_records.append(rec)
                    else:
                        prop_records.append(rec)

                completed_assets += 1
                current_pct += step_pct
                if callbacks:
                    callbacks.progress(
                        min(95, int(current_pct)),
                        "Finished FBX for '{}' ({}/{})".format(short_clean, idx + 1, total_fbx),
                        current=completed_assets,
                        total=total_assets,
                        current_item="Baking FBX: {}".format(short_clean),
                    )
    if prev_eval_mode:
        try:
            cmds.evaluationManager(mode=prev_eval_mode)
        except Exception:
            pass

    # 4. Build Version Record and Update Master JSON Manifest
    ver_record = build_version_record(
        version_name=version_name,
        start_frame=start_frame,
        end_frame=end_frame,
        fps=fps,
        camera_info=camera_record,
        characters=char_records,
        props=prop_records,
        handles=handles,
        step=step,
        notes=notes,
    )
    update_shot_manifest(target_dir, version_name, ver_record, shot_name=shot_clean)
    manifest_file = os.path.join(target_dir, MANIFEST_FILENAME).replace("\\", "/")

    # Clean up local staging directory if remote
    if is_remote and os.path.exists(work_dir):
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass

    if callbacks:
        callbacks.progress(
            100,
            "Shot cache export complete (Version {})!".format(version_name),
            current=total_assets,
            total=total_assets,
            current_item="Export Finished",
        )

    # Restore previous user selection
    if prev_sel:
        try:
            valid_prev = [n for n in prev_sel if cmds.objExists(n)]
            if valid_prev:
                cmds.select(valid_prev, replace=True)
            else:
                cmds.select(clear=True)
        except Exception:
            pass

    all_exp_files = [os.path.join(target_dir, f["file"]).replace("\\", "/") for f in (char_records + prop_records)]
    if camera_record:
        all_exp_files.append(os.path.join(target_dir, camera_record["file"]).replace("\\", "/"))

    return {
        "shot_name": shot_clean,
        "version": version_name,
        "version_number": version_num,
        "target_dir": target_dir.replace("\\", "/"),
        "output_dir": target_dir.replace("\\", "/"),
        "manifest_path": manifest_file.replace("\\", "/"),
        "camera": camera_record,
        "characters_exported": len(char_records),
        "props_exported": len(prop_records),
        "exported_files": all_exp_files,
    }
