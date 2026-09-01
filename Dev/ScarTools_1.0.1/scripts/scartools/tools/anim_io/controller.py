# -*- coding: utf-8 -*-
"""
Central State Model & Controller for Animation Export Suite.
Handles asset discovery, naming validation, export plan generation, and single-source-of-truth UI state.
"""

from __future__ import absolute_import, division, print_function

import os
import maya.cmds as cmds

from scartools.framework import ToolController
from scartools.framework.logging import emit_log
from scartools.framework import parse_shot_scene_identity
from .operations import (
    export_shot_package,
    import_shot_package,
    discover_scene_assets,
    load_shot_manifest,
)
from .api.camera import find_active_shot_camera, fix_or_create_shot_camera


class AnimExportStateEnum(object):
    """Centralized lifecycle states for the Anim Export tool."""
    NO_ASSETS = "NO_ASSETS"
    SCANNING = "SCANNING"
    READY = "READY"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"
    EXPORTING = "EXPORTING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class AnimAssetItem(object):
    """Data container for a detected exportable asset or camera."""

    def __init__(self, name, node, item_type="asset", status="Ready", status_variant="success",
                 checked=True, expected_name="", rename_safe=True, details=""):
        self.name = str(name)
        self.node = str(node or "")
        self.item_type = str(item_type)  # "camera", "character", "prop", "asset"
        self.status = str(status)
        self.status_variant = str(status_variant)  # "success", "warning", "error", "neutral"
        self.checked = bool(checked)
        self.expected_name = str(expected_name or name)
        self.rename_safe = bool(rename_safe)
        self.details = str(details)


