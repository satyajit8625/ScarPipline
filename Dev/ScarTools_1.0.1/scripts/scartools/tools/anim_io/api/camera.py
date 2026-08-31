# -*- coding: utf-8 -*-
"""Headless camera discovery, standardization, baking, and FBX/Alembic export."""

from __future__ import absolute_import, division, print_function

import os
import maya.cmds as cmds
import maya.mel as mel

DEFAULT_CAMERAS = ("persp", "top", "front", "side")


def discover_shot_cameras(preferred_shot_name=None):
    """
    Return valid shot camera transform names in the scene,
    filtering out default viewport cameras and internal rig/face UI cameras.
    """
    all_cams = cmds.ls(type="camera", long=True) or []
    shot_cams = []
    ignored_keywords = ("face", "ctrl", "sub", "preview", "turntable", "ui", "thumb", "rig:")

    for cam_shape in all_cams:
        parents = cmds.listRelatives(cam_shape, parent=True, fullPath=True)
        if not parents:
            continue
        cam_transform = parents[0]
        short_name = cam_transform.split("|")[-1]
        short_lower = short_name.lower()

        # Filter out default cameras
        if short_lower in DEFAULT_CAMERAS or short_lower.split(":")[-1] in DEFAULT_CAMERAS:
            continue

        # Filter out internal rig / face UI cameras
        if any(ign in short_lower for ign in ignored_keywords):
            continue

        shot_cams.append(cam_transform)

    # Sort prioritizing matching shot name / _CAM suffix
    if preferred_shot_name:
        pref = preferred_shot_name.lower()
        parts = [p.lower() for p in preferred_shot_name.split("_") if len(p) >= 2]
        
        def _score(c):
            c_low = c.split("|")[-1].lower()
            if pref in c_low and "cam" in c_low:
                return 0
            if any(p in c_low for p in parts) and "cam" in c_low:
                return 1
            if "cam" in c_low or "camera" in c_low:
                return 2
            return 3

        shot_cams.sort(key=_score)
    else:
        shot_cams.sort(key=lambda c: (0 if "cam" in c.lower() else 1))

    return shot_cams


def find_active_shot_camera(preferred_shot_name=None):
    """
    Find the primary shot camera matching standard studio naming (e.g. PRT_SH_010_CAM or Shot_020_Camera).
    Returns long DAG path of the camera or None.
    """
    cams = discover_shot_cameras(preferred_shot_name=preferred_shot_name)
    if not cams:
        # Fallback check if any camera in scene exists
        all_cams = cmds.ls(type="camera", long=True) or []
        for cam_shape in all_cams:
            parents = cmds.listRelatives(cam_shape, parent=True, fullPath=True)
            if parents:
                t = parents[0]
                short = t.split("|")[-1].lower()
                if short not in DEFAULT_CAMERAS:
                    cams.append(t)

    if not cams:
        return None

    if preferred_shot_name:
        pref = preferred_shot_name.lower()
        # 1. Exact or prefixed
        for c in cams:
            short = c.split("|")[-1].lower()
            if short == pref + "_cam" or short == "cam_" + pref or short == pref:
                return c
        # 2. Match whole shot name
        for c in cams:
            if pref in c.lower():
                return c
        # 3. Match numeric or shot tokens (e.g. 020 in Shot_020_Camera)
        tokens = [p.lower() for p in preferred_shot_name.split("_") if len(p) >= 2]
        for c in cams:
            short = c.split("|")[-1].lower()
            if any(tok in short for tok in tokens):
                return c

    return cams[0]


def fix_or_create_shot_camera(preferred_shot_name=None):
    """
    Ensure a standardized shot camera exists (e.g. PRT_SH_010_CAM).
    If a camera exists or is selected, rename it directly.
    If no camera exists, create a new one.
    Returns long DAG path of the camera.
    """
    target_name = (str(preferred_shot_name or "Shot").strip()) + "_CAM"

    # 1. If camera already exists with exact target name
    matches = cmds.ls(target_name, long=True) or []
    if matches:
        return matches[0]

    # 2. If a camera is currently selected in Maya
    sel = cmds.ls(selection=True, long=True) or []
    for s in sel:
        try:
            if not cmds.objExists(s):
                continue
            shapes = cmds.listRelatives(s, shapes=True, type="camera", fullPath=True) or []
            if shapes:
                renamed = cmds.rename(s, target_name)
                _rename_shape(renamed, target_name)
                return cmds.ls(renamed, long=True)[0]
            elif cmds.nodeType(s) == "camera":
                parents = cmds.listRelatives(s, parent=True, fullPath=True) or []
                if parents:
                    renamed = cmds.rename(parents[0], target_name)
                    _rename_shape(renamed, target_name)
                    return cmds.ls(renamed, long=True)[0]
        except Exception:
            continue

    # 3. If any camera in scene exists, find the best match and rename it
    cams = discover_shot_cameras(preferred_shot_name=preferred_shot_name)
    if cams:
        best_cam = None
        if preferred_shot_name:
            pref = preferred_shot_name.lower()
            tokens = [p.lower() for p in preferred_shot_name.split("_") if len(p) >= 2]
            tokens.append(pref)
            for c in cams:
                short = c.split("|")[-1].lower()
                if any(tok in short for tok in tokens):
                    best_cam = c
                    break
        if not best_cam:
            best_cam = cams[0]

        renamed = cmds.rename(best_cam, target_name)
        _rename_shape(renamed, target_name)
        return cmds.ls(renamed, long=True)[0]

    # 4. Create new shot camera
    cam_tuple = cmds.camera()
    renamed_tf = cmds.rename(cam_tuple[0], target_name)
    _rename_shape(renamed_tf, target_name)
    return cmds.ls(renamed_tf, long=True)[0]


