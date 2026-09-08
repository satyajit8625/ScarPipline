# -*- coding: utf-8 -*-
"""Headless operations layer for Anim I/O with atomic SceneTransactions."""

from __future__ import absolute_import, division, print_function

import os

from scartools.framework import SceneTransaction
from scartools.framework.logging import emit_log
from scartools.licensing import require_license

from .api.manifest_builder import build_shot_manifest, save_shot_manifest, load_shot_manifest
from .api.camera import discover_shot_cameras, bake_camera_world_space, export_camera
from .api.exporter import export_shot_package as _api_export_shot, discover_scene_assets
from .api.importer import import_shot_package as _api_import_shot, apply_shot_time_settings


def export_shot_package(
    output_dir,
    shot_name,
    start_frame,
    end_frame,
    fps=24.0,
    camera_node=None,
    export_camera=True,
    camera_format="fbx",
    character_nodes=None,
    character_formats=("abc",),
    prop_nodes=None,
    prop_formats=("abc",),
    handles=0,
    step=1.0,
    **kwargs
):
    """Export shot package with atomic undo safety and license validation."""
    require_license("ScarTools_AnimExport")

    char_count = len(character_nodes or [])
    prop_count = len(prop_nodes or [])
    total_assets = char_count + prop_count + (1 if (camera_node and export_camera) else 0)
    
    clean_output_dir = str(output_dir or "").replace("\\", "/")
    if (str(output_dir).startswith("\\\\") or str(output_dir).startswith("//")) and not clean_output_dir.startswith("//"):
        clean_output_dir = "/" + clean_output_dir

    emit_log(
        "═" * 50 + "\n"
        "🎬 INITIATING ANIM EXPORT PIPELINE\n"
        "• Shot: {}\n"
        "• Timeline: {} - {} (Handles: ±{}, Step: {})\n"
        "• Frame Rate: {} FPS\n"
        "• Targets: {} characters, {} props, camera={}\n"
        "• Output Dir: {}\n".format(
            shot_name, start_frame, end_frame, handles, step, fps, char_count, prop_count, bool(camera_node), clean_output_dir
        ) + "═" * 50,
        level="INFO",
        source="AnimExport",
    )

    result = _api_export_shot(
        output_dir=output_dir,
        shot_name=shot_name,
        start_frame=start_frame,
        end_frame=end_frame,
        fps=fps,
        camera_node=camera_node,
        export_camera=export_camera,
        camera_format=camera_format,
        character_nodes=character_nodes,
        character_formats=character_formats,
        prop_nodes=prop_nodes,
        prop_formats=prop_formats,
        handles=handles,
        step=step,
        **kwargs
    )

    summary_files = result.get("exported_files", [])
    file_list_str = "\n  → ".join([""] + [os.path.basename(f) for f in summary_files])
    clean_target_dir = str(result.get("target_dir", "")).replace("\\", "/")
    if (str(result.get("target_dir", "")).startswith("\\\\") or str(result.get("target_dir", "")).startswith("//")) and not clean_target_dir.startswith("//"):
        clean_target_dir = "/" + clean_target_dir

    emit_log(
        "✅ EXPORT COMPLETE: {} total asset caches generated successfully!\n"
        "• Destination: {}\n"
        "• Manifest: {}\n"
        "• Files Written:{}\n".format(
            len(summary_files),
            clean_target_dir,
            os.path.basename(result["manifest_path"]),
            file_list_str,
        ),
        level="SUCCESS",
        source="AnimExport",
    )
    return result


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
    """Import and assemble shot package inside atomic undo transaction."""
    require_license("ScarTools_AnimImport")

    with SceneTransaction("ScarTools_AssembleShot"):
        emit_log("Assembling shot scene from '{}' (version: {})...".format(package_dir_or_manifest, version or "latest"), level="INFO", source="anim_io")
        result = _api_import_shot(
            package_dir_or_manifest=package_dir_or_manifest,
            version=version,
            import_time_settings=import_time_settings,
            import_camera=import_camera,
            import_characters=import_characters,
            import_props=import_props,
            lock_camera=lock_camera,
            preferred_format=preferred_format,
            callbacks=callbacks,
        )
        emit_log(
            "Shot assembled: {} characters, {} props, camera={}".format(
                result["characters_imported"],
                result["props_imported"],
                result["camera_imported"],
            ),
            level="SUCCESS",
            source="anim_io",
        )
    return result
