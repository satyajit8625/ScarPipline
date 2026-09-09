# -*- coding: utf-8 -*-
"""Shot Package Importer and 1-Click Scene Assembler for Anim I/O."""

from __future__ import absolute_import, division, print_function

import os
import maya.cmds as cmds
import maya.mel as mel

from .manifest_builder import load_shot_manifest
from scartools.framework.scene import suspend_viewport_refresh


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

    # Snapshot existing cameras in scene prior to import
    existing_cams = set(cmds.ls(type="camera", long=True) or [])

    if fmt == "fbx":
        if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
            try:
                cmds.loadPlugin("fbxmaya", quiet=True)
            except Exception:
                pass
        try:
            mel.eval("FBXResetImport")
            mel.eval("FBXImportMode -v add")
            mel.eval("FBXImportCameras -v true")
            mel.eval("FBXImportLights -v false")
            mel.eval("FBXImportAudio -v false")
            mel.eval("FBXImportSkins -v false")
            mel.eval("FBXImportShapes -v false")
        except Exception:
            pass
        mel.eval('FBXImport -f "{}"'.format(cam_path.replace("\\", "/")))
    elif fmt in ["abc", "alembic"]:
        if hasattr(cmds, "pluginInfo") and not cmds.pluginInfo("AbcImport", query=True, loaded=True):
            try:
                cmds.loadPlugin("AbcImport", quiet=True)
            except Exception:
                pass
        if hasattr(cmds, "AbcImport"):
            cmds.AbcImport(cam_path.replace("\\", "/"), mode="import")

    # Locate and lock only the newly imported shot camera transforms
    if lock_attributes:
        default_cams = ("persp", "top", "front", "side")
        current_cams = set(cmds.ls(type="camera", long=True) or [])
        new_cams = current_cams - existing_cams
        for c in new_cams:
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
        if hasattr(cmds, "pluginInfo") and not cmds.pluginInfo("AbcImport", query=True, loaded=True):
            try:
                cmds.loadPlugin("AbcImport", quiet=True)
            except Exception:
                pass
        if hasattr(cmds, "AbcImport"):
            cmds.AbcImport(asset_path.replace("\\", "/"), mode="import")
    elif fmt == "fbx":
        if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
            try:
                cmds.loadPlugin("fbxmaya", quiet=True)
            except Exception:
                pass
        try:
            mel.eval("FBXResetImport")
            mel.eval("FBXImportMode -v add")
            mel.eval("FBXImportCameras -v false")
            mel.eval("FBXImportLights -v false")
            mel.eval("FBXImportAudio -v false")
            mel.eval("FBXImportConstraints -v false")
            mel.eval("FBXImportSkins -v true")
            mel.eval("FBXImportShapes -v true")
        except Exception:
            pass
        mel.eval('FBXImport -f "{}"'.format(asset_path.replace("\\", "/")))

    return asset_path


def _filter_records(records, pref_fmt):
    """Filter records so duplicate formats of the same asset are not imported together."""
    clean_pref = str(pref_fmt or "abc").lower().strip()
    if clean_pref in ("both", "all"):
        return records

    by_source = {}
    for r in records:
        src = r.get("source_node") or os.path.splitext(os.path.basename(r.get("file", "")))[0]
        by_source.setdefault(src, []).append(r)

    selected = []
    for src, recs in by_source.items():
        match = None
        for r in recs:
            if r.get("format", "").lower() == clean_pref:
                match = r
                break
        if not match:
            match = recs[0]
        selected.append(match)
    return selected


