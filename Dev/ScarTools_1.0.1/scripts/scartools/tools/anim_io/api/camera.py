# -*- coding: utf-8 -*-
"""Camera Discovery, World-Space Baking, and Export for Anim I/O."""

from __future__ import absolute_import, division, print_function

import os
import maya.cmds as cmds

DEFAULT_CAMERAS = {"persp", "top", "front", "side"}


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
        shot_cams.sort(key=lambda c: (
            0 if pref in c.lower() and "cam" in c.lower() else (
                1 if "cam" in c.lower() else 2
            )
        ))
    else:
        shot_cams.sort(key=lambda c: (0 if "cam" in c.lower() else 1))

    return shot_cams


def find_active_shot_camera(preferred_shot_name=None):
    """
    Find the primary shot camera matching standard studio naming (e.g. PRT_SH_010_CAM).
    Returns long DAG path of the camera or None.
    """
    cams = discover_shot_cameras(preferred_shot_name=preferred_shot_name)
    if not cams:
        # Fallback check if any camera with CAM in scene exists
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
        for c in cams:
            short = c.split("|")[-1].lower()
            if short == pref + "_cam" or short == "cam_" + pref or short == pref:
                return c
        for c in cams:
            if pref in c.lower():
                return c

    return cams[0]


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
        [dup_cam, dup_shape],
        time=(start_frame, end_frame),
        simulation=True,
        sampleBy=1,
        disableImplicitControl=True,
        preserveOutsideKeys=False,
        sparseAnimCurveBake=False,
        removeBakedAttributeFromLayer=False,
        bakeOnOverrideLayer=False,
        minimizeRotation=True,
        controlPoints=False,
        shape=True,
    )

    # Delete constraint
    if cmds.objExists(p_const):
        cmds.delete(p_const)

    return dup_cam


def export_camera(camera_transform, output_path, start_frame, end_frame, export_format="fbx"):
    """
    Export camera to FBX or Alembic.
    """
    fmt = str(export_format or "fbx").lower()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Bake to clean world-space camera
    baked_cam = bake_camera_world_space(camera_transform, start_frame, end_frame)

    try:
        if fmt == "fbx":
            if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
                try:
                    cmds.loadPlugin("fbxmaya", quiet=True)
                except Exception:
                    pass

            cmds.select(baked_cam, replace=True)
            import maya.mel as mel
            mel.eval("FBXResetExport")
            mel.eval("FBXExportInAscii -v false")
            mel.eval("FBXExportBakeComplexAnimation -v true")
            mel.eval("FBXExportBakeComplexStart -v {}".format(start_frame))
            mel.eval("FBXExportBakeComplexEnd -v {}".format(end_frame))
            mel.eval("FBXExportBakeComplexStep -v 1")
            mel.eval("FBXExportCameras -v true")
            mel.eval("FBXExportLights -v false")
            mel.eval("FBXExportAudio -v false")
            mel.eval("FBXExportEmbeddedTextures -v false")
            mel.eval('FBXExport -f "{}" -s'.format(output_path.replace("\\", "/")))

        elif fmt in ["abc", "alembic"]:
            job_arg = '-frameRange {} {} -step 1 -worldSpace -root {} -file "{}"'.format(
                start_frame,
                end_frame,
                baked_cam,
                output_path.replace("\\", "/"),
            )
            cmds.AbcExport(jobArg=job_arg)
        else:
            raise ValueError("Unsupported camera export format: {}".format(fmt))

    finally:
        if cmds.objExists(baked_cam):
            cmds.delete(baked_cam)

    return output_path
