# -*- coding: utf-8 -*-
"""Camera Discovery, World-Space Baking, and Export for Anim I/O."""

from __future__ import absolute_import, division, print_function

import os
import maya.cmds as cmds

DEFAULT_CAMERAS = {"persp", "top", "front", "side"}


def discover_shot_cameras():
    """Return all non-default scene camera transform names."""
    all_cams = cmds.ls(type="camera", long=True) or []
    shot_cams = []
    for cam_shape in all_cams:
        parents = cmds.listRelatives(cam_shape, parent=True, fullPath=True)
        if not parents:
            continue
        cam_transform = parents[0]
        short_name = cam_transform.split("|")[-1].split(":")[-1]
        if short_name.lower() not in DEFAULT_CAMERAS:
            shot_cams.append(cam_transform)
    return sorted(list(set(shot_cams)))


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