def import_shot_package(
    package_dir_or_manifest,
    version=None,
    import_time_settings=True,
    import_camera=True,
    import_characters=True,
    import_props=True,
    lock_camera=True,
    preferred_format="abc",
    callbacks=None,
):
    """
    Master downstream shot assembly: loads manifest and constructs the assembled shot scene.
    Supports Schema 2.0.0 multi-version manifests and explicit version selection.
    Uses preferred_format ("abc", "fbx", "both") to prevent importing duplicate formats of
    the same character/prop and pauses Viewport 2.0 (OGS) to accelerate high-poly assembly.
    """
    manifest = load_shot_manifest(package_dir_or_manifest)
    if not manifest:
        # Check parent directory in case user passed a specific version directory like Alembic/v001
        p_dir = str(package_dir_or_manifest or "").replace("\\", "/")
        parent_candidate = os.path.dirname(p_dir)
        grandparent_candidate = os.path.dirname(parent_candidate)
        for cand in (parent_candidate, grandparent_candidate):
            if cand and os.path.isdir(cand):
                manifest = load_shot_manifest(cand)
                if manifest:
                    break

    if not manifest:
        raise ValueError("Invalid shot package directory or manifest: {}".format(package_dir_or_manifest))

    package_dir = manifest["_package_dir"]

    # Extract target version record from multi-version manifest
    if "versions" in manifest and manifest["versions"]:
        available_versions = manifest["versions"]
        if version:
            v_key = str(version).strip().lower()
            if v_key not in available_versions and ("v" + v_key) in available_versions:
                v_key = "v" + v_key
            if v_key not in available_versions:
                raise ValueError("Version '{}' not found in manifest. Available: {}".format(version, list(available_versions.keys())))
            v_record = available_versions[v_key]
        else:
            latest = manifest.get("latest_version")
            if latest and latest in available_versions:
                v_record = available_versions[latest]
            else:
                sorted_vers = sorted(available_versions.keys())
                v_record = available_versions[sorted_vers[-1]]
    else:
        # Legacy single-version manifest
        v_record = manifest

    camera_rec = v_record.get("camera")
    char_records = v_record.get("characters", [])
    prop_records = v_record.get("props", [])

    with suspend_viewport_refresh():
        # 1. Import Camera
        cam_imported = None
        if import_camera and camera_rec:
            if callbacks:
                callbacks.progress(10, "Importing shot camera...", current_item="Camera")
            cam_imported = import_shot_camera(package_dir, camera_rec, lock_attributes=lock_camera)

        # 2. Import Characters (filtered by preferred format)
        chars_imported = []
        if import_characters:
            char_targets = _filter_records(char_records, preferred_format)
            total_c = len(char_targets)
            for idx, c_rec in enumerate(char_targets):
                short_name = os.path.basename(c_rec.get("file", "character"))
                if callbacks:
                    pct = int(10 + (idx / max(1, total_c)) * 40)
                    callbacks.progress(pct, "Importing character {}/{} ('{}')...".format(idx + 1, total_c, short_name), current_item=short_name)
                try:
                    p = import_asset_cache(package_dir, c_rec)
                    if p:
                        chars_imported.append(p)
                except Exception as e:
                    try:
                        from scartools.framework.logging import emit_log
                        emit_log("Character import warning: {}".format(e), level="warning", source="AnimIO")
                    except Exception:
                        pass

        # 3. Import Props (filtered by preferred format)
        props_imported = []
        if import_props:
            prop_targets = _filter_records(prop_records, preferred_format)
            total_p = len(prop_targets)
            for idx, p_rec in enumerate(prop_targets):
                short_name = os.path.basename(p_rec.get("file", "prop"))
                if callbacks:
                    pct = int(50 + (idx / max(1, total_p)) * 40)
                    callbacks.progress(pct, "Importing prop {}/{} ('{}')...".format(idx + 1, total_p, short_name), current_item=short_name)
                try:
                    p = import_asset_cache(package_dir, p_rec)
                    if p:
                        props_imported.append(p)
                except Exception as e:
                    try:
                        from scartools.framework.logging import emit_log
                        emit_log("Prop import warning: {}".format(e), level="warning", source="AnimIO")
                    except Exception:
                        pass

        # 4. Apply frame range and FPS (Applied after asset imports to ensure FBX does not overwrite timeline)
        if import_time_settings:
            if callbacks:
                callbacks.progress(95, "Applying shot timeline settings...", current_item="Timeline")
            apply_shot_time_settings(v_record)

        if callbacks:
            callbacks.progress(100, "Shot assembly complete!", current_item="Done")

    return {
        "success": True,
        "manifest": manifest,
        "version": v_record.get("version", "v001"),
        "camera_imported": bool(cam_imported),
        "characters_imported": len(chars_imported),
        "props_imported": len(props_imported),
    }


def assemble_shot_scene(package_dir_or_manifest):
    """1-Click helper to assemble full shot scene."""
    return import_shot_package(package_dir_or_manifest)