def _rename_shape(transform_node, target_base_name):
    """Helper to rename camera shape cleanly."""
    try:
        shapes = cmds.listRelatives(transform_node, shapes=True, type="camera", fullPath=True) or []
        if shapes:
            cmds.rename(shapes[0], target_base_name + "Shape")
    except Exception:
        pass


def bake_camera_world_space(camera_transform, start_frame, end_frame):
    """
    Create a clean, baked world-space duplicate of the camera transform.
    Returns the duplicate baked camera transform name.
    """
    if not cmds.objExists(camera_transform):
        raise RuntimeError("Camera does not exist: {}".format(camera_transform))

    # Duplicate camera
    dup_cam = cmds.camera(name="baked_" + camera_transform.split("|")[-1].split(":")[-1])[0]
    dup_shape = cmds.listRelatives(dup_cam, shapes=True, fullPath=True)[0]
    src_shapes = cmds.listRelatives(camera_transform, shapes=True, fullPath=True) or []
    src_shape = src_shapes[0] if src_shapes else camera_transform

    # Constrain to source camera
    p_const = cmds.parentConstraint(camera_transform, dup_cam, maintainOffset=False)[0]

    # Connect focal length and lens attributes
    for attr in ("focalLength", "horizontalFilmAperture", "verticalFilmAperture", "lensSqueezeRatio", "nearClipPlane", "farClipPlane"):
        if cmds.attributeQuery(attr, node=src_shape, exists=True) and cmds.attributeQuery(attr, node=dup_shape, exists=True):
            cmds.connectAttr(src_shape + "." + attr, dup_shape + "." + attr, force=True)

    # Bake simulation
    cmds.bakeResults(
        dup_cam,
        time=(start_frame, end_frame),
        simulation=True,
        sampleBy=1,
        disableImplicitControl=True,
        preserveOutsideKeys=False,
        sparseAnimCurveBake=False,
                        minimizeRotation=True,
    )

    cmds.delete(p_const)
    return dup_cam


def export_camera(camera_node, output_file, start_frame, end_frame, export_format="fbx", step=1.0):
    """
    Export baked camera to FBX (.fbx) or Alembic (.abc).
    """
    if not cmds.objExists(camera_node):
        raise RuntimeError("Camera '{}' not found in scene.".format(camera_node))

    out_dir = os.path.dirname(output_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    export_format = export_format.lower()
    baked_cam = bake_camera_world_space(camera_node, start_frame, end_frame)

    try:
        cmds.select(baked_cam, replace=True)

        if export_format == "fbx":
            try:
                if not cmds.pluginInfo("fbxmaya", q=True, loaded=True):
                    cmds.loadPlugin("fbxmaya")
            except Exception:
                pass

            mel.eval('FBXResetExport')
            mel.eval('FBXExportBakeComplexAnimation -v true')
            mel.eval('FBXExportBakeComplexStart -v {}'.format(start_frame))
            mel.eval('FBXExportBakeComplexEnd -v {}'.format(end_frame))
            mel.eval('FBXExportBakeComplexStep -v {}'.format(int(step)))
            mel.eval('FBXExportCameras -v true')
            mel.eval('FBXExportAnimationOnly -v false')
            mel.eval('FBXExportInputConnections -v false')

            norm_path = output_file.replace("\\", "/")
            mel.eval('FBXExport -f "{}" -s'.format(norm_path))

        elif export_format == "abc":
            try:
                if not cmds.pluginInfo("AbcExport", q=True, loaded=True):
                    cmds.loadPlugin("AbcExport")
            except Exception:
                pass

            job_str = (
                '-frameRange {start} {end} -step {step} '
                '-worldSpace -dataFormat ogawa '
                '-root {root} -file "{fpath}"'
            ).format(
                start=start_frame,
                end=end_frame,
                step=step,
                root=baked_cam,
                fpath=output_file.replace("\\", "/"),
            )
            cmds.AbcExport(job=job_str)
        else:
            raise ValueError("Unsupported camera format: {}".format(export_format))

    finally:
        if cmds.objExists(baked_cam):
            cmds.delete(baked_cam)

    return output_file
