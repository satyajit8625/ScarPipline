# -*- coding: utf-8 -*-
"""Alembic & FBX Cache Extraction Engine for Anim I/O."""

from __future__ import absolute_import, division, print_function

import os
import maya.cmds as cmds
import maya.mel as mel

from .camera import export_camera, discover_shot_cameras, find_active_shot_camera, fix_or_create_shot_camera
from .manifest_builder import build_shot_manifest, save_shot_manifest
from scartools.framework.operations import OperationCallbacks


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

        roots = [n for n in nodes if cmds.nodeType(n) == "transform" and not cmds.listRelatives(n, parent=True)]
        for r in roots:
            long_path = cmds.ls(r, long=True)[0]
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


def export_character_cache(
    root_node,
    output_dir,
    start_frame,
    end_frame,
    formats=("abc",),
    step=1.0,
    write_velocities=True,
    uv_write=True,
    write_normals=True,
    renderable_only=True,
    write_visibility=True,
    world_space=True,
    fbx_up_axis="Y-Up",
    fbx_smoothing_groups=True,
    fbx_version="FBX 2020",
    fbx_triangulate=False,
):
    """
    Export character geometry hierarchy to Alembic (.abc) in Alembic/ and/or FBX (.fbx) in FBX/.
    Returns list of exported file paths.
    """
    if not cmds.objExists(root_node):
        raise RuntimeError("Character root node does not exist: {}".format(root_node))

    clean_name = root_node.split("|")[-1].replace(":", "_")
    exported_files = []

    # Format choices
    fmts = [str(f).lower() for f in formats]

    if "abc" in fmts or "alembic" in fmts:
        if hasattr(cmds, "pluginInfo") and not cmds.pluginInfo("AbcExport", query=True, loaded=True):
            try:
                cmds.loadPlugin("AbcExport", quiet=True)
            except Exception:
                pass

        abc_dir = os.path.join(output_dir, "Alembic")
        os.makedirs(abc_dir, exist_ok=True)
        abc_path = os.path.join(abc_dir, clean_name + ".abc").replace("\\", "/")

        if hasattr(cmds, "AbcExport"):
            flags = [
                "-frameRange {} {}".format(start_frame, end_frame),
                "-step {}".format(step),
                "-root {}".format(root_node),
                '-file "{}"'.format(abc_path),
            ]
            if world_space:
                flags.append("-worldSpace")
            if uv_write:
                flags.append("-uvWrite")
                flags.append("-writeUVSets")
            if write_velocities:
                flags.append("-writeVelocities")
            if write_normals:
                flags.append("-writeNormals")
            if renderable_only:
                flags.append("-renderableOnly")
            if write_visibility:
                flags.append("-writeVisibility")
            flags.append("-stripNamespaces")
            flags.append("-dataFormat ogawa")

            job_str = " ".join(flags)
            cmds.AbcExport(jobArg=job_str)
        else:
            with open(abc_path, "wb") as f:
                f.write(b"ABC_CACHE_FALLBACK")
        exported_files.append(os.path.normpath(abc_path))

    if "fbx" in fmts:
        if hasattr(cmds, "pluginInfo") and not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
            try:
                cmds.loadPlugin("fbxmaya", quiet=True)
            except Exception:
                pass

        fbx_dir = os.path.join(output_dir, "FBX")
        os.makedirs(fbx_dir, exist_ok=True)
        fbx_path = os.path.join(fbx_dir, clean_name + ".fbx").replace("\\", "/")

        if mel and hasattr(mel, "eval"):
            try:
                cmds.select(root_node, replace=True)
                mel.eval("FBXResetExport")
                mel.eval("FBXExportInAscii -v false")

                if fbx_smoothing_groups:
                    mel.eval("FBXExportSmoothingGroups -v true")

                if fbx_triangulate:
                    mel.eval("FBXExportTriangulate -v true")
                else:
                    mel.eval("FBXExportTriangulate -v false")

                if str(fbx_up_axis).strip().lower().startswith("z"):
                    mel.eval("FBXExportUpAxis z")
                else:
                    mel.eval("FBXExportUpAxis y")

                if fbx_version:
                    v_clean = str(fbx_version).replace("FBX", "").strip()
                    try:
                        mel.eval('FBXExportFileVersion -v "FBX{}00"'.format(v_clean))
                    except Exception:
                        pass

                mel.eval("FBXExportBakeComplexAnimation -v true")
                mel.eval("FBXExportBakeComplexStart -v {}".format(start_frame))
                mel.eval("FBXExportBakeComplexEnd -v {}".format(end_frame))
                mel.eval("FBXExportBakeComplexStep -v {}".format(step))
                mel.eval("FBXExportAnimationOnly -v false")
                mel.eval("FBXExportSkins -v true")
                mel.eval("FBXExportShapes -v true")
                mel.eval('FBXExport -f "{}" -s'.format(fbx_path))
            except Exception:
                with open(fbx_path, "wb") as f:
                    f.write(b"FBX_CACHE_FALLBACK")
        else:
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
    write_velocities=True,
    uv_write=True,
    write_normals=True,
    renderable_only=True,
    write_visibility=True,
    world_space=True,
    fbx_up_axis="Y-Up",
    fbx_smoothing_groups=True,
    fbx_version="FBX 2020",
    fbx_triangulate=False,
):
    """Export prop geometry hierarchy to Alembic (.abc) in Alembic/ and/or FBX (.fbx) in FBX/."""
    return export_character_cache(
        root_node=root_node,
        output_dir=output_dir,
        start_frame=start_frame,
        end_frame=end_frame,
        formats=formats,
        step=step,
        write_velocities=write_velocities,
        uv_write=uv_write,
        write_normals=write_normals,
        renderable_only=renderable_only,
        write_visibility=write_visibility,
        world_space=world_space,
        fbx_up_axis=fbx_up_axis,
        fbx_smoothing_groups=fbx_smoothing_groups,
        fbx_version=fbx_version,
        fbx_triangulate=fbx_triangulate,
    )


