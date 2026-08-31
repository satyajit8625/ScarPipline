# -*- coding: utf-8 -*-
"""Headless operations layer for Anim I/O with atomic SceneTransactions."""

from __future__ import absolute_import, division, print_function

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
    camera_format="fbx",
    character_nodes=None,
    character_formats=("abc",),
    prop_nodes=None,
    prop_formats=("abc",),
    handles=0,
    step=1.0,
    write_velocities=True,
    uv_write=True,
    notes="",
):
    """Export shot package with atomic undo safety and license validation."""
    require_license("ScarTools_AnimExport")

    emit_log("Starting shot package export for '{}'...".format(shot_name), level="INFO", source="anim_io")
    result = _api_export_shot(
        output_dir=output_dir,
        shot_name=shot_name,
        start_frame=start_frame,
        end_frame=end_frame,
        fps=fps,
        camera_node=camera_node,
        camera_format=camera_format,
        character_nodes=character_nodes,
        character_formats=character_formats,
        prop_nodes=prop_nodes,
        prop_formats=prop_formats,
        handles=handles,
        step=step,
        write_velocities=write_velocities,
        uv_write=uv_write,
        notes=notes,
    )
    emit_log("Shot package exported successfully to '{}'.".format(result["target_dir"]), level="SUCCESS", source="anim_io")
    return result


def import_shot_package(
    package_dir_or_manifest,
    import_time_settings=True,
    import_camera=True,
    import_characters=True,
    import_props=True,
    lock_camera=True,
):
    """Import and assemble shot package inside atomic undo transaction."""
    require_license("ScarTools_AnimImport")

    with SceneTransaction("ScarTools_AssembleShot"):
        emit_log("Assembling shot scene from '{}'...".format(package_dir_or_manifest), level="INFO", source="anim_io")
        result = _api_import_shot(
            package_dir_or_manifest=package_dir_or_manifest,
            import_time_settings=import_time_settings,
            import_camera=import_camera,
            import_characters=import_characters,
            import_props=import_props,
            lock_camera=lock_camera,
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