class AnimIOController(ToolController):
    """
    Central Controller and State Machine coordinating Anim Export intelligence.
    Ensures table, asset counts, status dot, footer message, and export button derive from 1 model.
    """

    def __init__(self):
        super(AnimIOController, self).__init__(tool_id="scartools_anim_io")
        self.state = AnimExportStateEnum.NO_ASSETS
        self.format_mode = "both"  # "both", "abc", "fbx"
        self.shot_name = "untitled_shot"
        self.shot_root = ""
        self.project_name = ""
        self.start_frame = 1001
        self.end_frame = 1100
        self.fps = 24.0
        self.assets = []  # List of AnimAssetItem
        self.export_plan = []  # Internal routing plan
        self.last_export_result = None

    def scan_scene(self):
        """
        Inspect active Maya scene:
        1. Resolve shot identity and export paths
        2. Detect cameras, characters, and prop rigs
        3. Validate naming against central pipeline standards
        4. Classify assets by actual node types/shapes/skinning
        5. Compute single-source-of-truth state
        """
        self.state = AnimExportStateEnum.SCANNING
        self.assets = []
        self.export_plan = []

        # 1. Resolve Shot Identity
        identity = parse_shot_scene_identity()
        self.shot_name = identity.get("shot_name") or "untitled_shot"
        self.shot_root = identity.get("export_dir") or ""
        self.project_name = identity.get("project") or "Active Maya Scene"
        is_unsaved = (self.shot_name.lower() in ("untitled_shot", "untitled_scene", "untitled"))

        target_cam_name = (self.shot_name + "_CAM") if not is_unsaved else "Shot_CAM"

        # 2. Timeline Frame Range
        try:
            if hasattr(cmds, "playbackOptions"):
                min_t = cmds.playbackOptions(q=True, minTime=True)
                max_t = cmds.playbackOptions(q=True, maxTime=True)
                if min_t is not None and max_t is not None:
                    self.start_frame = int(min_t)
                    self.end_frame = int(max_t)
                    if self.start_frame > self.end_frame:
                        self.start_frame, self.end_frame = self.end_frame, self.start_frame
        except Exception:
            pass

        # 3. Detect Cameras
        cam_node = find_active_shot_camera(self.shot_name)
        if cam_node and cmds.objExists(cam_node):
            short_cam = cam_node.split("|")[-1]
            if short_cam.lower() == target_cam_name.lower():
                cam_status = "Ready"
                cam_variant = "success"
                rename_safe = True
            else:
                cam_status = "Rename Needed"
                cam_variant = "warning"
                rename_safe = True  # Safe auto-rename during export or double-click

            self.assets.append(AnimAssetItem(
                name=short_cam,
                node=cam_node,
                item_type="camera",
                status=cam_status,
                status_variant=cam_variant,
                checked=True,
                expected_name=target_cam_name,
                rename_safe=rename_safe,
                details="Shot Camera",
            ))
        elif not is_unsaved:
            # Camera missing
            self.assets.append(AnimAssetItem(
                name=target_cam_name,
                node="",
                item_type="camera",
                status="Missing Camera",
                status_variant="error",
                checked=False,
                expected_name=target_cam_name,
                rename_safe=False,
                details="Camera not found in scene. Double-click to create.",
            ))

        # 4. Detect Scene Rigs & Meshes (Inspecting actual Maya nodes)
        raw_data = discover_scene_assets()
        raw_assets = raw_data.get("assets", []) or (raw_data.get("characters", []) + raw_data.get("props", []))
        seen_roots = set()

        for anode in raw_assets:
            if not cmds.objExists(anode):
                continue
            long_path = cmds.ls(anode, long=True)[0]
            if long_path in seen_roots:
                continue
            seen_roots.add(long_path)
            short = long_path.split("|")[-1]

            # Inspect actual Maya node structure
            has_skin = False
            has_mesh = False
            has_joints = False

            descendants = cmds.listRelatives(long_path, allDescendents=True, fullPath=True) or []
            for d in descendants:
                ntype = cmds.nodeType(d)
                if ntype == "mesh":
                    has_mesh = True
                    # Check skinClusters with fast early exit
                    if not has_skin:
                        hist = cmds.listHistory(d, pruneDagObjects=True) or []
                        if any(cmds.nodeType(h) == "skinCluster" for h in hist):
                            has_skin = True
                elif ntype == "joint":
                    has_joints = True
                if has_skin and has_joints and has_mesh:
                    break

            asset_type = "character" if (has_skin or has_joints) else "prop"

            self.assets.append(AnimAssetItem(
                name=short,
                node=long_path,
                item_type=asset_type,
                status="Ready",
                status_variant="success",
                checked=True,
                expected_name=short,
                rename_safe=True,
                details="Skinned Character Rig" if has_skin else "Scene Asset Rig",
            ))

        # 5. Build Internal Export Plan
        self._recompute_export_plan()

        # 6. Recompute Overall State
        self.recompute_state()
        return self.state

    def _recompute_export_plan(self):
        """Generate backend routing plan mapping assets to appropriate ABC/FBX formats."""
        self.export_plan = []
        fmt = self.format_mode.lower()

        for item in self.assets:
            if not item.checked or not item.node:
                continue

            if item.item_type == "camera":
                # Cameras route strictly to FBX camera animation
                self.export_plan.append({
                    "name": item.name,
                    "node": item.node,
                    "type": "camera",
                    "formats": ["fbx"],
                    "output_file": (item.expected_name or item.name) + ".fbx",
                })
            elif item.item_type == "character":
                # Characters route to ABC geometry + FBX skeletal animation
                fmts = ["abc", "fbx"] if fmt == "both" else [fmt]
                self.export_plan.append({
                    "name": item.name,
                    "node": item.node,
                    "type": "character",
                    "formats": fmts,
                    "output_file": item.name,
                })
            else:
                # Props route to ABC point cache and/or FBX transform animation
                fmts = ["abc", "fbx"] if fmt == "both" else [fmt]
                self.export_plan.append({
                    "name": item.name,
                    "node": item.node,
                    "type": "prop",
                    "formats": fmts,
                    "output_file": item.name,
                })

    def recompute_state(self):
        """
        Derive central UI state from detected assets, selections, and validation issues:
        - NO_ASSETS: 0 assets in table
        - BLOCKED: 0 checked assets, missing required camera, invalid shot path
        - WARNING: 1+ checked assets have non-blocking auto-fixable renames
        - READY: All checked assets 100% valid
        """
        self._recompute_export_plan()

        total_assets = len(self.assets)
        if total_assets == 0:
            self.state = AnimExportStateEnum.NO_ASSETS
            return self.state

        checked_items = [a for a in self.assets if a.checked]
        if len(checked_items) == 0:
            self.state = AnimExportStateEnum.BLOCKED
            return self.state

        # Check blocking errors
        has_blocking = False
        has_warning = False

        for item in checked_items:
            if item.status_variant == "error" or not item.node:
                has_blocking = True
            elif item.status_variant == "warning":
                has_warning = True

        if not self.shot_root or (self.shot_name.lower() in ("untitled_shot", "untitled_scene", "untitled")):
            has_warning = True

        if has_blocking:
            self.state = AnimExportStateEnum.BLOCKED
        elif has_warning:
            self.state = AnimExportStateEnum.WARNING
        else:
            self.state = AnimExportStateEnum.READY

        return self.state

    def get_asset_count_text(self):
        """Correct singular/plural asset count string. Never '1 asset(s)'."""
        count = len(self.assets)
        if count == 1:
            return "1 asset detected"
        return "{} assets detected".format(count)

    def get_status_info(self):
        """
        Return (status_text, status_state, message_text, message_state, export_enabled).
        Single source of truth for UI footer.
        """
        checked_count = len([a for a in self.assets if a.checked])
        total_count = len(self.assets)
        renamed_count = len([a for a in self.assets if a.checked and a.status == "Rename Needed"])

        if self.state == AnimExportStateEnum.NO_ASSETS:
            return (
                "Waiting",
                "idle",
                "No exportable assets detected.",
                "neutral",
                False,
            )
        elif self.state == AnimExportStateEnum.SCANNING:
            return (
                "Scanning...",
                "running",
                "Scanning Maya scene for assets and cameras...",
                "neutral",
                False,
            )
        elif self.state == AnimExportStateEnum.BLOCKED:
            if checked_count == 0:
                msg = "Select at least 1 asset in the table to export."
            else:
                blocked_items = [a for a in self.assets if a.checked and (a.status_variant == "error" or not a.node)]
                b_count = len(blocked_items)
                att_part = "1 asset requires attention" if b_count <= 1 else "{} assets require attention".format(b_count)
                msg = "{} selected · {} before export.".format(
                    "1 asset" if checked_count == 1 else "{} assets".format(checked_count),
                    att_part,
                )
            return (
                "Blocked",
                "error",
                msg,
                "warning",
                False,
            )
        elif self.state == AnimExportStateEnum.WARNING:
            if renamed_count > 0:
                rename_part = "1 asset will be corrected automatically." if renamed_count == 1 else "{} assets will be corrected automatically.".format(renamed_count)
                msg = "{} selected · {}".format(
                    "1 asset" if checked_count == 1 else "{} assets".format(checked_count),
                    rename_part,
                )
            else:
                msg = "Scene is unsaved. Will export to default scene directory."
            return (
                "Warning",
                "warning",
                msg,
                "warning",
                True,
            )
        elif self.state == AnimExportStateEnum.READY:
            msg = "{} validated and ready for export.".format(
                "1 asset" if checked_count == 1 else "{} assets".format(checked_count)
            )
            return (
                "Ready",
                "idle",
                msg,
                "neutral",
                True,
            )
        elif self.state == AnimExportStateEnum.EXPORTING:
            return (
                "Exporting...",
                "running",
                "Exporting shot caches into Alembic/ and FBX/...",
                "neutral",
                False,
            )
        elif self.state == AnimExportStateEnum.SUCCESS:
            return (
                "Complete",
                "idle",
                "{} exported successfully.".format(
                    "1 asset" if checked_count == 1 else "{} assets".format(checked_count)
                ),
                "neutral",
                True,
            )
        elif self.state == AnimExportStateEnum.FAILED:
            return (
                "Failed",
                "error",
                "Export encountered errors. Check Global Log for details.",
                "warning",
                True,
            )
        return ("Ready", "idle", "Ready to export shot caches.", "neutral", True)