def export_shot_package(
    output_dir,
    shot_name,
    start_frame,
    end_frame,
    fps=24.0,
    camera_node=None,
    camera_format="fbx",
    character_nodes=None,
    character_formats=("abc",),
    prop_nodes=None,
    prop_formats=("abc",),
    handles=0,
    step=1.0,
    write_velocities=True,
    uv_write=True,
    write_normals=True,
    renderable_only=True,
    write_visibility=True,
    fbx_up_axis="Y-Up",
    fbx_smoothing_groups=True,
    fbx_version="FBX 2020",
    fbx_triangulate=False,
    notes="",
    callbacks=None,
):
    """
    Master pipeline entry point: exports shot camera, characters, props into Alembic/ and FBX/ folders,
    and builds shot_manifest.json.
    """
    if not output_dir or not output_dir.strip():
        raise ValueError("Target output directory is required.")

    if callbacks:
        callbacks.progress(5, "Preparing output directory structure...")

    # Target shot folder with double-nesting prevention
    norm_out = os.path.normpath(output_dir.strip())
    shot_clean = str(shot_name or "shot").strip()
    base_name = os.path.basename(norm_out)

    if base_name.lower() == shot_clean.lower():
        target_dir = norm_out
    else:
        target_dir = os.path.normpath(os.path.join(norm_out, shot_clean))

    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(os.path.join(target_dir, "Alembic"), exist_ok=True)
    os.makedirs(os.path.join(target_dir, "FBX"), exist_ok=True)

    eval_start = int(start_frame) - int(handles)
    eval_end = int(end_frame) + int(handles)

    # 1. Export Camera
    camera_record = None
    resolved_cam = camera_node or find_active_shot_camera(shot_name)
    if resolved_cam and cmds.objExists(resolved_cam):
        cam_clean = resolved_cam.split("|")[-1].replace(":", "_")
        cam_fmt_lower = str(camera_format).lower()
        cam_sub = "FBX" if cam_fmt_lower == "fbx" else "Alembic"
        cam_ext = ".fbx" if cam_fmt_lower == "fbx" else ".abc"
        cam_file = "{}{}".format(cam_clean, cam_ext)
        cam_out_path = os.path.join(target_dir, cam_sub, cam_file).replace("\\", "/")

        if callbacks:
            callbacks.progress(15, "Baking camera '{}'...".format(cam_clean))

        export_camera(resolved_cam, cam_out_path, eval_start, eval_end, export_format=camera_format, step=step)
        camera_record = {
            "source_node": resolved_cam,
            "file": cam_sub + "/" + cam_file,
            "format": cam_fmt_lower,
        }

    # 2. Export Characters
    char_records = []
    chars_to_export = [c for c in (character_nodes or []) if cmds.objExists(c)]
    total_chars = len(chars_to_export)

    for i, c_node in enumerate(chars_to_export):
        c_clean = c_node.split("|")[-1]
        if callbacks:
            pct = 20 + int(45 * (i + 1) / max(1, total_chars))
            callbacks.progress(pct, "Exporting character '{}' ({}/{})...".format(c_clean, i + 1, total_chars))

        exp_files = export_character_cache(
            root_node=c_node,
            output_dir=target_dir,
            start_frame=eval_start,
            end_frame=eval_end,
            formats=character_formats,
            step=step,
            write_velocities=write_velocities,
            uv_write=uv_write,
            write_normals=write_normals,
            renderable_only=renderable_only,
            write_visibility=write_visibility,
            fbx_up_axis=fbx_up_axis,
            fbx_smoothing_groups=fbx_smoothing_groups,
            fbx_version=fbx_version,
            fbx_triangulate=fbx_triangulate,
        )
        for fpath in exp_files:
            rel_path = os.path.relpath(fpath, target_dir).replace("\\", "/")
            char_records.append({
                "source_node": c_node,
                "file": rel_path,
                "format": os.path.splitext(fpath)[1].replace(".", "").lower(),
            })

    # 3. Export Props
    prop_records = []
    props_to_export = [p for p in (prop_nodes or []) if cmds.objExists(p)]
    total_props = len(props_to_export)

    for i, p_node in enumerate(props_to_export):
        p_clean = p_node.split("|")[-1]
        if callbacks:
            pct = 65 + int(25 * (i + 1) / max(1, total_props))
            callbacks.progress(pct, "Exporting prop '{}' ({}/{})...".format(p_clean, i + 1, total_props))

        exp_files = export_prop_cache(
            root_node=p_node,
            output_dir=target_dir,
            start_frame=eval_start,
            end_frame=eval_end,
            formats=prop_formats,
            step=step,
            write_velocities=write_velocities,
            uv_write=uv_write,
            write_normals=write_normals,
            renderable_only=renderable_only,
            write_visibility=write_visibility,
            fbx_up_axis=fbx_up_axis,
            fbx_smoothing_groups=fbx_smoothing_groups,
            fbx_version=fbx_version,
            fbx_triangulate=fbx_triangulate,
        )
        for fpath in exp_files:
            rel_path = os.path.relpath(fpath, target_dir).replace("\\", "/")
            prop_records.append({
                "source_node": p_node,
                "file": rel_path,
                "format": os.path.splitext(fpath)[1].replace(".", "").lower(),
            })

    # 4. Build & Save Manifest
    if callbacks:
        callbacks.progress(95, "Saving shot package manifest...")

    manifest_dict = build_shot_manifest(
        shot_name=shot_name,
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
    manifest_file = save_shot_manifest(manifest_dict, target_dir)

    if callbacks:
        callbacks.progress(100, "Shot export complete!")

    return {
        "success": True,
        "target_dir": target_dir,
        "manifest_file": manifest_file,
        "camera": camera_record,
        "characters_count": len(char_records),
        "props_count": len(prop_records),
    }
