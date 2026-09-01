# -*- coding: utf-8 -*-
"""Shot Package Importer and 1-Click Scene Assembler for Anim I/O."""

from __future__ import absolute_import, division, print_function

import os
import maya.cmds as cmds
import maya.mel as mel

from .manifest_builder import load_shot_manifest


def apply_shot_time_settings(manifest_data):
    """Set Maya playback range and FPS from manifest data."""
    fr = manifest_data.get("frame_range", {})
    start = fr.get("start", 1001)
    end = fr.get("end", 1100)
    fps = manifest_data.get("fps", 24.0)

    # Set timeline
    cmds.playbackOptions(minTime=start, maxTime=end, animationStartTime=start, animationEndTime=end)
    cmds.currentTime(start)

    # Set FPS
    fps_mapping = {
        24.0: "film",
        25.0: "pal",
        30.0: "ntsc",
        48.0: "show",
        50.0: "palf",
        60.0: "ntscf",
    }
    unit = fps_mapping.get(float(fps), "film")
    try:
        cmds.currentUnit(time=unit)
    except Exception:
        pass


def import_shot_camera(package_dir, camera_record, lock_attributes=True):
    """Import or reference the shot camera from the package."""
    cam_file = camera_record.get("file")
    if not cam_file:
        return None

    # Resolve camera file with subfolder fallbacks
    cam_path = os.path.join(package_dir, cam_file)
    if not os.path.isfile(cam_path):
        base_cam = os.path.basename(cam_file)
        for sub in ("alembic", "fbx", ""):
            cand = os.path.join(package_dir, sub, base_cam) if sub else os.path.join(package_dir, base_cam)
            if os.path.isfile(cand):
                cam_path = cand
                break

    if not os.path.isfile(cam_path):
        raise RuntimeError("Camera file not found: {}".format(cam_path))

    fmt = camera_record.get("format", "fbx").lower()

    if fmt == "fbx":
        if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
            try:
                cmds.loadPlugin("fbxmaya", quiet=True)
            except Exception:
                pass
        mel.eval('FBXImport -f "{}"'.format(cam_path.replace("\\", "/")))
    elif fmt in ["abc", "alembic"]:
        if not cmds.pluginInfo("AbcImport", query=True, loaded=True):
            cmds.loadPlugin("AbcImport", quiet=True)
        cmds.AbcImport(cam_path.replace("\\", "/"), mode="import")

    # Locate and lock only the newly imported shot camera transforms
    if lock_attributes:
        default_cams = ("persp", "top", "front", "side")
        cams = cmds.ls(type="camera", long=True) or []
        for c in cams:
            parents = cmds.listRelatives(c, parent=True, fullPath=True)
            if parents:
                t = parents[0]
                short = t.split("|")[-1].lower().split(":")[-1]
                if short in default_cams:
                    continue
                for attr in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"):
                    try:
                        cmds.setAttr(t + "." + attr, lock=True)
                    except Exception:
                        pass
    return cam_path


def import_asset_cache(package_dir, asset_record):
    """Import an Alembic or FBX asset cache into the scene."""
    asset_file = asset_record.get("file")
    if not asset_file:
        return None

    # Resolve asset file with subfolder fallbacks
    asset_path = os.path.join(package_dir, asset_file)
    if not os.path.isfile(asset_path):
        base_asset = os.path.basename(asset_file)
        for sub in ("alembic", "fbx", ""):
            cand = os.path.join(package_dir, sub, base_asset) if sub else os.path.join(package_dir, base_asset)
            if os.path.isfile(cand):
                asset_path = cand
                break

    if not os.path.isfile(asset_path):
        raise RuntimeError("Asset file not found: {}".format(asset_path))

    fmt = asset_record.get("format", "abc").lower()
    if fmt in ["abc", "alembic"]:
        if not cmds.pluginInfo("AbcImport", query=True, loaded=True):
            cmds.loadPlugin("AbcImport", quiet=True)
        cmds.AbcImport(asset_path.replace("\\", "/"), mode="import")
    elif fmt == "fbx":
        if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
            try:
                cmds.loadPlugin("fbxmaya", quiet=True)
            except Exception:
                pass
        mel.eval('FBXImport -f "{}"'.format(asset_path.replace("\\", "/")))

    return asset_path


def import_shot_package(
    package_dir_or_manifest,
    import_time_settings=True,
    import_camera=True,
    import_characters=True,
    import_props=True,
    lock_camera=True,
):
    """
    Master downstream shot assembly: loads manifest and constructs the assembled shot scene.
    """
    manifest = load_shot_manifest(package_dir_or_manifest)
    if not manifest:
        raise ValueError("Invalid shot package directory or manifest: {}".format(package_dir_or_manifest))

    package_dir = manifest["_package_dir"]

    # 1. Import Camera
    cam_imported = None
    if import_camera and manifest.get("camera"):
        cam_imported = import_shot_camera(package_dir, manifest["camera"], lock_attributes=lock_camera)

    # 2. Import Characters
    chars_imported = []
    if import_characters:
        for c_rec in manifest.get("characters", []):
            try:
                p = import_asset_cache(package_dir, c_rec)
                if p:
                    chars_imported.append(p)
            except Exception as e:
                print("[ScarTools Anim I/O] Character import warning: {}".format(e))

    # 3. Import Props
    props_imported = []
    if import_props:
        for p_rec in manifest.get("props", []):
            try:
                p = import_asset_cache(package_dir, p_rec)
                if p:
                    props_imported.append(p)
            except Exception as e:
                print("[ScarTools Anim I/O] Prop import warning: {}".format(e))

    # 4. Apply frame range and FPS (Applied after asset imports to ensure FBX does not overwrite timeline)
    if import_time_settings:
        apply_shot_time_settings(manifest)

    return {
        "success": True,
        "manifest": manifest,
        "camera_imported": bool(cam_imported),
        "characters_imported": len(chars_imported),
        "props_imported": len(props_imported),
    }


def assemble_shot_scene(package_dir_or_manifest):
    """1-Click helper to assemble full shot scene."""
    return import_shot_package(package_dir_or_manifest)
